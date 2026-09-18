from __future__ import annotations

import logging
import re
from collections.abc import Mapping
from datetime import datetime
from typing import Any
from urllib.parse import urlencode

from app.adapters.alibaba.http import AlibabaHttpClient
from app.adapters.alibaba.parsing import (
    TEHRAN_TIMEZONE,
    gregorian_to_jalali,
    number,
    parse_datetime,
)
from app.adapters.alibaba.spec import (
    ALIBABA_BUS_AVAILABILITY_URL,
    ALIBABA_BUS_CANCELLATION_URL,
    ALIBABA_BUS_SEATS_URL,
    ALIBABA_BUS_STATIONS,
    ALIBABA_BUS_STATIONS_URL,
    ALIBABA_SELLER,
    AlibabaBusStation,
)
from app.adapters.shared.branding import (
    ALIBABA_LOGO_HOSTS,
    bus_operator_logo_url,
    first_trusted_logo_url,
)
from app.adapters.shared.context import ExpiringLruStore
from app.adapters.shared.parsing import ProviderRowError, mapping_rows_or_raise
from app.core.errors import AdapterUnavailableError, ResourceNotFoundError
from app.domain.capabilities import Capability, RefundRules, Seat, SeatMap
from app.domain.itinerary import BusDetails, OfferAttributes
from app.domain.location import LocationKind, TravelLocation
from app.domain.offer import Money, OfferDetails, ProviderOffer, Seller
from app.domain.travel import BusSearchPreferences, SearchRequest, TravelMode
from app.ports.capabilities import SupportsRefundRules, SupportsSeatSelection
from app.ports.location_search import (
    SupportsCachedLocationSearch,
    SupportsLocationSearch,
)
from app.ports.travel_adapter import TravelAdapter

logger = logging.getLogger(__name__)


def _bounded_text(value: Any, *, maximum: int) -> str:
    text = " ".join(str(value or "").split()).strip()
    if len(text) <= maximum:
        return text
    return text[: maximum - 1].rstrip() + "…"


class AlibabaBusAdapter(
    TravelAdapter,
    SupportsSeatSelection,
    SupportsRefundRules,
    SupportsLocationSearch,
    SupportsCachedLocationSearch,
):
    """Verified Alibaba domestic-bus integration."""

    def __init__(
        self,
        *,
        timeout_seconds: float = 5.0,
        offer_ttl_seconds: int = 900,
        max_entries: int = 5_000,
        http_client: AlibabaHttpClient | None = None,
    ) -> None:
        self._http = http_client or AlibabaHttpClient(timeout_seconds=timeout_seconds)
        self._redirects = ExpiringLruStore[str, str](
            ttl_seconds=offer_ttl_seconds,
            max_entries=max_entries,
        )
        self._details = ExpiringLruStore[str, OfferDetails](
            ttl_seconds=offer_ttl_seconds,
            max_entries=max_entries,
        )
        self._refundable = ExpiringLruStore[str, bool](
            ttl_seconds=offer_ttl_seconds,
            max_entries=max_entries,
        )
        self._stations: dict[str, AlibabaBusStation] = dict(ALIBABA_BUS_STATIONS)

    @property
    def mode(self) -> TravelMode:
        return TravelMode.BUS

    @property
    def provider(self) -> str:
        return "alibaba"

    @property
    def seller(self) -> Seller:
        return ALIBABA_SELLER

    async def search_locations(
        self,
        query: str,
        *,
        limit: int = 10,
    ) -> tuple[TravelLocation, ...]:
        try:
            rows = await self._fetch_station_rows(query)
        except AdapterUnavailableError:
            cached = self._cached_locations(query, limit=limit)
            if cached:
                return cached
            raise
        locations: list[TravelLocation] = []
        for row in rows:
            station = self._parse_station(row)
            if station is None:
                continue
            self._remember_station(station)
            locations.append(
                TravelLocation(
                    code=station.route_code,
                    name=station.name,
                    mode=self.mode,
                    kind=LocationKind.BUS_STATION,
                    popular=bool(row.get("isPopular")),
                    providers=[self.provider],
                )
            )
            if len(locations) >= max(1, limit):
                break
        return tuple(locations)

    def _cached_locations(
        self,
        query: str,
        *,
        limit: int,
    ) -> tuple[TravelLocation, ...]:
        normalized_query = self._normalize_station_text(query)
        unique: dict[str, AlibabaBusStation] = {}
        for station in self._stations.values():
            unique.setdefault(station.domain_code, station)
        matches = [
            station
            for station in unique.values()
            if not normalized_query
            or normalized_query
            in self._normalize_station_text(
                f"{station.name} {station.route_code} {station.domain_code}"
            )
        ]
        matches.sort(key=lambda station: station.name)
        return tuple(
            TravelLocation(
                code=station.route_code,
                name=station.name,
                mode=self.mode,
                kind=LocationKind.BUS_STATION,
                popular=True,
                providers=[self.provider],
            )
            for station in matches[: max(1, limit)]
        )

    def search_cached_locations(
        self,
        query: str,
        *,
        limit: int = 10,
    ) -> tuple[TravelLocation, ...]:
        """Return only stations previously confirmed by Alibaba."""

        return self._cached_locations(query, limit=limit)

    async def search(self, request: SearchRequest) -> tuple[ProviderOffer, ...]:
        if request.mode is not self.mode:
            raise ValueError("AlibabaBusAdapter only accepts bus searches.")
        if request.return_date is not None:
            raise AdapterUnavailableError(
                "مقایسهٔ رفت‌وبرگشت اتوبوس هنوز با قرارداد "
                "تأییدشدهٔ علی‌بابا "
                "پیاده نشده است."
            )
        origin = await self._resolve_station(request.origin)
        destination = await self._resolve_station(request.destination)
        preferences = (
            request.preferences
            if isinstance(request.preferences, BusSearchPreferences)
            else BusSearchPreferences(mode=TravelMode.BUS)
        )
        query = {
            # `orginCityCode` is Alibaba's verified public spelling.
            "orginCityCode": origin.domain_code,
            "destinationCityCode": destination.domain_code,
            "requestDate": request.departure_date.isoformat(),
            "passengerCount": request.passengers.total,
            "serviceType": "Bus",
        }
        try:
            rows = await self._fetch_rows(query)
        except AdapterUnavailableError:
            raise
        except Exception as exc:  # pragma: no cover - network boundary
            logger.warning("Alibaba bus search failed", exc_info=exc)
            raise AdapterUnavailableError(
                "امکان دریافت اطلاعات اتوبوس از علی‌بابا "
                "وجود ندارد."
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
                    "Skipping malformed Alibaba bus row",
                    extra={"error_type": type(exc).__name__},
                )
                continue
            if offer is not None:
                offers.append(offer)
                self._remember_details(offer)
        if rows and malformed_rows == len(rows):
            raise AdapterUnavailableError(
                "ساختار همهٔ نتایج اتوبوس علی‌بابا نامعتبر بود."
            )
        return tuple(offers)

    async def get_details(self, offer_id: str) -> OfferDetails:
        details = self._details.get(offer_id)
        if details is None:
            raise ResourceNotFoundError(
                "جزئیات این اتوبوس در حافظهٔ جست‌وجوی "
                "علی‌بابا "
                "پیدا نشد."
            )
        return details

    async def get_seat_map(self, offer_id: str) -> SeatMap:
        details = await self.get_details(offer_id)
        if Capability.SEAT_SELECTION not in details.capabilities:
            raise AdapterUnavailableError(
                "انتخاب صندلی برای این پیشنهاد فعال نیست."
            )
        response = await self._http.request_json(
            ALIBABA_BUS_SEATS_URL,
            method="POST",
            payload={"proposalId": offer_id},
        )
        if not isinstance(response, Mapping) or response.get("success") is not True:
            raise AdapterUnavailableError(
                "نقشهٔ صندلی علی‌بابا دریافت نشد."
            )
        rows = response.get("result")
        if not isinstance(rows, list):
            raise AdapterUnavailableError(
                "پاسخ نقشهٔ صندلی علی‌بابا معتبر نبود."
            )
        seats: list[Seat] = []
        for row in rows:
            if not isinstance(row, Mapping):
                continue
            seat_number = row.get("number")
            seat_row = number(row.get("row"))
            seat_column = number(row.get("column"))
            status = str(row.get("status") or "").strip()
            if seat_number is None or not status:
                continue
            seats.append(
                Seat(
                    number=str(seat_number),
                    row=(round(seat_row) if seat_row is not None else None),
                    column=(
                        round(seat_column) if seat_column is not None else None
                    ),
                    available=status.casefold() == "available",
                )
            )
        return SeatMap(offer_id=offer_id, seats=seats)

    async def get_refund_rules(self, offer_id: str) -> RefundRules:
        details = await self.get_details(offer_id)
        if Capability.REFUND_RULES not in details.capabilities:
            raise AdapterUnavailableError(
                "قانون استرداد این پیشنهاد تأیید نشده است."
            )
        refundable = self._refundable.get(offer_id)
        if refundable is None:
            raise AdapterUnavailableError(
                "وضعیت استرداد این پیشنهاد مشخص نیست."
            )
        if not refundable:
            return RefundRules(
                offer_id=offer_id,
                refundable=False,
                summary="این بلیت غیرقابل‌استرداد است.",
            )
        response = await self._http.request_json(
            ALIBABA_BUS_CANCELLATION_URL,
            query={"proposalId": offer_id},
        )
        if not isinstance(response, Mapping) or response.get("success") is not True:
            raise AdapterUnavailableError(
                "قانون استرداد علی‌بابا دریافت نشد."
            )
        rows = response.get("result")
        if not isinstance(rows, list):
            raise AdapterUnavailableError(
                "پاسخ قانون استرداد علی‌بابا معتبر نبود."
            )
        summary = "؛ ".join(
            str(item).strip() for item in rows if str(item).strip()
        )
        if not summary:
            summary = (
                "قوانین دقیق استرداد در سایت علی‌بابا "
                "نمایش داده می‌شود."
            )
        return RefundRules(
            offer_id=offer_id,
            refundable=True,
            summary=summary[:500],
        )

    def _station(self, value: str) -> AlibabaBusStation | None:
        key = value.strip().upper() if value.isascii() else value.strip()
        return self._stations.get(key)

    async def _resolve_station(self, value: str) -> AlibabaBusStation:
        cached = self._station(value)
        if cached is not None:
            return cached
        rows = await self._fetch_station_rows(value)
        normalized = self._normalize_station_text(value)
        for row in rows:
            station = self._parse_station(row)
            if station is None:
                continue
            self._remember_station(station)
            if normalized in {
                self._normalize_station_text(station.name),
                station.route_code.casefold(),
                station.domain_code.casefold(),
            }:
                return station
        raise AdapterUnavailableError(
            "شناسهٔ پایانهٔ این شهر از پاسخ زندهٔ علی‌بابا تأیید نشد."
        )

    async def _fetch_station_rows(self, query: str) -> list[Mapping[str, Any]]:
        safe_query = re.sub(r"['{}\\]", "", " ".join(query.split()))
        response = await self._http.request_json(
            ALIBABA_BUS_STATIONS_URL,
            query={"filter": f"q={{ct:'{safe_query}'}}"},
        )
        if not isinstance(response, Mapping) or response.get("success") is not True:
            raise AdapterUnavailableError("فهرست پایانه‌های علی‌بابا دریافت نشد.")
        result = response.get("result")
        rows = result.get("items") if isinstance(result, Mapping) else None
        if not isinstance(rows, list):
            raise AdapterUnavailableError("پاسخ فهرست پایانه‌های علی‌بابا معتبر نبود.")
        return mapping_rows_or_raise(
            rows,
            invalid_message="ساختار فهرست پایانه‌های علی‌بابا نامعتبر بود.",
        )

    @staticmethod
    def _parse_station(row: Mapping[str, Any]) -> AlibabaBusStation | None:
        country = row.get("country")
        if isinstance(country, Mapping) and country.get("domainCode") != "IRN":
            return None
        domain_code = str(row.get("domainCode") or "").strip()
        name = _bounded_text(row.get("name"), maximum=120)
        display_names = row.get("displayNames")
        route_code = ""
        if isinstance(display_names, list):
            for display_name in display_names:
                if not isinstance(display_name, Mapping):
                    continue
                if str(display_name.get("language")) != "en-US":
                    continue
                candidate = str(display_name.get("value") or "").strip().upper()
                if re.fullmatch(r"[A-Z0-9]{2,12}", candidate):
                    route_code = candidate
                    break
        if not domain_code or not name or not route_code:
            return None
        return AlibabaBusStation(
            domain_code=domain_code,
            route_code=route_code,
            name=name,
        )

    @staticmethod
    def _normalize_station_text(value: str) -> str:
        return (
            " ".join(value.split())
            .replace("ي", "ی")
            .replace("ك", "ک")
            .replace("\u200c", "")
            .casefold()
        )

    def _remember_station(self, station: AlibabaBusStation) -> None:
        self._stations[station.name] = station
        self._stations[station.domain_code] = station
        self._stations[station.route_code.upper()] = station

    async def _fetch_rows(self, query: Mapping[str, Any]) -> list[Mapping[str, Any]]:
        response = await self._http.request_json(
            ALIBABA_BUS_AVAILABILITY_URL,
            query=query,
        )
        if not isinstance(response, Mapping) or response.get("success") is not True:
            raise AdapterUnavailableError(
                "جست‌وجوی اتوبوس علی‌بابا ناموفق بود."
            )
        result = response.get("result")
        rows = result.get("availableList") if isinstance(result, Mapping) else None
        if not isinstance(rows, list):
            raise AdapterUnavailableError(
                "پاسخ جست‌وجوی اتوبوس معتبر نبود."
            )
        return mapping_rows_or_raise(
            rows,
            invalid_message="ساختار نتایج اتوبوس علی‌بابا نامعتبر بود.",
        )

    def _parse_offer(
        self,
        row: Mapping[str, Any],
        *,
        request: SearchRequest,
        preferences: BusSearchPreferences,
        origin: AlibabaBusStation,
        destination: AlibabaBusStation,
    ) -> ProviderOffer | None:
        source_offer_id = row.get("proposalId")
        departure = parse_datetime(row.get("departureDateTime"))
        price_rials = number(row.get("price"))
        provider_origin_code = row.get("originCityCode") or row.get("orginCityCode")
        provider_destination_code = row.get("destinationCityCode")
        company = _bounded_text(row.get("companyName"), maximum=100)
        company_code = _bounded_text(row.get("companyCode"), maximum=40) or None
        company_logo_url = bus_operator_logo_url(company) or first_trusted_logo_url(
            row.get("companyLogo"),
            row.get("logoUrl"),
            row.get("logo"),
            allowed_hosts=ALIBABA_LOGO_HOSTS,
        ) or bus_operator_logo_url(company)
        raw_bus_class = _bounded_text(row.get("busType"), maximum=240)
        # Some suppliers append operational notices to busType after a dash.
        # The product field represents the vehicle class, not that notice.
        bus_class = _bounded_text(raw_bus_class.split("-", 1)[0], maximum=80)
        origin_terminal = _bounded_text(row.get("orginTerminal"), maximum=120)
        destination_terminal = _bounded_text(
            row.get("destinationTerminal"),
            maximum=120,
        )
        if (
            not source_offer_id
            or departure is None
            or price_rials is None
            or price_rials < 0
            or not company
            or not bus_class
            or not origin_terminal
            or not destination_terminal
        ):
            raise ProviderRowError("required bus fields are missing or invalid")
        if (
            departure.date() != request.departure_date
            or not self._same_station_code(
                provider_origin_code,
                origin.domain_code,
            )
            or not self._same_station_code(
                provider_destination_code,
                destination.domain_code,
            )
            or (
                "type" in row
                and str(row.get("type") or "").strip().casefold() != "bus"
            )
        ):
            return None

        available_seats = number(row.get("availableSeats"))
        if (
            preferences.seat_selection_required
            and available_seats is not None
            and available_seats < request.passengers.total
        ):
            return None
        source_offer_id = str(source_offer_id)
        refundable = bool(row.get("isRefundable")) if "isRefundable" in row else None
        capabilities = [Capability.SEAT_SELECTION]
        if refundable is not None:
            capabilities.append(Capability.REFUND_RULES)
            self._refundable.set(source_offer_id, refundable)
        cancellation_summary = (
            (
                "قوانین دقیق استرداد در سایت علی‌بابا "
                "نمایش داده می‌شود."
            )
            if refundable is True
            else (
                "این بلیت غیرقابل‌استرداد است."
                if refundable is False
                else None
            )
        )
        service_number = str(row.get("companyCode") or "").strip() or None
        if service_number is not None and len(service_number) > 40:
            service_number = None
        self._remember_redirect(
            source_offer_id,
            request=request,
            origin_code=origin.route_code,
            destination_code=destination.route_code,
        )
        return ProviderOffer(
            source_offer_id=source_offer_id,
            origin=origin.name,
            destination=destination.name,
            departure_at=departure,
            arrival_at=None,
            # Alibaba's live bus response keeps `price` per seat even when
            # passengerCount is greater than one. The normalized contract is
            # the total payable amount for the requested party.
            price=Money(
                amount=round((price_rials * request.passengers.total) / 10)
            ),
            attributes=OfferAttributes(
                operator=company,
                operator_code=company_code,
                operator_logo_url=company_logo_url,
                service_number=service_number,
                vehicle_class=bus_class,
                ticket_type=(
                    "charter" if bool(row.get("isCharter")) else "system"
                ) if "isCharter" in row else None,
                stops=None,
            ),
            mode_details=BusDetails(
                mode=TravelMode.BUS,
                origin_terminal=origin_terminal,
                destination_terminal=destination_terminal,
                company=company,
                service_number=service_number,
                bus_class=bus_class,
                seat_selection_available=True,
                capacity=None,
                cancellation_policy=cancellation_summary,
            ),
            capabilities=capabilities,
            remaining_seats=(
                max(0, round(available_seats))
                if available_seats is not None
                else None
            ),
            cancellation_summary=cancellation_summary,
            refundable=refundable,
            last_updated_at=datetime.now(TEHRAN_TIMEZONE),
        )

    @staticmethod
    def _same_station_code(value: Any, expected: str) -> bool:
        return bool(value) and str(value).strip().casefold() == expected.casefold()

    def _remember_redirect(
        self,
        source_offer_id: str,
        *,
        request: SearchRequest,
        origin_code: str,
        destination_code: str,
    ) -> None:
        query = urlencode(
            {"departing": gregorian_to_jalali(request.departure_date)}
        )
        self._redirects.set(
            source_offer_id,
            f"https://www.alibaba.ir/bus/{origin_code}-{destination_code}?{query}"
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
            raise ResourceNotFoundError(
                "پیوند این پیشنهاد علی‌بابا پیدا نشد."
            )
        return redirect
