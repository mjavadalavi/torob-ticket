from __future__ import annotations

import logging
from collections.abc import Mapping
from datetime import datetime, time
from typing import Any
from urllib.parse import quote, urlencode, urljoin

from app.adapters.payaneha.base import PayanehaOfferStore
from app.adapters.payaneha.http import PayanehaHttpClient
from app.adapters.payaneha.parsing import (
    TEHRAN_TIMEZONE,
    PayanehaResultParser,
    bounded_text,
    normalized_text,
    number,
    parse_clock,
    parse_price,
)
from app.adapters.payaneha.spec import (
    PAYANEHA_DESTINATIONS_URL,
    PAYANEHA_LOGO_HOSTS,
    PAYANEHA_ORIGINS_URL,
    PAYANEHA_SEARCH_URL,
    PAYANEHA_SELLER,
)
from app.adapters.shared.branding import bus_operator_logo_url, first_trusted_logo_url
from app.adapters.shared.calendar import gregorian_to_jalali
from app.adapters.shared.context import ExpiringLruStore
from app.adapters.shared.parsing import ProviderRowError, mapping_rows_or_raise
from app.core.errors import AdapterUnavailableError
from app.domain.itinerary import BusDetails, OfferAttributes
from app.domain.location import LocationKind, TravelLocation
from app.domain.offer import Money, ProviderOffer, Seller
from app.domain.travel import BusSearchPreferences, SearchRequest, TravelMode
from app.ports.location_search import SupportsLocationSearch
from app.ports.travel_adapter import TravelAdapter

logger = logging.getLogger(__name__)


class PayanehaBusAdapter(PayanehaOfferStore, TravelAdapter, SupportsLocationSearch):
    """Verified Payaneha HTML bus inventory integration."""

    def __init__(
        self,
        *,
        timeout_seconds: float = 5.0,
        offer_ttl_seconds: int = 900,
        max_entries: int = 5_000,
        http_client: PayanehaHttpClient | None = None,
    ) -> None:
        PayanehaOfferStore.__init__(
            self, offer_ttl_seconds=offer_ttl_seconds, max_entries=max_entries
        )
        self._http = http_client or PayanehaHttpClient(timeout_seconds=timeout_seconds)
        self._origins = ExpiringLruStore[str, tuple[Mapping[str, Any], ...]](
            ttl_seconds=offer_ttl_seconds, max_entries=1
        )
        self._destinations = ExpiringLruStore[str, tuple[Mapping[str, Any], ...]](
            ttl_seconds=offer_ttl_seconds, max_entries=128
        )

    @property
    def mode(self) -> TravelMode:
        return TravelMode.BUS

    @property
    def provider(self) -> str:
        return "payaneha"

    @property
    def seller(self) -> Seller:
        return PAYANEHA_SELLER

    async def search_locations(
        self, query: str, *, limit: int = 10
    ) -> tuple[TravelLocation, ...]:
        rows = await self._fetch_origins()
        needle = normalized_text(query)
        locations: list[TravelLocation] = []
        for row in rows:
            name = bounded_text(row.get("CityName"), maximum=120)
            code = bounded_text(row.get("CityCode") or name, maximum=120)
            if not name or (needle and needle not in normalized_text(f"{name} {code}")):
                continue
            locations.append(
                TravelLocation(
                    code=code,
                    name=name,
                    mode=self.mode,
                    kind=LocationKind.BUS_STATION,
                    popular=False,
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
            raise ValueError("PayanehaBusAdapter only accepts bus searches.")
        if request.return_date is not None:
            raise AdapterUnavailableError(
                "اتوبوس رفت‌وبرگشت پایانه‌ها باید به‌صورت دو جست‌وجوی یک‌طرفه انجام شود."
            )
        preferences = (
            request.preferences
            if isinstance(request.preferences, BusSearchPreferences)
            else BusSearchPreferences(mode=TravelMode.BUS)
        )
        if preferences.seat_selection_required:
            return ()
        origins = await self._fetch_origins()
        origin = self._resolve_city(request.origin, origins)
        destinations = await self._fetch_destinations(origin[0])
        destination = self._resolve_city(request.destination, destinations)
        if origin[0] == destination[0]:
            raise AdapterUnavailableError("مبدأ و مقصد اتوبوس نمی‌توانند یکسان باشند.")
        jalali_date = gregorian_to_jalali(request.departure_date).replace("-", "/")
        try:
            html = await self._http.request_text(
                PAYANEHA_SEARCH_URL,
                query={"origin": origin[1], "dest": destination[1], "datemove": jalali_date},
            )
        except AdapterUnavailableError:
            raise
        except Exception as exc:  # pragma: no cover - network boundary
            logger.warning("Payaneha bus search failed", exc_info=exc)
            raise AdapterUnavailableError("امکان دریافت اطلاعات اتوبوس از پایانه‌ها وجود ندارد.") from exc
        parser = PayanehaResultParser()
        parser.feed(html)
        parser.close()
        if not parser.rows and "result_wrapper" in html:
            raise AdapterUnavailableError("ساختار نتایج اتوبوس پایانه‌ها نامعتبر بود.")
        redirect_url = self._redirect_url(origin=origin, destination=destination, jalali_date=jalali_date)
        offers: list[ProviderOffer] = []
        malformed_rows = 0
        for row in parser.rows:
            try:
                offer = self._parse_offer(row, request=request, origin=origin, destination=destination)
            except (ProviderRowError, ValueError, TypeError, OverflowError) as exc:
                malformed_rows += 1
                logger.warning("Skipping malformed Payaneha bus row", extra={"error_type": type(exc).__name__})
                continue
            if offer is None:
                continue
            self._remember_offer(offer, redirect_url)
            offers.append(offer)
        if parser.rows and malformed_rows == len(parser.rows):
            raise AdapterUnavailableError("ساختار همهٔ نتایج اتوبوس پایانه‌ها نامعتبر بود.")
        return tuple(offers)

    async def _fetch_origins(self) -> tuple[Mapping[str, Any], ...]:
        cached = self._origins.get("cities")
        if cached is not None:
            return cached
        response = await self._http.request_json(PAYANEHA_ORIGINS_URL)
        if not isinstance(response, list):
            raise AdapterUnavailableError("فهرست شهرهای مبدأ پایانه‌ها معتبر نبود.")
        rows = tuple(mapping_rows_or_raise(response, invalid_message="ساختار شهرهای مبدأ پایانه‌ها نامعتبر بود."))
        self._origins.set("cities", rows)
        return rows

    async def _fetch_destinations(self, origin: str) -> tuple[Mapping[str, Any], ...]:
        cached = self._destinations.get(origin)
        if cached is not None:
            return cached
        response = await self._http.request_json(
            PAYANEHA_DESTINATIONS_URL, query={"Origin": origin}
        )
        if not isinstance(response, list):
            raise AdapterUnavailableError("فهرست شهرهای مقصد پایانه‌ها معتبر نبود.")
        rows = tuple(mapping_rows_or_raise(response, invalid_message="ساختار شهرهای مقصد پایانه‌ها نامعتبر بود."))
        self._destinations.set(origin, rows)
        return rows

    @staticmethod
    def _resolve_city(value: str, rows: tuple[Mapping[str, Any], ...]) -> tuple[str, str]:
        needle = normalized_text(value)
        matches: dict[str, tuple[str, str]] = {}
        for row in rows:
            name = bounded_text(row.get("CityName"), maximum=120)
            code = bounded_text(row.get("CityCode") or name, maximum=120)
            if name and code and needle in {normalized_text(name), normalized_text(code)}:
                matches[code] = (name, code)
        if len(matches) != 1:
            raise AdapterUnavailableError("شهر این مسیر در فهرست تأییدشدهٔ پایانه‌ها پیدا نشد.")
        return next(iter(matches.values()))

    def _parse_offer(
        self,
        row: Mapping[str, Any],
        *,
        request: SearchRequest,
        origin: tuple[str, str],
        destination: tuple[str, str],
    ) -> ProviderOffer | None:
        source_id = bounded_text(row.get("id"), maximum=20_000)
        company = bounded_text(row.get("company_short") or row.get("company"), maximum=100)
        bus_type = bounded_text(row.get("bus_type"), maximum=80)
        origin_terminal = bounded_text(row.get("origin_terminal"), maximum=120)
        destination_terminal = self._destination_terminal(row.get("route"), destination[0])
        clock = parse_clock(row.get("time"))
        price_rials = parse_price(row.get("price"))
        capacity = number(row.get("capacity"))
        if not source_id or not company or not bus_type or not origin_terminal or not destination_terminal or clock is None or price_rials is None or price_rials <= 0 or capacity is None or not float(capacity).is_integer():
            raise ProviderRowError("required bus fields are missing or invalid")
        if capacity < request.passengers.total:
            return None
        departure = datetime.combine(request.departure_date, time(*clock), tzinfo=TEHRAN_TIMEZONE)
        logo = row.get("logo")
        if isinstance(logo, str):
            logo = urljoin("https://www.payaneha.com/busticket/", logo)
        available = round(capacity)
        return ProviderOffer(
            source_offer_id=source_id,
            origin=origin[0],
            destination=destination[0],
            departure_at=departure,
            price=Money(amount=round((price_rials * request.passengers.total) / 10)),
            attributes=OfferAttributes(
                operator=company,
                operator_logo_url=bus_operator_logo_url(company) or first_trusted_logo_url(
                    logo,
                    allowed_hosts=PAYANEHA_LOGO_HOSTS,
                ),
                service_number=source_id[:40],
                vehicle_class=bus_type,
            ),
            mode_details=BusDetails(
                mode=TravelMode.BUS,
                origin_terminal=origin_terminal,
                destination_terminal=destination_terminal,
                company=company,
                service_number=source_id[:40],
                bus_class=bus_type,
                seat_selection_available=None,
                capacity=None,
                cancellation_policy=None,
            ),
            capabilities=[],
            remaining_seats=available,
            last_updated_at=datetime.now(TEHRAN_TIMEZONE),
        )

    @staticmethod
    def _destination_terminal(value: Any, destination: str) -> str:
        text = bounded_text(value, maximum=300)
        match = text.split("مقصدنهایی", 1)
        if len(match) == 2:
            suffix = match[1].lstrip(" :：")
            if suffix:
                return bounded_text(suffix, maximum=120)
        return ""

    @staticmethod
    def _redirect_url(*, origin: tuple[str, str], destination: tuple[str, str], jalali_date: str) -> str:
        slug = f"خرید-بلیط-اتوبوس-از-{origin[0]}-به-{destination[0]}"
        return f"https://www.payaneha.com/busticket/search/{quote(slug, safe='') }?{urlencode({'date': jalali_date})}"
