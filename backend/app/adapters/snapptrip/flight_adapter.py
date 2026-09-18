from __future__ import annotations

import logging
from collections.abc import Mapping
from datetime import datetime
from typing import Any
from urllib.parse import urlencode

from app.adapters.shared.branding import (
    SNAPPTRIP_LOGO_HOSTS,
    airline_code,
    alibaba_airline_logo_url,
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
    SNAPPTRIP_FLIGHT_LOCATIONS_URL,
    SNAPPTRIP_FLIGHT_SEARCH_URL,
    SNAPPTRIP_SELLER,
)
from app.core.errors import AdapterUnavailableError, ResourceNotFoundError
from app.domain.capabilities import Capability, RefundRules
from app.domain.itinerary import FlightDetails, OfferAttributes
from app.domain.location import LocationKind, TravelLocation
from app.domain.offer import Money, OfferDetails, ProviderOffer, Seller
from app.domain.travel import FlightSearchPreferences, SearchRequest, TravelMode
from app.ports.capabilities import SupportsRefundRules
from app.ports.location_search import SupportsLocationSearch
from app.ports.travel_adapter import TravelAdapter

logger = logging.getLogger(__name__)


class SnappTripFlightAdapter(
    TravelAdapter,
    SupportsRefundRules,
    SupportsLocationSearch,
):
    """Verified SnappTrip domestic-flight web API integration."""

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
        self._refund_rules = ExpiringLruStore[str, RefundRules](
            ttl_seconds=offer_ttl_seconds,
            max_entries=max_entries,
        )
        self._location_rows = ExpiringLruStore[
            str, tuple[Mapping[str, Any], ...]
        ](
            ttl_seconds=offer_ttl_seconds,
            max_entries=1,
        )

    @property
    def mode(self) -> TravelMode:
        return TravelMode.FLIGHT

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
        response = await self._fetch_location_rows()
        needle = normalized_text(query)
        locations: list[TravelLocation] = []
        for row in response:
            if not isinstance(row, Mapping):
                continue
            code = bounded_text(row.get("iataCode"), maximum=4).upper()
            name = bounded_text(row.get("cityFaName"), maximum=120)
            english_name = bounded_text(row.get("cityName"), maximum=120)
            if not code or not name:
                continue
            searchable = normalized_text(f"{code} {name} {english_name}")
            if needle and needle not in searchable:
                continue
            locations.append(
                TravelLocation(
                    code=code,
                    name=name,
                    mode=self.mode,
                    kind=LocationKind.AIRPORT,
                    popular=bool(row.get("isSuggested")),
                    providers=[self.provider],
                )
            )
        locations.sort(key=lambda item: (not item.popular, item.name))
        return tuple(locations[: max(1, limit)])

    async def search(self, request: SearchRequest) -> tuple[ProviderOffer, ...]:
        if request.mode is not self.mode:
            raise ValueError("SnappTripFlightAdapter only accepts flight searches.")
        if request.return_date is not None:
            raise AdapterUnavailableError(
                "مقایسهٔ رفت‌وبرگشت پرواز هنوز با قرارداد تأییدشدهٔ "
                "اسنپ‌تریپ پیاده نشده است."
            )
        preferences = (
            request.preferences
            if isinstance(request.preferences, FlightSearchPreferences)
            else FlightSearchPreferences(mode=TravelMode.FLIGHT)
        )
        # The public API accepts the human-readable names returned by
        # `/locations`. Resolve those names through SnappTrip's verified
        # suggestions document instead of forcing the UI to know OTA codes.
        location_rows = await self._fetch_location_rows()
        origin_code = self._resolve_airport_code(request.origin, location_rows)
        destination_code = self._resolve_airport_code(request.destination, location_rows)
        payload = {
            "dateType": "jalali",
            "origin": origin_code,
            "destination": destination_code,
            "destinationIsCity": True,
            "originIsCity": True,
            "adultCount": request.passengers.adults,
            "childCount": request.passengers.children,
            "infantCount": request.passengers.infants,
            "departureDate": request.departure_date.isoformat(),
            "returnDate": None,
            "cabinType": "ECONOMY",
        }
        try:
            rows = await self._fetch_rows(payload)
        except AdapterUnavailableError:
            raise
        except Exception as exc:  # pragma: no cover - network boundary
            logger.warning("SnappTrip flight search failed", exc_info=exc)
            raise AdapterUnavailableError(
                "امکان دریافت اطلاعات پرواز از اسنپ‌تریپ وجود ندارد."
            ) from exc

        offers: list[ProviderOffer] = []
        malformed_rows = 0
        for row in rows:
            try:
                offer = self._parse_offer(
                    row,
                    request=request,
                    preferences=preferences,
                    origin_code=origin_code,
                    destination_code=destination_code,
                )
            except (ValueError, TypeError, OverflowError) as exc:
                malformed_rows += 1
                logger.warning(
                    "Skipping malformed SnappTrip flight row",
                    extra={"error_type": type(exc).__name__},
                )
                continue
            if offer is not None:
                offers.append(offer)
                self._remember_details(offer)
        if rows and malformed_rows == len(rows):
            raise AdapterUnavailableError(
                "ساختار همهٔ نتایج پرواز اسنپ‌تریپ نامعتبر بود."
            )
        return tuple(offers)

    async def get_details(self, offer_id: str) -> OfferDetails:
        details = self._details.get(offer_id)
        if details is None:
            raise ResourceNotFoundError(
                "جزئیات این پرواز در حافظهٔ جست‌وجوی اسنپ‌تریپ پیدا نشد."
            )
        return details

    async def get_refund_rules(self, offer_id: str) -> RefundRules:
        await self.get_details(offer_id)
        rules = self._refund_rules.get(offer_id)
        if rules is None:
            raise AdapterUnavailableError(
                "قانون استرداد این پیشنهاد از اسنپ‌تریپ دریافت نشده است."
            )
        return rules

    @staticmethod
    def _verified_iata_code(value: Any) -> str | None:
        if not isinstance(value, str):
            return None
        code = value.strip().upper()
        if len(code) != 3 or not code.isascii() or not code.isalpha():
            return None
        return code

    def _resolve_airport_code(
        self,
        value: str,
        rows: tuple[Mapping[str, Any], ...],
    ) -> str:
        needle = normalized_text(value)
        exact_code = next(
            (
                code
                for row in rows
                if (code := self._verified_iata_code(row.get("iataCode")))
                and needle
                in {
                    normalized_text(code),
                    normalized_text(
                        bounded_text(row.get("cityFaName"), maximum=120)
                    ),
                    normalized_text(
                        bounded_text(row.get("cityName"), maximum=120)
                    ),
                }
            ),
            None,
        )
        if not exact_code:
            raise AdapterUnavailableError(
                "کد فرودگاه این شهر در فهرست تأییدشدهٔ اسنپ‌تریپ نیست."
            )
        return exact_code

    async def _fetch_location_rows(self) -> tuple[Mapping[str, Any], ...]:
        cached = self._location_rows.get("locations")
        if cached is not None:
            return cached
        response = await self._http.request_json(SNAPPTRIP_FLIGHT_LOCATIONS_URL)
        if not isinstance(response, list):
            raise AdapterUnavailableError("فهرست فرودگاه‌های اسنپ‌تریپ معتبر نبود.")
        rows = tuple(
            row
            for row in response
            if isinstance(row, Mapping)
            and self._verified_iata_code(row.get("iataCode")) is not None
            and bool(bounded_text(row.get("cityFaName"), maximum=120))
        )
        if not rows:
            raise AdapterUnavailableError("فهرست فرودگاه‌های اسنپ‌تریپ معتبر نبود.")
        self._location_rows.set("locations", rows)
        return rows

    async def _fetch_rows(self, payload: Mapping[str, Any]) -> list[Mapping[str, Any]]:
        response = await self._http.request_json(
            SNAPPTRIP_FLIGHT_SEARCH_URL,
            method="POST",
            payload=payload,
            query={"source": "history_cards"},
            flight_api=True,
        )
        rows = response.get("airfares") if isinstance(response, Mapping) else None
        if not isinstance(rows, list):
            raise AdapterUnavailableError("پاسخ جست‌وجوی پرواز اسنپ‌تریپ معتبر نبود.")
        return mapping_rows_or_raise(
            rows,
            invalid_message="ساختار نتایج پرواز اسنپ‌تریپ نامعتبر بود.",
        )

    def _parse_offer(
        self,
        row: Mapping[str, Any],
        *,
        request: SearchRequest,
        preferences: FlightSearchPreferences,
        origin_code: str,
        destination_code: str,
    ) -> ProviderOffer | None:
        source_offer_id = bounded_text(row.get("id"), maximum=20_000)
        routes = row.get("routes")
        route = routes[0] if isinstance(routes, list) and len(routes) == 1 else None
        if not source_offer_id or not isinstance(route, Mapping):
            raise ProviderRowError("flight identifier or route is missing")
        segments = route.get("segments")
        if not isinstance(segments, list) or not segments:
            raise ProviderRowError("flight segments are missing")
        valid_segments = [item for item in segments if isinstance(item, Mapping)]
        if len(valid_segments) != len(segments):
            raise ProviderRowError("flight segments are malformed")

        route_origin = self._verified_iata_code(route.get("originAirportCode"))
        route_destination = self._verified_iata_code(
            route.get("destinationAirportCode")
        )
        if (
            route_origin is None
            or route_destination is None
            or route_origin != origin_code
            or route_destination != destination_code
        ):
            raise ProviderRowError("flight route does not match search")

        segment_times: list[tuple[datetime, datetime]] = []
        previous_arrival_code: str | None = None
        previous_arrival_at: datetime | None = None
        for index, segment in enumerate(valid_segments):
            segment_origin = self._verified_iata_code(
                segment.get("departureAirportCode")
            )
            segment_destination = self._verified_iata_code(
                segment.get("arrivalAirportCode")
            )
            segment_departure = parse_datetime(segment.get("departureDateTime"))
            segment_arrival = parse_datetime(segment.get("arrivalDateTime"))
            if (
                segment_origin is None
                or segment_destination is None
                or segment_departure is None
                or segment_arrival is None
                or segment_arrival <= segment_departure
                or (
                    previous_arrival_code is not None
                    and segment_origin != previous_arrival_code
                )
                or (
                    previous_arrival_at is not None
                    and segment_departure < previous_arrival_at
                )
            ):
                raise ProviderRowError("flight segments are not continuous")
            if index == 0 and (
                segment_origin != origin_code
                or segment_departure.date() != request.departure_date
            ):
                raise ProviderRowError("flight route or departure date does not match search")
            previous_arrival_code = segment_destination
            previous_arrival_at = segment_arrival
            segment_times.append((segment_departure, segment_arrival))

        if previous_arrival_code != destination_code:
            raise ProviderRowError("flight route does not match search")

        first_segment = valid_segments[0]
        departure = segment_times[0][0]
        arrival = segment_times[-1][1]
        pricing = row.get("pricing")
        currency = (
            bounded_text(pricing.get("currency"), maximum=8).upper()
            if isinstance(pricing, Mapping)
            else ""
        )
        price_rials = (
            number(pricing.get("totalPayablePrice"))
            if isinstance(pricing, Mapping)
            else None
        )
        carrier = first_segment.get("carrierAirlineInfo")
        airline = bounded_text(
            carrier.get("airlineName") if isinstance(carrier, Mapping) else None,
            maximum=100,
        )
        verified_airline_code = airline_code(
            first_segment.get("carrierAirlineCode")
            or (
                carrier.get("airlineCode")
                if isinstance(carrier, Mapping)
                else None
            )
            or row.get("airlineCode")
        )
        operator_logo_url = alibaba_airline_logo_url(verified_airline_code) or first_trusted_logo_url(
            carrier.get("logoUrl") if isinstance(carrier, Mapping) else None,
            carrier.get("logo") if isinstance(carrier, Mapping) else None,
            allowed_hosts=SNAPPTRIP_LOGO_HOSTS,
        )
        flight_number = bounded_text(first_segment.get("flightNumber"), maximum=20)
        cabin_class = bounded_text(first_segment.get("cabinType"), maximum=40)
        if (
            departure is None
            or arrival is None
            or arrival <= departure
            or currency != "IRR"
            or price_rials is None
            or price_rials < 0
            or not airline
            or not flight_number
            or not cabin_class
        ):
            raise ProviderRowError("required flight fields are missing or invalid")

        is_charter = any(bool(segment.get("isCharter")) for segment in valid_segments)
        fare_type = "charter" if is_charter else "system"
        stops = max(0, len(valid_segments) - 1)
        if preferences.nonstop_only and stops:
            return None
        if preferences.fare_type is not None and preferences.fare_type != fare_type:
            return None

        baggage_detail = route.get("baggageDetail")
        baggage = (
            number(baggage_detail.get("weight"))
            if isinstance(baggage_detail, Mapping)
            else number(first_segment.get("baggage"))
        )
        baggage_kg = (
            max(0, min(200, round(baggage))) if baggage is not None else None
        )
        remaining_values = [
            number(segment.get("seatsRemaining")) for segment in valid_segments
        ]
        remaining_numbers = [
            max(0, round(value)) for value in remaining_values if value is not None
        ]
        remaining_seats = min(remaining_numbers) if remaining_numbers else None

        refund_type = str(row.get("refundType") or "").strip().upper()
        refundable = {
            "REFUNDABLE": True,
            "NON_REFUNDABLE": False,
            "NONREFUNDABLE": False,
        }.get(refund_type)
        refund_summary = self._refund_summary(row, refundable)
        capabilities: list[Capability] = []
        if refundable is not None and refund_summary:
            capabilities.append(Capability.REFUND_RULES)
            self._remember_refund_rules(
                RefundRules(
                    offer_id=source_offer_id,
                    refundable=refundable,
                    summary=refund_summary,
                )
            )
        installment = row.get("installment")
        if isinstance(installment, Mapping) and installment.get("isAvailable") is True:
            capabilities.append(Capability.INSTALLMENT_PAYMENT)

        origin_info = route.get("originAirportInfo")
        destination_info = route.get("destinationAirportInfo")
        origin_name = bounded_text(
            origin_info.get("faCityName")
            if isinstance(origin_info, Mapping)
            else route_origin,
            maximum=120,
        )
        destination_name = bounded_text(
            destination_info.get("faCityName")
            if isinstance(destination_info, Mapping)
            else route_destination,
            maximum=120,
        )
        if not origin_name or not destination_name:
            raise ProviderRowError("flight route fields are missing")
        self._remember_redirect(
            source_offer_id,
            request=request,
            origin_code=route_origin,
            destination_code=route_destination,
        )
        cancellation_summary = (
            refund_summary[:237] + "..."
            if refund_summary and len(refund_summary) > 240
            else refund_summary
        )
        return ProviderOffer(
            source_offer_id=source_offer_id,
            origin=origin_name,
            destination=destination_name,
            departure_at=departure,
            arrival_at=arrival,
            price=Money(amount=round(price_rials / 10)),
            attributes=OfferAttributes(
                operator=airline,
                operator_code=verified_airline_code,
                operator_logo_url=operator_logo_url,
                service_number=flight_number,
                vehicle_class=cabin_class,
                ticket_type=fare_type,
                stops=stops,
                baggage_allowance_kg=baggage_kg,
            ),
            mode_details=FlightDetails(
                mode=TravelMode.FLIGHT,
                origin_airport_code=route_origin,
                destination_airport_code=route_destination,
                airline=airline,
                flight_number=flight_number,
                fare_type=fare_type,
                cabin_class=cabin_class,
                baggage_allowance_kg=baggage_kg,
            ),
            capabilities=capabilities,
            remaining_seats=remaining_seats,
            cancellation_summary=cancellation_summary,
            refundable=refundable,
            last_updated_at=datetime.now(TEHRAN_TIMEZONE),
        )

    @staticmethod
    def _refund_summary(
        row: Mapping[str, Any],
        refundable: bool | None,
    ) -> str | None:
        if refundable is False:
            return "این بلیت غیرقابل‌استرداد است."
        policies = row.get("policies")
        parts: list[str] = []
        if isinstance(policies, list):
            for policy in policies:
                if not isinstance(policy, Mapping):
                    continue
                rules = policy.get("cancellationPolicies")
                if not isinstance(rules, list):
                    continue
                for rule in rules:
                    if not isinstance(rule, Mapping):
                        continue
                    description = bounded_text(rule.get("description"), maximum=300)
                    percentage = number(rule.get("adultPenaltyPercentage"))
                    if description and percentage is not None:
                        parts.append(f"{description}: {percentage:g}٪ جریمه")
        if parts:
            return "؛ ".join(parts)[:500]
        return None

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
                "adultCount": request.passengers.adults,
                "childCount": request.passengers.children,
                "infantCount": request.passengers.infants,
                "departureDate": request.departure_date.isoformat(),
                "source": "history_cards",
                "dateType": "jalali",
            }
        )
        self._redirects.set(
            source_offer_id,
            (
                f"https://www.snapptrip.com/flights/"
                f"{origin_code}_city/{destination_code}_city?{query}"
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

    def _remember_refund_rules(self, rules: RefundRules) -> None:
        self._refund_rules.set(rules.offer_id, rules)

    def build_redirect_url(self, source_offer_id: str) -> str:
        redirect = self._redirects.get(source_offer_id)
        if redirect is None:
            raise ResourceNotFoundError("پیوند این پیشنهاد اسنپ‌تریپ پیدا نشد.")
        return redirect
