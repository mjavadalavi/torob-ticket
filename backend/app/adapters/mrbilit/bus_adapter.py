from __future__ import annotations

import asyncio
import logging
from collections.abc import Mapping
from datetime import datetime
from typing import Any
from urllib.parse import quote, urlencode

from app.adapters.mrbilit.base import MrBilitOfferStore
from app.adapters.mrbilit.http import MrBilitHttpClient
from app.adapters.mrbilit.parsing import (
    TEHRAN_TIMEZONE,
    bounded_text,
    normalized_text,
    number,
    parse_datetime,
)
from app.adapters.mrbilit.spec import (
    MRBILIT_BUS_LOCATIONS_URL,
    MRBILIT_BUS_SEARCH_URL,
    MRBILIT_SELLER,
)
from app.adapters.shared.branding import bus_operator_logo_url
from app.adapters.shared.context import ExpiringLruStore
from app.adapters.shared.parsing import ProviderRowError, mapping_rows_or_raise
from app.core.errors import AdapterUnavailableError
from app.domain.capabilities import Capability
from app.domain.itinerary import BusDetails, OfferAttributes
from app.domain.location import LocationKind, TravelLocation
from app.domain.offer import Money, ProviderOffer, Seller
from app.domain.travel import BusSearchPreferences, SearchRequest, TravelMode
from app.ports.capabilities import SupportsRefundRules
from app.ports.location_search import SupportsLocationSearch
from app.ports.travel_adapter import TravelAdapter

logger = logging.getLogger(__name__)


class MrBilitBusAdapter(
    MrBilitOfferStore,
    TravelAdapter,
    SupportsRefundRules,
    SupportsLocationSearch,
):
    """Verified MrBilit domestic-bus web API integration."""

    def __init__(
        self,
        *,
        timeout_seconds: float = 5.0,
        offer_ttl_seconds: int = 900,
        location_ttl_seconds: int = 86_400,
        max_entries: int = 5_000,
        http_client: MrBilitHttpClient | None = None,
    ) -> None:
        MrBilitOfferStore.__init__(
            self,
            offer_ttl_seconds=offer_ttl_seconds,
            max_entries=max_entries,
        )
        self._http = http_client or MrBilitHttpClient(
            timeout_seconds=timeout_seconds
        )
        self._city_rows = ExpiringLruStore[
            str, tuple[Mapping[str, Any], ...]
        ](
            ttl_seconds=location_ttl_seconds,
            max_entries=1,
        )

    @property
    def mode(self) -> TravelMode:
        return TravelMode.BUS

    @property
    def provider(self) -> str:
        return "mrbilit"

    @property
    def seller(self) -> Seller:
        return MRBILIT_SELLER

    async def search_locations(
        self,
        query: str,
        *,
        limit: int = 10,
    ) -> tuple[TravelLocation, ...]:
        rows = await self._fetch_city_rows()
        needle = normalized_text(query)
        locations: list[TravelLocation] = []
        for row in rows:
            city = self._city(row)
            if city is None:
                continue
            identifier, code, name = city
            searchable = normalized_text(
                f"{identifier} {code} {name} {row.get('englishTitle', '')}"
            )
            if needle and needle not in searchable:
                continue
            locations.append(
                TravelLocation(
                    code=code,
                    name=name,
                    mode=self.mode,
                    kind=LocationKind.BUS_STATION,
                    providers=[self.provider],
                )
            )
        locations.sort(
            key=lambda item: (
                normalized_text(item.name) != needle,
                not normalized_text(item.name).startswith(needle),
                item.name,
            )
        )
        return tuple(locations[: max(1, limit)])

    async def search(self, request: SearchRequest) -> tuple[ProviderOffer, ...]:
        if request.mode is not self.mode:
            raise ValueError("MrBilitBusAdapter only accepts bus searches.")
        if request.return_date is not None:
            raise AdapterUnavailableError(
                "اتوبوس رفت‌وبرگشت مستربلیط باید به‌صورت دو جست‌وجوی "
                "یک‌طرفه انجام شود."
            )
        preferences = (
            request.preferences
            if isinstance(request.preferences, BusSearchPreferences)
            else BusSearchPreferences(mode=TravelMode.BUS)
        )
        rows = await self._fetch_city_rows()
        origin, destination = await asyncio.gather(
            asyncio.to_thread(self._resolve_city, request.origin, rows),
            asyncio.to_thread(self._resolve_city, request.destination, rows),
        )
        if origin[0] == destination[0]:
            raise AdapterUnavailableError("مبدأ و مقصد اتوبوس نمی‌توانند یکسان باشند.")

        payload = {
            "from": origin[0],
            "to": destination[0],
            "date": f"{request.departure_date.isoformat()}T00:00:00.000Z",
            "includeClosed": True,
            "includePromotions": True,
            "loadFromDbOnUnavailability": True,
            "includeUnderDevelopment": False,
        }
        try:
            result_rows = await self._fetch_rows(payload)
        except AdapterUnavailableError:
            raise
        except Exception as exc:  # pragma: no cover - network boundary
            logger.warning("MrBilit bus search failed", exc_info=exc)
            raise AdapterUnavailableError(
                "امکان دریافت اطلاعات اتوبوس از مستربلیط وجود ندارد."
            ) from exc

        offers: list[ProviderOffer] = []
        malformed_rows = 0
        for row in result_rows:
            try:
                offer = self._parse_offer(
                    row,
                    request=request,
                    preferences=preferences,
                    origin=origin,
                    destination=destination,
                )
            except (ValueError, TypeError, OverflowError) as exc:
                malformed_rows += 1
                logger.warning(
                    "Skipping malformed MrBilit bus row",
                    extra={"error_type": type(exc).__name__},
                )
                continue
            if offer is not None:
                self._remember_offer(
                    offer,
                    self._redirect_url(
                        request=request,
                        origin_slug=origin[1],
                        destination_slug=destination[1],
                    ),
                )
                offers.append(offer)
        if result_rows and malformed_rows == len(result_rows):
            raise AdapterUnavailableError(
                "ساختار همهٔ نتایج اتوبوس مستربلیط نامعتبر بود."
            )
        return tuple(offers)

    async def _fetch_city_rows(self) -> tuple[Mapping[str, Any], ...]:
        cached = self._city_rows.get("cities")
        if cached is not None:
            return cached
        response = await self._http.request_json(
            MRBILIT_BUS_LOCATIONS_URL,
            query={
                "getCities": True,
                "groupTerminals": True,
                "domestic": True,
                "includePopular": True,
            },
        )
        if not isinstance(response, list):
            raise AdapterUnavailableError("فهرست شهرهای اتوبوس مستربلیط معتبر نبود.")
        city_rows: list[Mapping[str, Any]] = []
        for province in response:
            if not isinstance(province, Mapping):
                continue
            cities = province.get("cities")
            if not isinstance(cities, list):
                continue
            city_rows.extend(city for city in cities if isinstance(city, Mapping))
        rows = tuple(row for row in city_rows if self._city(row) is not None)
        if not rows:
            raise AdapterUnavailableError("فهرست شهرهای اتوبوس مستربلیط معتبر نبود.")
        self._city_rows.set("cities", rows)
        return rows

    @classmethod
    def _resolve_city(
        cls,
        value: str,
        rows: tuple[Mapping[str, Any], ...],
    ) -> tuple[int, str, str]:
        needle = normalized_text(value)
        matches: dict[int, tuple[int, str, str]] = {}
        for row in rows:
            city = cls._city(row)
            if city is None:
                continue
            identifier, code, name = city
            candidates = {
                normalized_text(str(identifier)),
                normalized_text(code),
                normalized_text(name),
                normalized_text(
                    bounded_text(row.get("englishTitle"), maximum=120)
                ),
            }
            if needle in candidates:
                matches[identifier] = city
        if len(matches) != 1:
            raise AdapterUnavailableError(
                "شناسهٔ شهر این مسیر در فهرست تأییدشدهٔ مستربلیط نیست."
            )
        return next(iter(matches.values()))

    @staticmethod
    def _city(row: Mapping[str, Any]) -> tuple[int, str, str] | None:
        identifier_value = number(row.get("id"))
        code = bounded_text(row.get("code"), maximum=32)
        raw_name = bounded_text(
            row.get("title") or row.get("persianTitle"), maximum=120
        )
        if (
            identifier_value is None
            or not float(identifier_value).is_integer()
            or identifier_value <= 0
            or round(identifier_value) % 10_000 != 0
            or not code
            or not raw_name
        ):
            return None
        name = raw_name.removesuffix(" - همه پایانه‌ها").strip()
        return round(identifier_value), code, name

    async def _fetch_rows(
        self,
        payload: Mapping[str, Any],
    ) -> list[Mapping[str, Any]]:
        response = await self._http.request_json(
            MRBILIT_BUS_SEARCH_URL,
            method="POST",
            payload=payload,
            json_patch=True,
        )
        rows = response.get("buses") if isinstance(response, Mapping) else None
        if not isinstance(rows, list):
            raise AdapterUnavailableError("پاسخ جست‌وجوی اتوبوس مستربلیط معتبر نبود.")
        return mapping_rows_or_raise(
            rows,
            invalid_message="ساختار نتایج اتوبوس مستربلیط نامعتبر بود.",
        )

    def _parse_offer(
        self,
        row: Mapping[str, Any],
        *,
        request: SearchRequest,
        preferences: BusSearchPreferences,
        origin: tuple[int, str, str],
        destination: tuple[int, str, str],
    ) -> ProviderOffer | None:
        source_offer_id = bounded_text(row.get("id"), maximum=20_000)
        departure = parse_datetime(row.get("departureTime"))
        arrival = parse_datetime(row.get("arrivalTime"))
        price_rials = number(row.get("price"))
        capacity = number(row.get("capacity"))
        company = bounded_text(
            row.get("superCorporation") or row.get("corporation"), maximum=100
        )
        company_code = bounded_text(
            row.get("superCorporationID") or row.get("corportaionID"),
            maximum=40,
        ) or None
        bus_class = bounded_text(
            row.get("shortTitle") or row.get("busType"), maximum=80
        )
        origin_terminal = bounded_text(
            row.get("fromTerminal") or row.get("fromName"), maximum=120
        )
        destination_terminal = bounded_text(
            row.get("toTerminal") or row.get("toName"), maximum=120
        )
        if (
            not source_offer_id
            or departure is None
            or (arrival is not None and arrival <= departure)
            or price_rials is None
            or price_rials <= 0
            or capacity is None
            or not float(capacity).is_integer()
            or capacity < 0
            or not company
            or not bus_class
            or not origin_terminal
            or not destination_terminal
        ):
            raise ProviderRowError("required bus fields are missing or invalid")
        if (
            departure.date() != request.departure_date
            or capacity < request.passengers.total
            or row.get("reservable") is not True
            or row.get("isCar") is True
            or not self._matches_city(row.get("fromCity"), origin[2])
            or not self._matches_city(row.get("toCity"), destination[2])
        ):
            return None

        seat_selection = (
            row.get("needsSelectSeat")
            if isinstance(row.get("needsSelectSeat"), bool)
            else None
        )
        if preferences.seat_selection_required and seat_selection is not True:
            return None
        service_number = bounded_text(
            row.get("serviceNo") or row.get("serviceNumber") or row.get("id"),
            maximum=40,
        ) or None
        refund_summary = bounded_text(row.get("penaltyText"), maximum=240) or None
        refundable = True if refund_summary else None
        capabilities = (
            [Capability.REFUND_RULES] if refund_summary is not None else []
        )
        capacity_value = max(1, min(100, round(capacity)))

        return ProviderOffer(
            source_offer_id=source_offer_id,
            origin=origin[2],
            destination=destination[2],
            departure_at=departure,
            arrival_at=arrival,
            price=Money(
                amount=round(
                    (price_rials * request.passengers.total) / 10
                )
            ),
            attributes=OfferAttributes(
                operator=company,
                operator_code=company_code,
                operator_logo_url=bus_operator_logo_url(company),
                service_number=service_number,
                vehicle_class=bus_class,
                stops=0,
            ),
            mode_details=BusDetails(
                mode=TravelMode.BUS,
                origin_terminal=origin_terminal,
                destination_terminal=destination_terminal,
                company=company,
                service_number=service_number,
                bus_class=bus_class,
                seat_selection_available=seat_selection,
                capacity=capacity_value,
                cancellation_policy=refund_summary,
            ),
            capabilities=capabilities,
            remaining_seats=capacity_value,
            cancellation_summary=refund_summary,
            refundable=refundable,
            last_updated_at=datetime.now(TEHRAN_TIMEZONE),
        )

    @staticmethod
    def _matches_city(value: Any, expected: str) -> bool:
        candidate = normalized_text(bounded_text(value, maximum=120))
        target = normalized_text(expected)
        return bool(candidate) and (
            candidate == target or candidate.startswith(f"{target} (")
        )

    @staticmethod
    def _redirect_url(
        *,
        request: SearchRequest,
        origin_slug: str,
        destination_slug: str,
    ) -> str:
        query = urlencode(
            {
                "departureDate": request.departure_date.isoformat(),
                "adultCount": request.passengers.adults,
            }
        )
        return (
            "https://mrbilit.com/buses/"
            f"{quote(origin_slug, safe='')}-{quote(destination_slug, safe='')}?{query}"
        )
