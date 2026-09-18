from __future__ import annotations

import logging
import re
from collections.abc import Mapping
from datetime import datetime, timedelta
from typing import Any
from urllib.parse import quote, urlencode

from app.adapters.shared.branding import (
    SNAPPTRIP_TRAIN_LOGO_HOSTS,
    train_operator_logo_url,
    trusted_logo_url,
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
    SNAPPTRIP_SELLER,
    SNAPPTRIP_TRAIN_ALIASES,
    SNAPPTRIP_TRAIN_SEARCH_URL,
    SNAPPTRIP_TRAIN_STATIONS_URL,
)
from app.core.errors import AdapterUnavailableError, ResourceNotFoundError
from app.domain.itinerary import OfferAttributes, TrainDetails
from app.domain.location import LocationKind, TravelLocation
from app.domain.offer import Money, OfferDetails, ProviderOffer, Seller
from app.domain.travel import SearchRequest, TrainSearchPreferences, TravelMode
from app.ports.location_search import SupportsLocationSearch
from app.ports.travel_adapter import TravelAdapter

logger = logging.getLogger(__name__)

_LOGO_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")
_CLOCK = re.compile(r"^(?P<hour>[01]\d|2[0-3]):(?P<minute>[0-5]\d)$")


class SnappTripTrainAdapter(TravelAdapter, SupportsLocationSearch):
    """Verified SnappTrip domestic-train web API integration."""

    def __init__(
        self,
        *,
        timeout_seconds: float = 5.0,
        offer_ttl_seconds: int = 900,
        station_ttl_seconds: int = 86_400,
        max_entries: int = 5_000,
        http_client: SnappTripHttpClient | None = None,
    ) -> None:
        self._http = http_client or SnappTripHttpClient(
            timeout_seconds=timeout_seconds
        )
        self._redirects = ExpiringLruStore[str, str](
            ttl_seconds=offer_ttl_seconds,
            max_entries=max_entries,
        )
        self._details = ExpiringLruStore[str, OfferDetails](
            ttl_seconds=offer_ttl_seconds,
            max_entries=max_entries,
        )
        self._station_rows = ExpiringLruStore[
            str, tuple[Mapping[str, Any], ...]
        ](
            ttl_seconds=station_ttl_seconds,
            max_entries=1,
        )

    @property
    def mode(self) -> TravelMode:
        return TravelMode.TRAIN

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
        rows = await self._fetch_station_rows()
        needle = normalized_text(query)
        locations: list[TravelLocation] = []
        seen_endpoints: set[str] = set()
        for row in rows:
            endpoint = self._station_endpoint(row)
            name = self._station_display_name(row)
            if endpoint is None or not name:
                continue
            searchable = normalized_text(
                f"{row.get('code', '')} {name} {endpoint}"
            )
            if needle and needle not in searchable:
                continue
            endpoint_key = endpoint.casefold()
            if endpoint_key in seen_endpoints:
                continue
            seen_endpoints.add(endpoint_key)
            locations.append(
                TravelLocation(
                    code=endpoint,
                    name=name,
                    mode=self.mode,
                    kind=LocationKind.RAILWAY_STATION,
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
            raise ValueError("SnappTripTrainAdapter only accepts train searches.")
        if request.return_date is not None:
            raise AdapterUnavailableError(
                "مقایسهٔ رفت‌وبرگشت قطار باید به‌صورت دو جست‌وجوی "
                "یک‌طرفه از اسنپ‌تریپ انجام شود."
            )
        preferences = (
            request.preferences
            if isinstance(request.preferences, TrainSearchPreferences)
            else TrainSearchPreferences(mode=TravelMode.TRAIN)
        )
        if preferences.vehicle_transport:
            raise AdapterUnavailableError(
                "حمل خودرو در قرارداد زندهٔ قطار اسنپ‌تریپ تأیید نشده است."
            )
        if preferences.passenger_type != "family":
            raise AdapterUnavailableError(
                "فروش ویژهٔ بانوان یا آقایان در قرارداد زندهٔ قطار "
                "اسنپ‌تریپ تأیید نشده است."
            )

        station_rows = await self._fetch_station_rows()
        origin = self._resolve_station(request.origin, station_rows)
        destination = self._resolve_station(request.destination, station_rows)
        if origin[0].casefold() == destination[0].casefold():
            raise AdapterUnavailableError("مبدأ و مقصد قطار نمی‌توانند یکسان باشند.")
        payload = {
            "ticketType": "NORMAL",
            "adultCount": request.passengers.adults,
            "childCount": request.passengers.children,
            "infantCount": request.passengers.infants,
            "origin": origin[0],
            "destination": destination[0],
            "moveDate": request.departure_date.isoformat(),
            "isExclusive": preferences.exclusive_compartment,
        }
        try:
            rows = await self._fetch_rows(payload)
        except AdapterUnavailableError:
            raise
        except Exception as exc:  # pragma: no cover - network boundary
            logger.warning("SnappTrip train search failed", exc_info=exc)
            raise AdapterUnavailableError(
                "امکان دریافت اطلاعات قطار از اسنپ‌تریپ وجود ندارد."
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
                    "Skipping malformed SnappTrip train row",
                    extra={"error_type": type(exc).__name__},
                )
                continue
            if offer is not None:
                offers.append(offer)
                self._remember_details(offer)
        if rows and malformed_rows == len(rows):
            raise AdapterUnavailableError(
                "ساختار همهٔ نتایج قطار اسنپ‌تریپ نامعتبر بود."
            )
        return tuple(offers)

    async def get_details(self, offer_id: str) -> OfferDetails:
        details = self._details.get(offer_id)
        if details is None:
            raise ResourceNotFoundError(
                "جزئیات این قطار در حافظهٔ جست‌وجوی اسنپ‌تریپ پیدا نشد."
            )
        return details

    async def _fetch_station_rows(self) -> tuple[Mapping[str, Any], ...]:
        cached = self._station_rows.get("stations")
        if cached is not None:
            return cached
        response = await self._http.request_json(SNAPPTRIP_TRAIN_STATIONS_URL)
        if not isinstance(response, list):
            raise AdapterUnavailableError("فهرست ایستگاه‌های اسنپ‌تریپ معتبر نبود.")
        rows = tuple(
            row
            for row in mapping_rows_or_raise(
                response,
                invalid_message="ساختار فهرست ایستگاه‌های اسنپ‌تریپ نامعتبر بود.",
            )
            if row.get("isActive") is True
            and self._station_endpoint(row) is not None
            and bool(self._station_display_name(row))
            and self._station_code(row) is not None
        )
        if not rows:
            raise AdapterUnavailableError("فهرست ایستگاه‌های اسنپ‌تریپ معتبر نبود.")
        self._station_rows.set("stations", rows)
        return rows

    async def _fetch_rows(
        self,
        payload: Mapping[str, Any],
    ) -> list[Mapping[str, Any]]:
        response = await self._http.request_json(
            SNAPPTRIP_TRAIN_SEARCH_URL,
            method="POST",
            payload=payload,
        )
        envelope = response.get("solutions") if isinstance(response, Mapping) else None
        rows = envelope.get("solutions") if isinstance(envelope, Mapping) else None
        response_code = (
            number(envelope.get("responseCode"))
            if isinstance(envelope, Mapping)
            else None
        )
        if response_code != 200 or not isinstance(rows, list):
            raise AdapterUnavailableError("پاسخ جست‌وجوی قطار اسنپ‌تریپ معتبر نبود.")
        return mapping_rows_or_raise(
            rows,
            invalid_message="ساختار نتایج قطار اسنپ‌تریپ نامعتبر بود.",
        )

    def _resolve_station(
        self,
        value: str,
        rows: tuple[Mapping[str, Any], ...],
    ) -> tuple[str, str, str]:
        lookup = SNAPPTRIP_TRAIN_ALIASES.get(value.strip().upper(), value.strip())
        needle = normalized_text(lookup)
        matches: list[tuple[str, str, str]] = []
        for row in rows:
            endpoint = self._station_endpoint(row)
            name = self._station_display_name(row)
            code = self._station_code(row)
            candidates = {
                normalized_text(endpoint or ""),
                normalized_text(name),
                normalized_text(code or ""),
            }
            if endpoint and name and code and needle in candidates:
                matches.append((endpoint, name, code))
        unique = {match[0].casefold(): match for match in matches}
        if len(unique) != 1:
            raise AdapterUnavailableError(
                "شناسهٔ ایستگاه این مسیر در فهرست تأییدشدهٔ "
                "اسنپ‌تریپ نیست."
            )
        return next(iter(unique.values()))

    def _parse_offer(
        self,
        row: Mapping[str, Any],
        *,
        request: SearchRequest,
        preferences: TrainSearchPreferences,
        origin: tuple[str, str, str],
        destination: tuple[str, str, str],
    ) -> ProviderOffer | None:
        source_offer_id = bounded_text(row.get("id"), maximum=20_000)
        departure = parse_datetime(row.get("departureDateTime"))
        duration_value = number(row.get("duration"))
        seats_value = number(row.get("seatsRemaining"))
        pricing = row.get("pricing")
        price_rials = (
            number(pricing.get("totalPayablePrice"))
            if isinstance(pricing, Mapping)
            else None
        )
        provider_origin = bounded_text(row.get("origin"), maximum=32)
        provider_destination = bounded_text(row.get("destination"), maximum=32)
        origin_name = self._persian_text(
            bounded_text(row.get("originName"), maximum=120)
        )
        destination_name = self._persian_text(
            bounded_text(row.get("destinationName"), maximum=120)
        )
        company = self._persian_text(
            bounded_text(row.get("trainCompany"), maximum=100)
        )
        company_code = bounded_text(
            row.get("supplierCode") or row.get("businessProvider"), maximum=40
        ) or None
        train_number = bounded_text(row.get("trainNumber"), maximum=20)
        wagon_name = self._persian_text(
            bounded_text(row.get("wagonName"), maximum=80)
        )
        ticket_type = bounded_text(row.get("ticketType"), maximum=40).upper()
        capacity_status = bounded_text(
            row.get("capacityStatus"), maximum=40
        ).upper()
        exclusive_value = row.get("exclusible")
        if (
            not source_offer_id
            or departure is None
            or duration_value is None
            or not float(duration_value).is_integer()
            or duration_value <= 0
            or duration_value > 10_080
            or seats_value is None
            or not float(seats_value).is_integer()
            or seats_value < 0
            or price_rials is None
            or price_rials < 0
            or not provider_origin
            or not provider_destination
            or not origin_name
            or not destination_name
            or not company
            or not train_number
            or not wagon_name
            or ticket_type != "NORMAL"
            or not isinstance(exclusive_value, bool)
        ):
            raise ProviderRowError("required train fields are missing or invalid")

        if capacity_status not in {"AVAILABLE", "UNAVAILABLE"}:
            raise ProviderRowError("train capacity status is invalid")
        remaining_seats = round(seats_value)
        if capacity_status != "AVAILABLE" or remaining_seats < request.passengers.total:
            return None
        if (
            departure.date() != request.departure_date
            or provider_origin.casefold() != origin[2].casefold()
            or provider_destination.casefold() != destination[2].casefold()
            or normalized_text(origin_name) != normalized_text(origin[1])
            or normalized_text(destination_name) != normalized_text(destination[1])
            or exclusive_value is not preferences.exclusive_compartment
        ):
            return None

        duration_minutes = round(duration_value)
        arrival = departure + timedelta(minutes=duration_minutes)
        self._verify_arrival_time(arrival, row.get("arrivalTime"))
        compartment_value = number(row.get("compartmentCapacity"))
        compartment_capacity = None
        if compartment_value is not None:
            if (
                not float(compartment_value).is_integer()
                or compartment_value < 1
                or compartment_value > 12
            ):
                raise ProviderRowError("train compartment capacity is invalid")
            compartment_capacity = round(compartment_value)

        logo_url = self._operator_logo_url(row.get("logoName")) or train_operator_logo_url(company)
        self._remember_redirect(
            source_offer_id,
            request=request,
            preferences=preferences,
            origin_endpoint=origin[0],
            destination_endpoint=destination[0],
        )
        return ProviderOffer(
            source_offer_id=source_offer_id,
            origin=origin[1],
            destination=destination[1],
            departure_at=departure,
            arrival_at=arrival,
            price=Money(amount=round(price_rials / 10)),
            attributes=OfferAttributes(
                operator=company,
                operator_code=company_code,
                operator_logo_url=logo_url,
                service_number=train_number,
                vehicle_class=wagon_name,
                ticket_type="normal",
                stops=0,
            ),
            mode_details=TrainDetails(
                mode=TravelMode.TRAIN,
                railway_company=company,
                train_number=train_number,
                class_name=wagon_name,
                compartment_capacity=compartment_capacity,
                private_compartment_available=(
                    True if preferences.exclusive_compartment else None
                ),
                women_only_available=None,
                vehicle_transport_available=None,
            ),
            capabilities=[],
            remaining_seats=remaining_seats,
            cancellation_summary=None,
            refundable=None,
            last_updated_at=datetime.now(TEHRAN_TIMEZONE),
        )

    @staticmethod
    def _station_endpoint(row: Mapping[str, Any]) -> str | None:
        endpoint = bounded_text(row.get("nameEn"), maximum=32)
        return endpoint if endpoint and endpoint.isascii() else None

    @staticmethod
    def _station_code(row: Mapping[str, Any]) -> str | None:
        raw = row.get("code")
        if isinstance(raw, bool):
            return None
        code = bounded_text(raw, maximum=32)
        return code if code and code.isdigit() else None

    @classmethod
    def _station_display_name(cls, row: Mapping[str, Any]) -> str:
        return cls._persian_text(bounded_text(row.get("nameFa"), maximum=120))

    @staticmethod
    def _persian_text(value: str) -> str:
        return value.replace("ي", "ی").replace("ك", "ک")

    @staticmethod
    def _verify_arrival_time(arrival: datetime, value: Any) -> None:
        clock = bounded_text(value, maximum=5)
        match = _CLOCK.fullmatch(clock)
        if match is None or (
            arrival.hour != int(match.group("hour"))
            or arrival.minute != int(match.group("minute"))
        ):
            raise ProviderRowError("train arrival time does not match duration")

    @staticmethod
    def _operator_logo_url(value: Any):
        logo_name = bounded_text(value, maximum=128)
        if (
            not _LOGO_NAME.fullmatch(logo_name)
            or ".." in logo_name
            or logo_name.startswith(".")
        ):
            return None
        return trusted_logo_url(
            f"https://fs.snapptrip.com/images/train/uploads/{logo_name}",
            allowed_hosts=SNAPPTRIP_TRAIN_LOGO_HOSTS,
        )

    def _remember_redirect(
        self,
        source_offer_id: str,
        *,
        request: SearchRequest,
        preferences: TrainSearchPreferences,
        origin_endpoint: str,
        destination_endpoint: str,
    ) -> None:
        query = urlencode(
            {
                "adultCount": request.passengers.adults,
                "childCount": request.passengers.children,
                "infantCount": request.passengers.infants,
                "departureDate": request.departure_date.isoformat(),
                "isExclusive": str(preferences.exclusive_compartment).lower(),
                "ticketType": "NORMAL",
                "source": "searchBox",
                "saleType": "one-way",
            }
        )
        self._redirects.set(
            source_offer_id,
            (
                "https://www.snapptrip.com/train-ticket/"
                f"{quote(origin_endpoint, safe='')}/"
                f"{quote(destination_endpoint, safe='')}?{query}"
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
