from __future__ import annotations

import asyncio
import logging
from collections.abc import Mapping
from datetime import datetime
from typing import Any
from urllib.parse import quote, urlencode

from app.adapters.flytoday.base import FlyTodayOfferStore
from app.adapters.flytoday.http import FlyTodayHttpClient
from app.adapters.flytoday.parsing import (
    TEHRAN_TIMEZONE,
    bounded_text,
    normalized_text,
    number,
    parse_datetime,
)
from app.adapters.flytoday.spec import (
    FLYTODAY_BUS_LOCATION_URL,
    FLYTODAY_BUS_SEARCH_URL,
    FLYTODAY_SELLER,
)
from app.adapters.shared.branding import bus_operator_logo_url
from app.adapters.shared.parsing import ProviderRowError, mapping_rows_or_raise
from app.core.errors import AdapterUnavailableError
from app.domain.itinerary import BusDetails, OfferAttributes
from app.domain.location import LocationKind, TravelLocation
from app.domain.offer import Money, ProviderOffer, Seller
from app.domain.travel import BusSearchPreferences, SearchRequest, TravelMode
from app.ports.location_search import SupportsLocationSearch
from app.ports.travel_adapter import TravelAdapter

logger = logging.getLogger(__name__)


class FlyTodayBusAdapter(
    FlyTodayOfferStore,
    TravelAdapter,
    SupportsLocationSearch,
):
    """Verified FlyToday domestic-bus web API integration."""

    def __init__(
        self,
        *,
        timeout_seconds: float = 5.0,
        offer_ttl_seconds: int = 900,
        max_entries: int = 5_000,
        http_client: FlyTodayHttpClient | None = None,
    ) -> None:
        FlyTodayOfferStore.__init__(
            self,
            offer_ttl_seconds=offer_ttl_seconds,
            max_entries=max_entries,
        )
        self._http = http_client or FlyTodayHttpClient(
            timeout_seconds=timeout_seconds
        )

    @property
    def mode(self) -> TravelMode:
        return TravelMode.BUS

    @property
    def provider(self) -> str:
        return "flytoday"

    @property
    def seller(self) -> Seller:
        return FLYTODAY_SELLER

    async def search_locations(
        self,
        query: str,
        *,
        limit: int = 10,
    ) -> tuple[TravelLocation, ...]:
        rows = await self._fetch_location_rows(query)
        needle = normalized_text(query)
        locations: list[TravelLocation] = []
        seen: set[str] = set()
        for row in rows:
            code = bounded_text(row.get("cityId") or row.get("id"), maximum=32)
            name = bounded_text(
                row.get("cityNameFa") or row.get("nameFa"), maximum=120
            )
            searchable = normalized_text(
                f"{code} {name} {row.get('cityName', '')} {row.get('name', '')}"
            )
            if (
                not code
                or not name
                or code in seen
                or (needle and needle not in searchable)
            ):
                continue
            seen.add(code)
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
            raise ValueError("FlyTodayBusAdapter only accepts bus searches.")
        if request.return_date is not None:
            raise AdapterUnavailableError(
                "اتوبوس رفت‌وبرگشت فلای‌تودی باید به‌صورت دو جست‌وجوی "
                "یک‌طرفه انجام شود."
            )
        preferences = (
            request.preferences
            if isinstance(request.preferences, BusSearchPreferences)
            else BusSearchPreferences(mode=TravelMode.BUS)
        )
        if preferences.seat_selection_required:
            return ()
        origin, destination = await asyncio.gather(
            self._resolve_location(request.origin),
            self._resolve_location(request.destination),
        )
        if origin[0] == destination[0]:
            raise AdapterUnavailableError("مبدأ و مقصد اتوبوس نمی‌توانند یکسان باشند.")

        result_url = self._result_url(
            request=request,
            origin=origin,
            destination=destination,
        )
        payload = {
            "originDestinations": [
                {
                    "originId": origin[0],
                    "destinationId": destination[0],
                    "departureDate": request.departure_date.isoformat(),
                }
            ]
        }
        try:
            response = await self._http.request_json(
                FLYTODAY_BUS_SEARCH_URL,
                method="POST",
                payload=payload,
                path=result_url,
            )
        except AdapterUnavailableError:
            raise
        except Exception as exc:  # pragma: no cover - network boundary
            logger.warning("FlyToday bus search failed", exc_info=exc)
            raise AdapterUnavailableError(
                "امکان دریافت اطلاعات اتوبوس از فلای‌تودی وجود ندارد."
            ) from exc

        if not isinstance(response, Mapping):
            raise AdapterUnavailableError("پاسخ جست‌وجوی اتوبوس فلای‌تودی معتبر نبود.")
        raw_legs = response.get("originDestinationItineraries")
        if not isinstance(raw_legs, list):
            raise AdapterUnavailableError("نتایج اتوبوس فلای‌تودی معتبر نبود.")
        legs = mapping_rows_or_raise(
            raw_legs,
            invalid_message="ساختار مسیرهای اتوبوس فلای‌تودی نامعتبر بود.",
        )
        search_id = bounded_text(response.get("searchId"), maximum=80)
        if not search_id:
            raise AdapterUnavailableError("شناسهٔ جست‌وجوی فلای‌تودی معتبر نبود.")

        rows: list[Mapping[str, Any]] = []
        malformed_legs = 0
        for leg in legs:
            if not self._matches_leg(
                leg,
                request=request,
                origin_id=origin[0],
                destination_id=destination[0],
            ):
                malformed_legs += 1
                continue
            itineraries = leg.get("itineraries")
            if not isinstance(itineraries, list):
                malformed_legs += 1
                continue
            rows.extend(
                mapping_rows_or_raise(
                    itineraries,
                    invalid_message=(
                        "ساختار نتایج اتوبوس فلای‌تودی نامعتبر بود."
                    ),
                )
            )
        if legs and malformed_legs == len(legs):
            raise AdapterUnavailableError(
                "هیچ مسیر معتبری در پاسخ اتوبوس فلای‌تودی نبود."
            )

        offers: list[ProviderOffer] = []
        malformed_rows = 0
        for row in rows:
            try:
                offer = self._parse_offer(
                    row,
                    request=request,
                    search_id=search_id,
                    origin=origin,
                    destination=destination,
                )
            except (ValueError, TypeError, OverflowError) as exc:
                malformed_rows += 1
                logger.warning(
                    "Skipping malformed FlyToday bus row",
                    extra={"error_type": type(exc).__name__},
                )
                continue
            if offer is None:
                continue
            self._remember_offer(offer, result_url)
            offers.append(offer)
        if rows and malformed_rows == len(rows):
            raise AdapterUnavailableError(
                "ساختار همهٔ نتایج اتوبوس فلای‌تودی نامعتبر بود."
            )
        return tuple(offers)

    async def _fetch_location_rows(
        self,
        query: str,
    ) -> list[Mapping[str, Any]]:
        response = await self._http.request_json(
            FLYTODAY_BUS_LOCATION_URL,
            method="POST",
            payload={
                "searchTerm": query,
                "pageSize": 100,
                "pageNumber": 0,
            },
            path="https://www.flytodayir.com/bus",
        )
        rows = response.get("locations") if isinstance(response, Mapping) else None
        if not isinstance(rows, list):
            raise AdapterUnavailableError("فهرست شهرهای اتوبوس فلای‌تودی معتبر نبود.")
        return mapping_rows_or_raise(
            rows,
            invalid_message="ساختار فهرست شهرهای اتوبوس فلای‌تودی نامعتبر بود.",
        )

    async def _resolve_location(self, value: str) -> tuple[str, str, str]:
        rows = await self._fetch_location_rows(value)
        needle = normalized_text(value)
        matches: dict[str, tuple[str, str, str]] = {}
        for row in rows:
            city_id = bounded_text(row.get("cityId") or row.get("id"), maximum=32)
            slug = bounded_text(
                row.get("cityName") or row.get("name"), maximum=120
            )
            name = bounded_text(
                row.get("cityNameFa") or row.get("nameFa"), maximum=120
            )
            candidates = {
                normalized_text(city_id),
                normalized_text(slug),
                normalized_text(name),
                normalized_text(row.get("id")),
                normalized_text(row.get("name")),
                normalized_text(row.get("nameFa")),
            }
            if city_id and slug and name and needle in candidates:
                matches[city_id] = (city_id, slug, name)
        if len(matches) != 1:
            raise AdapterUnavailableError(
                "شناسهٔ شهر این مسیر در فهرست تأییدشدهٔ فلای‌تودی نیست."
            )
        return next(iter(matches.values()))

    def _parse_offer(
        self,
        row: Mapping[str, Any],
        *,
        request: SearchRequest,
        search_id: str,
        origin: tuple[str, str, str],
        destination: tuple[str, str, str],
    ) -> ProviderOffer | None:
        source = bounded_text(row.get("fareSourceCode"), maximum=20_000)
        departure = parse_datetime(row.get("departureDate"))
        price_rials = number(row.get("price"))
        remaining = number(row.get("remainingSeat"))
        row_origin = row.get("origin")
        row_destination = row.get("destination")
        if not isinstance(row_origin, Mapping) or not isinstance(
            row_destination, Mapping
        ):
            raise ProviderRowError("bus endpoints are missing")
        row_origin_city_id = bounded_text(row_origin.get("cityId"), maximum=32)
        row_destination_city_id = bounded_text(
            row_destination.get("cityId"), maximum=32
        )
        company = bounded_text(
            row.get("busGroupCompanyNameFa")
            or row.get("busCompanyNameFa")
            or row.get("name"),
            maximum=100,
        )
        company_code = bounded_text(
            row.get("busGroupCompanyCode") or row.get("busCompanyId"),
            maximum=40,
        ) or None
        bus_class = bounded_text(row.get("busType"), maximum=80)
        origin_terminal = bounded_text(
            row_origin.get("terminalNameFa") or row_origin.get("nameFa"),
            maximum=120,
        )
        destination_terminal = bounded_text(
            row_destination.get("terminalNameFa")
            or row_destination.get("nameFa"),
            maximum=120,
        )
        if (
            not source
            or departure is None
            or departure.date() != request.departure_date
            or price_rials is None
            or price_rials <= 0
            or remaining is None
            or not float(remaining).is_integer()
            or row_origin_city_id != origin[0]
            or row_destination_city_id != destination[0]
            or not company
            or not bus_class
            or not origin_terminal
            or not destination_terminal
        ):
            raise ProviderRowError("required bus fields are missing or invalid")
        if row.get("isFull") is True or remaining < request.passengers.total:
            return None

        remaining_seats = max(0, min(100, round(remaining)))
        return ProviderOffer(
            source_offer_id=f"{search_id}:{source}",
            origin=origin[2],
            destination=destination[2],
            departure_at=departure,
            arrival_at=None,
            price=Money(
                amount=round(
                    (price_rials * request.passengers.total) / 10
                )
            ),
            attributes=OfferAttributes(
                operator=company,
                operator_code=company_code,
                operator_logo_url=bus_operator_logo_url(company),
                service_number=None,
                vehicle_class=bus_class,
                stops=None,
            ),
            mode_details=BusDetails(
                mode=TravelMode.BUS,
                origin_terminal=origin_terminal,
                destination_terminal=destination_terminal,
                company=company,
                service_number=None,
                bus_class=bus_class,
                seat_selection_available=None,
                capacity=None,
                cancellation_policy=None,
            ),
            capabilities=[],
            remaining_seats=remaining_seats,
            cancellation_summary=None,
            refundable=None,
            last_updated_at=datetime.now(TEHRAN_TIMEZONE),
        )

    @staticmethod
    def _matches_leg(
        leg: Mapping[str, Any],
        *,
        request: SearchRequest,
        origin_id: str,
        destination_id: str,
    ) -> bool:
        origin = leg.get("origin")
        destination = leg.get("destination")
        departure = parse_datetime(leg.get("departureDate"))
        return (
            isinstance(origin, Mapping)
            and isinstance(destination, Mapping)
            and bounded_text(origin.get("cityId"), maximum=32) == origin_id
            and bounded_text(destination.get("cityId"), maximum=32)
            == destination_id
            and departure is not None
            and departure.date() == request.departure_date
        )

    @staticmethod
    def _result_url(
        *,
        request: SearchRequest,
        origin: tuple[str, str, str],
        destination: tuple[str, str, str],
    ) -> str:
        route = (
            f"{quote(origin[1].lower(), safe='-')}-"
            f"{quote(destination[1].lower(), safe='-')}"
        )
        query = urlencode(
            {
                "origin": origin[0],
                "destination": destination[0],
                "departureDate": request.departure_date.isoformat(),
            }
        )
        return f"https://www.flytodayir.com/bus/{route}?{query}"
