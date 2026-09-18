from __future__ import annotations

import logging
import re
from collections.abc import Mapping
from datetime import datetime, time
from typing import Any
from urllib.parse import quote, urlencode

from app.adapters.safar724.base import Safar724OfferStore
from app.adapters.safar724.http import Safar724HttpClient
from app.adapters.safar724.parsing import (
    TEHRAN_TIMEZONE,
    bounded_text,
    normalized_text,
    number,
)
from app.adapters.safar724.spec import (
    SAFAR724_LOCATIONS_URL,
    SAFAR724_LOGO_HOSTS,
    SAFAR724_SEARCH_URL,
    SAFAR724_SELLER,
)
from app.adapters.shared.branding import bus_operator_logo_url, first_trusted_logo_url
from app.adapters.shared.calendar import gregorian_to_jalali
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
_CLOCK_TIME = re.compile(r"^(?P<hour>\d{1,2}):(?P<minute>\d{2})$")


class Safar724BusAdapter(
    Safar724OfferStore,
    TravelAdapter,
    SupportsRefundRules,
    SupportsLocationSearch,
):
    """Verified Safar724 bus inventory integration."""

    def __init__(
        self,
        *,
        timeout_seconds: float = 5.0,
        offer_ttl_seconds: int = 900,
        max_entries: int = 5_000,
        http_client: Safar724HttpClient | None = None,
    ) -> None:
        Safar724OfferStore.__init__(
            self,
            offer_ttl_seconds=offer_ttl_seconds,
            max_entries=max_entries,
        )
        self._http = http_client or Safar724HttpClient(
            timeout_seconds=timeout_seconds
        )
        self._location_rows = ExpiringLruStore[
            str, tuple[Mapping[str, Any], ...]
        ](
            ttl_seconds=offer_ttl_seconds,
            max_entries=1,
        )

    @property
    def mode(self) -> TravelMode:
        return TravelMode.BUS

    @property
    def provider(self) -> str:
        return "safar724"

    @property
    def seller(self) -> Seller:
        return SAFAR724_SELLER

    async def search_locations(
        self,
        query: str,
        *,
        limit: int = 10,
    ) -> tuple[TravelLocation, ...]:
        rows = await self._fetch_location_rows()
        needle = normalized_text(query)
        locations: list[TravelLocation] = []
        for row in rows:
            code = bounded_text(row.get("Code"), maximum=32)
            name = bounded_text(row.get("PersianName"), maximum=120)
            if not code or not name or not self._row_matches(row, needle):
                continue
            locations.append(
                TravelLocation(
                    code=code,
                    name=name,
                    mode=self.mode,
                    kind=LocationKind.BUS_STATION,
                    popular=bool(row.get("IsCapital")),
                    providers=[self.provider],
                )
            )
        locations.sort(
            key=lambda item: (
                normalized_text(item.name) != needle,
                not normalized_text(item.name).startswith(needle),
                not item.popular,
                item.name,
            )
        )
        return tuple(locations[: max(1, limit)])

    async def search(self, request: SearchRequest) -> tuple[ProviderOffer, ...]:
        if request.mode is not self.mode:
            raise ValueError("Safar724BusAdapter only accepts bus searches.")
        if request.return_date is not None:
            raise AdapterUnavailableError(
                "اتوبوس رفت‌وبرگشت سفر ۷۲۴ باید به‌صورت دو جست‌وجوی "
                "یک‌طرفه انجام شود."
            )
        preferences = (
            request.preferences
            if isinstance(request.preferences, BusSearchPreferences)
            else BusSearchPreferences(mode=TravelMode.BUS)
        )
        if preferences.seat_selection_required:
            return ()
        rows = await self._fetch_location_rows()
        origin = self._resolve_location(request.origin, rows)
        destination = self._resolve_location(request.destination, rows)
        if origin[0] == destination[0]:
            raise AdapterUnavailableError("مبدأ و مقصد اتوبوس نمی‌توانند یکسان باشند.")

        jalali_date = gregorian_to_jalali(request.departure_date)
        try:
            response = await self._http.request_json(
                SAFAR724_SEARCH_URL,
                query={
                    "Date": jalali_date,
                    "Destination": destination[0],
                    "Origin": origin[0],
                },
            )
        except AdapterUnavailableError:
            raise
        except Exception as exc:  # pragma: no cover - network boundary
            logger.warning("Safar724 bus search failed", exc_info=exc)
            raise AdapterUnavailableError(
                "امکان دریافت اطلاعات اتوبوس از سفر ۷۲۴ وجود ندارد."
            ) from exc

        if not isinstance(response, Mapping):
            raise AdapterUnavailableError("پاسخ جست‌وجوی اتوبوس سفر ۷۲۴ معتبر نبود.")
        if (
            bounded_text(response.get("originCode"), maximum=32) != origin[0]
            or bounded_text(response.get("destinationCode"), maximum=32)
            != destination[0]
        ):
            raise AdapterUnavailableError("مسیر پاسخ اتوبوس سفر ۷۲۴ معتبر نبود.")
        raw_rows = response.get("items")
        if not isinstance(raw_rows, list):
            raise AdapterUnavailableError("نتایج اتوبوس سفر ۷۲۴ معتبر نبود.")
        provider_rows = mapping_rows_or_raise(
            raw_rows,
            invalid_message="ساختار نتایج اتوبوس سفر ۷۲۴ نامعتبر بود.",
        )
        redirect_url = self._redirect_url(
            origin=origin,
            destination=destination,
            jalali_date=jalali_date,
        )

        offers: list[ProviderOffer] = []
        malformed_rows = 0
        for row in provider_rows:
            try:
                offer = self._parse_offer(
                    row,
                    request=request,
                    origin=origin,
                    destination=destination,
                )
            except (ValueError, TypeError, OverflowError) as exc:
                malformed_rows += 1
                logger.warning(
                    "Skipping malformed Safar724 bus row",
                    extra={"error_type": type(exc).__name__},
                )
                continue
            if offer is None:
                continue
            self._remember_offer(offer, redirect_url)
            offers.append(offer)
        if provider_rows and malformed_rows == len(provider_rows):
            raise AdapterUnavailableError(
                "ساختار همهٔ نتایج اتوبوس سفر ۷۲۴ نامعتبر بود."
            )
        return tuple(offers)

    async def _fetch_location_rows(self) -> tuple[Mapping[str, Any], ...]:
        cached = self._location_rows.get("cities")
        if cached is not None:
            return cached
        response = await self._http.request_json(SAFAR724_LOCATIONS_URL)
        if not isinstance(response, list):
            raise AdapterUnavailableError("فهرست شهرهای سفر ۷۲۴ معتبر نبود.")
        rows = tuple(
            mapping_rows_or_raise(
                response,
                invalid_message="ساختار فهرست شهرهای سفر ۷۲۴ نامعتبر بود.",
            )
        )
        self._location_rows.set("cities", rows)
        return rows

    @classmethod
    def _resolve_location(
        cls,
        value: str,
        rows: tuple[Mapping[str, Any], ...],
    ) -> tuple[str, str, str]:
        needle = normalized_text(value)
        matches: dict[str, tuple[str, str, str]] = {}
        for row in rows:
            code = bounded_text(row.get("Code"), maximum=32)
            english_name = bounded_text(row.get("Name"), maximum=120)
            persian_name = bounded_text(row.get("PersianName"), maximum=120)
            exact = {
                normalized_text(code),
                normalized_text(english_name),
                normalized_text(persian_name),
            }
            if code and english_name and persian_name and needle in exact:
                matches[code] = (code, english_name, persian_name)
        if len(matches) != 1:
            raise AdapterUnavailableError(
                "شناسهٔ شهر این مسیر در فهرست تأییدشدهٔ سفر ۷۲۴ نیست."
            )
        return next(iter(matches.values()))

    def _parse_offer(
        self,
        row: Mapping[str, Any],
        *,
        request: SearchRequest,
        origin: tuple[str, str, str],
        destination: tuple[str, str, str],
    ) -> ProviderOffer | None:
        source_offer_id = bounded_text(row.get("id"), maximum=20_000)
        departure = self._departure_at(
            request.departure_date,
            row.get("departureTime"),
        )
        price_rials = number(row.get("price"))
        available_seats = number(row.get("availableSeatCount"))
        capacity = number(row.get("capacity"))
        company = bounded_text(
            row.get("companyPersianName") or row.get("companyName"),
            maximum=100,
        )
        company_code = bounded_text(row.get("companyCode"), maximum=40) or None
        bus_class = bounded_text(row.get("busType"), maximum=80)
        origin_terminal = bounded_text(
            row.get("originTerminalPersianName"), maximum=120
        )
        destination_terminal = bounded_text(
            row.get("destinationTerminalPersianName"), maximum=120
        )
        if (
            not source_offer_id
            or departure is None
            or price_rials is None
            or price_rials <= 0
            or available_seats is None
            or not float(available_seats).is_integer()
            or not company
            or not bus_class
            or not origin_terminal
            or not destination_terminal
        ):
            raise ProviderRowError("required bus fields are missing or invalid")
        if (
            normalized_text(row.get("vehicleType")) != "bus"
            or normalized_text(row.get("status")) != "available"
            or available_seats < request.passengers.total
        ):
            return None

        cancellation_summary = self._refund_summary(row.get("refundRules"))
        capabilities = (
            [Capability.REFUND_RULES] if cancellation_summary else []
        )
        total_capacity = (
            max(1, min(100, round(capacity)))
            if capacity is not None and float(capacity).is_integer() and capacity > 0
            else None
        )
        return ProviderOffer(
            source_offer_id=source_offer_id,
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
                # Safar724 sometimes returns a syntactically valid URL for a
                # deleted image (for example ``royal-safar-iranian.png``).
                # Prefer the verified provider-owned catalogue for known
                # companies so the browser never receives a guaranteed 404.
                operator_logo_url=bus_operator_logo_url(company) or first_trusted_logo_url(
                    row.get("companyLogo"),
                    allowed_hosts=SAFAR724_LOGO_HOSTS,
                ),
                service_number=source_offer_id[:40],
                vehicle_class=bus_class,
                stops=None,
            ),
            mode_details=BusDetails(
                mode=TravelMode.BUS,
                origin_terminal=origin_terminal,
                destination_terminal=destination_terminal,
                company=company,
                service_number=source_offer_id[:40],
                bus_class=bus_class,
                seat_selection_available=None,
                capacity=total_capacity,
                cancellation_policy=cancellation_summary,
            ),
            capabilities=capabilities,
            remaining_seats=max(0, min(100, round(available_seats))),
            cancellation_summary=cancellation_summary,
            refundable=True if cancellation_summary else None,
            last_updated_at=datetime.now(TEHRAN_TIMEZONE),
        )

    @staticmethod
    def _departure_at(value: Any, clock_value: Any) -> datetime | None:
        if not hasattr(value, "year"):
            return None
        match = _CLOCK_TIME.fullmatch(bounded_text(clock_value, maximum=8))
        if match is None:
            return None
        hour = int(match.group("hour"))
        minute = int(match.group("minute"))
        if hour > 23 or minute > 59:
            return None
        return datetime.combine(
            value,
            time(hour=hour, minute=minute),
            tzinfo=TEHRAN_TIMEZONE,
        )

    @staticmethod
    def _refund_summary(value: Any) -> str | None:
        if not isinstance(value, list):
            return None
        parts: list[str] = []
        for row in value:
            if not isinstance(row, Mapping):
                continue
            message = bounded_text(row.get("message"), maximum=120)
            percent = number(row.get("percent"))
            if not message or percent is None or percent < 0 or percent > 100:
                continue
            parts.append(f"{message}: {percent:g}٪ جریمه")
        return bounded_text("؛ ".join(parts), maximum=240) or None

    @staticmethod
    def _row_matches(row: Mapping[str, Any], needle: str) -> bool:
        if not needle:
            return bool(row.get("IsCapital"))
        values = [
            row.get("Code"),
            row.get("Name"),
            row.get("PersianName"),
            row.get("ProvinceName"),
            row.get("ProvincePersianName"),
        ]
        search_expressions = row.get("SearchExpressions")
        if isinstance(search_expressions, list):
            values.extend(search_expressions)
        return any(needle in normalized_text(value) for value in values)

    @staticmethod
    def _redirect_url(
        *,
        origin: tuple[str, str, str],
        destination: tuple[str, str, str],
        jalali_date: str,
    ) -> str:
        route = (
            f"{quote(origin[1].lower(), safe='-')}-"
            f"{quote(destination[1].lower(), safe='-')}"
        )
        return f"https://safar724.com/bus/{route}?{urlencode({'date': jalali_date})}"
