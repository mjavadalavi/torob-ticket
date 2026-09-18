from __future__ import annotations

import asyncio
import logging
from collections.abc import Mapping
from datetime import datetime
from typing import Any
from urllib.parse import quote, urlencode

from app.adapters.shared.branding import (
    SNAPPTRIP_LOGO_HOSTS,
    bus_operator_logo_url,
    first_trusted_logo_url,
)
from app.adapters.shared.context import ExpiringLruStore
from app.adapters.shared.parsing import ProviderRowError, mapping_rows_or_raise
from app.adapters.snapptrip.http import SnappTripHttpClient
from app.adapters.snapptrip.parsing import (
    TEHRAN_TIMEZONE,
    bounded_text,
    normalized_text,
    number,
    parse_datetime,
)
from app.adapters.snapptrip.spec import (
    SNAPPTRIP_BUS_ALIASES,
    SNAPPTRIP_BUS_AVAILABILITY_URL,
    SNAPPTRIP_BUS_LOCATIONS_URL,
    SNAPPTRIP_SELLER,
)
from app.core.errors import AdapterUnavailableError, ResourceNotFoundError
from app.domain.itinerary import BusDetails, OfferAttributes
from app.domain.location import LocationKind, TravelLocation
from app.domain.offer import Money, OfferDetails, ProviderOffer, Seller
from app.domain.travel import BusSearchPreferences, SearchRequest, TravelMode
from app.ports.location_search import SupportsLocationSearch
from app.ports.travel_adapter import TravelAdapter

logger = logging.getLogger(__name__)


class SnappTripBusAdapter(TravelAdapter, SupportsLocationSearch):
    """Verified SnappTrip domestic-bus web API integration."""

    def __init__(
        self,
        *,
        timeout_seconds: float = 5.0,
        offer_ttl_seconds: int = 900,
        max_entries: int = 5_000,
        http_client: SnappTripHttpClient | None = None,
    ) -> None:
        self._http = http_client or SnappTripHttpClient(timeout_seconds=timeout_seconds)
        self._redirects = ExpiringLruStore[str, str](
            ttl_seconds=offer_ttl_seconds,
            max_entries=max_entries,
        )
        self._details = ExpiringLruStore[str, OfferDetails](
            ttl_seconds=offer_ttl_seconds,
            max_entries=max_entries,
        )

    @property
    def mode(self) -> TravelMode:
        return TravelMode.BUS

    @property
    def provider(self) -> str:
        return "snapptrip"

    @property
    def seller(self) -> Seller:
        return SNAPPTRIP_SELLER

    async def search_locations(
        self,
        query: str,
        *,
        limit: int = 10,
    ) -> tuple[TravelLocation, ...]:
        rows = await self._fetch_location_rows(query)
        locations: list[TravelLocation] = []
        seen: set[str] = set()
        for row in rows:
            code = bounded_text(row.get("code"), maximum=32)
            name = bounded_text(row.get("city") or row.get("name"), maximum=120)
            if not code or not name or code.casefold() in seen:
                continue
            seen.add(code.casefold())
            locations.append(
                TravelLocation(
                    code=code,
                    name=name,
                    mode=self.mode,
                    kind=LocationKind.BUS_STATION,
                    providers=[self.provider],
                )
            )
        locations.sort(key=lambda item: item.name)
        return tuple(locations[: max(1, limit)])

    async def search(self, request: SearchRequest) -> tuple[ProviderOffer, ...]:
        if request.mode is not self.mode:
            raise ValueError("SnappTripBusAdapter only accepts bus searches.")
        if request.return_date is not None:
            raise AdapterUnavailableError(
                "مقایسهٔ رفت‌وبرگشت اتوبوس هنوز با قرارداد تأییدشدهٔ "
                "اسنپ‌تریپ پیاده نشده است."
            )
        preferences = (
            request.preferences
            if isinstance(request.preferences, BusSearchPreferences)
            else BusSearchPreferences(mode=TravelMode.BUS)
        )
        if preferences.seat_selection_required:
            raise AdapterUnavailableError(
                "انتخاب صندلی اتوبوس در قرارداد زندهٔ اسنپ‌تریپ تأیید نشده است."
            )
        origin, destination = await asyncio.gather(
            self._resolve_endpoint(request.origin),
            self._resolve_endpoint(request.destination),
        )
        if origin[0].casefold() == destination[0].casefold():
            raise AdapterUnavailableError("مبدأ و مقصد اتوبوس نمی‌توانند یکسان باشند.")
        try:
            rows = await self._fetch_rows(
                origin[0],
                destination[0],
                request.departure_date.isoformat(),
            )
        except AdapterUnavailableError:
            raise
        except Exception as exc:  # pragma: no cover - network boundary
            logger.warning("SnappTrip bus search failed", exc_info=exc)
            raise AdapterUnavailableError(
                "امکان دریافت اطلاعات اتوبوس از اسنپ‌تریپ وجود ندارد."
            ) from exc

        offers: list[ProviderOffer] = []
        malformed_rows = 0
        for row in rows:
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
                    "Skipping malformed SnappTrip bus row",
                    extra={"error_type": type(exc).__name__},
                )
                continue
            if offer is not None:
                offers.append(offer)
                self._remember_details(offer)
        if rows and malformed_rows == len(rows):
            raise AdapterUnavailableError(
                "ساختار همهٔ نتایج اتوبوس اسنپ‌تریپ نامعتبر بود."
            )
        return tuple(offers)

    async def get_details(self, offer_id: str) -> OfferDetails:
        details = self._details.get(offer_id)
        if details is None:
            raise ResourceNotFoundError(
                "جزئیات این اتوبوس در حافظهٔ جست‌وجوی اسنپ‌تریپ پیدا نشد."
            )
        return details

    async def _fetch_location_rows(self, query: str) -> list[Mapping[str, Any]]:
        response = await self._http.request_json(
            SNAPPTRIP_BUS_LOCATIONS_URL,
            query={"query": query},
        )
        rows = response.get("endpoints") if isinstance(response, Mapping) else None
        if not isinstance(rows, list):
            raise AdapterUnavailableError("فهرست شهرهای اتوبوس اسنپ‌تریپ معتبر نبود.")
        return mapping_rows_or_raise(
            rows,
            invalid_message="ساختار فهرست شهرهای اتوبوس اسنپ‌تریپ نامعتبر بود.",
        )

    async def _resolve_endpoint(self, value: str) -> tuple[str, str]:
        lookup = SNAPPTRIP_BUS_ALIASES.get(value.strip().upper(), value.strip())
        rows = await self._fetch_location_rows(lookup)
        needle = normalized_text(lookup)
        for row in rows:
            code = bounded_text(row.get("code"), maximum=32)
            name = bounded_text(row.get("city") or row.get("name"), maximum=120)
            candidates = {
                normalized_text(code),
                normalized_text(name),
                normalized_text(str(row.get("cityEn") or "")),
            }
            if code and name and needle in candidates:
                return code, name
        raise AdapterUnavailableError(
            "شناسهٔ شهر این مسیر در فهرست تأییدشدهٔ اسنپ‌تریپ نیست."
        )

    async def _fetch_rows(
        self,
        origin_code: str,
        destination_code: str,
        departure_date: str,
    ) -> list[Mapping[str, Any]]:
        url = (
            f"{SNAPPTRIP_BUS_AVAILABILITY_URL}/"
            f"{quote(origin_code, safe='')}/to/"
            f"{quote(destination_code, safe='')}/on/"
            f"{quote(departure_date, safe='')}"
        )
        response = await self._http.request_json(url)
        rows = response.get("solutions") if isinstance(response, Mapping) else None
        if not isinstance(rows, list):
            raise AdapterUnavailableError("پاسخ جست‌وجوی اتوبوس اسنپ‌تریپ معتبر نبود.")
        return mapping_rows_or_raise(
            rows,
            invalid_message="ساختار نتایج اتوبوس اسنپ‌تریپ نامعتبر بود.",
        )

    def _parse_offer(
        self,
        row: Mapping[str, Any],
        *,
        request: SearchRequest,
        preferences: BusSearchPreferences,
        origin: tuple[str, str],
        destination: tuple[str, str],
    ) -> ProviderOffer | None:
        source_offer_id = bounded_text(row.get("id"), maximum=20_000)
        departure = parse_datetime(row.get("departureDatetime"))
        arrival = parse_datetime(row.get("arrivalDatetime"))
        price_rials = number(row.get("finalPrice"))
        if price_rials is None:
            price_rials = number(row.get("price"))
        provider_limit_value = row.get("providerPerOrderLimit")
        provider_limit = number(provider_limit_value)
        provider_departure_date = bounded_text(
            row.get("departureDate"),
            maximum=10,
        )
        provider_origin = bounded_text(row.get("originCity"), maximum=120)
        provider_destination = bounded_text(
            row.get("destinationCity"),
            maximum=120,
        )
        company_value = row.get("company")
        company = bounded_text(
            company_value.get("name")
            if isinstance(company_value, Mapping)
            else None,
            maximum=100,
        )
        company_code = bounded_text(
            company_value.get("id") if isinstance(company_value, Mapping) else None,
            maximum=40,
        ) or None
        company_logo_url = bus_operator_logo_url(company) or first_trusted_logo_url(
            company_value.get("logoUrl")
            if isinstance(company_value, Mapping)
            else None,
            company_value.get("logo")
            if isinstance(company_value, Mapping)
            else None,
            allowed_hosts=SNAPPTRIP_LOGO_HOSTS,
        ) or bus_operator_logo_url(company)
        origin_terminal_value = row.get("originTerminal")
        destination_terminal_value = row.get("destinationTerminal")
        origin_terminal = bounded_text(
            origin_terminal_value.get("name")
            if isinstance(origin_terminal_value, Mapping)
            else None,
            maximum=120,
        )
        destination_terminal = bounded_text(
            destination_terminal_value.get("name")
            if isinstance(destination_terminal_value, Mapping)
            else None,
            maximum=120,
        )
        bus_class = bounded_text(
            row.get("busDescription") or row.get("busType"),
            maximum=80,
        )
        if (
            not source_offer_id
            or departure is None
            or (arrival is not None and arrival <= departure)
            or price_rials is None
            or price_rials < 0
            or not company
            or not origin_terminal
            or not destination_terminal
            or not bus_class
        ):
            raise ProviderRowError("required bus fields are missing or invalid")
        if (
            departure.date() != request.departure_date
            or (
                provider_departure_date
                and provider_departure_date != request.departure_date.isoformat()
            )
            or not self._same_endpoint(provider_origin, origin)
            or not self._same_endpoint(provider_destination, destination)
            or (
                provider_limit_value is not None
                and (
                    provider_limit is None
                    or provider_limit < request.passengers.total
                )
            )
        ) or row.get("multiStop") is True:
            return None

        remaining = number(row.get("capacity"))
        remaining_seats = (
            max(0, min(100, round(remaining))) if remaining is not None else None
        )
        if (
            preferences.seat_selection_required
            and remaining_seats is not None
            and remaining_seats < request.passengers.total
        ):
            return None
        service_number = bounded_text(row.get("serviceId"), maximum=40) or None
        self._remember_redirect(
            source_offer_id,
            request=request,
            origin_code=origin[0],
            destination_code=destination[0],
        )
        return ProviderOffer(
            source_offer_id=source_offer_id,
            origin=bounded_text(row.get("originCity"), maximum=120) or origin[1],
            destination=(
                bounded_text(row.get("destinationCity"), maximum=120)
                or destination[1]
            ),
            departure_at=departure,
            arrival_at=arrival,
            # SnappTrip's bus availability endpoint returns a per-seat fare
            # and has no passenger-count input. Normalize it to the total for
            # the requested party, consistently with both flight adapters.
            price=Money(
                amount=round((price_rials * request.passengers.total) / 10)
            ),
            attributes=OfferAttributes(
                operator=company,
                operator_code=company_code,
                operator_logo_url=company_logo_url,
                service_number=service_number,
                vehicle_class=bus_class,
                stops=None,
            ),
            mode_details=BusDetails(
                mode=TravelMode.BUS,
                origin_terminal=origin_terminal,
                destination_terminal=destination_terminal,
                company=company,
                service_number=service_number,
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
    def _same_endpoint(value: str, endpoint: tuple[str, str]) -> bool:
        normalized = normalized_text(value)
        return bool(normalized) and normalized in {
            normalized_text(endpoint[0]),
            normalized_text(endpoint[1]),
        }

    def _remember_redirect(
        self,
        source_offer_id: str,
        *,
        request: SearchRequest,
        origin_code: str,
        destination_code: str,
    ) -> None:
        query = urlencode(
            {
                "source": "searchBox",
                "departureDate": request.departure_date.isoformat(),
            }
        )
        self._redirects.set(
            source_offer_id,
            (
                f"https://www.snapptrip.com/bus/"
                f"{quote(origin_code, safe='')}/"
                f"{quote(destination_code, safe='')}?{query}"
            ),
        )

    def _remember_details(self, offer: ProviderOffer) -> None:
        self._details.set(
            offer.source_offer_id,
            OfferDetails(
                seller_offer_id=offer.source_offer_id,
                mode=self.mode,
                attributes=offer.attributes,
                mode_details=offer.mode_details,
                capabilities=offer.capabilities,
                remaining_seats=offer.remaining_seats,
                cancellation_summary=offer.cancellation_summary,
                refundable=offer.refundable,
                last_updated_at=offer.last_updated_at,
            ),
        )

    def build_redirect_url(self, source_offer_id: str) -> str:
        redirect = self._redirects.get(source_offer_id)
        if redirect is None:
            raise ResourceNotFoundError("پیوند این پیشنهاد اسنپ‌تریپ پیدا نشد.")
        return redirect
