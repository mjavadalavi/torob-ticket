from __future__ import annotations

import logging
from collections.abc import Mapping
from datetime import datetime
from typing import Any
from urllib.parse import urlencode

from app.adapters.booking.base import BookingOfferStore
from app.adapters.booking.http import BookingHttpClient
from app.adapters.booking.parsing import (
    TEHRAN_TIMEZONE,
    bounded_text,
    normalized_text,
    number,
    parse_datetime,
)
from app.adapters.booking.spec import (
    BOOKING_FLIGHT_AIRPORTS_URL,
    BOOKING_FLIGHT_SEARCH_URL,
    BOOKING_SELLER,
)
from app.adapters.shared.branding import alibaba_airline_logo_url
from app.adapters.shared.context import ExpiringLruStore
from app.adapters.shared.parsing import ProviderRowError, mapping_rows_or_raise
from app.core.errors import AdapterUnavailableError
from app.domain.itinerary import FlightDetails, OfferAttributes
from app.domain.location import LocationKind, TravelLocation
from app.domain.offer import Money, ProviderOffer, Seller
from app.domain.travel import FlightSearchPreferences, SearchRequest, TravelMode
from app.ports.location_search import SupportsLocationSearch
from app.ports.travel_adapter import TravelAdapter

logger = logging.getLogger(__name__)


class BookingFlightAdapter(BookingOfferStore, TravelAdapter, SupportsLocationSearch):
    """Verified Booking.ir flight search integration."""

    def __init__(
        self,
        *,
        timeout_seconds: float = 5.0,
        offer_ttl_seconds: int = 900,
        max_entries: int = 5_000,
        http_client: BookingHttpClient | None = None,
    ) -> None:
        BookingOfferStore.__init__(
            self, offer_ttl_seconds=offer_ttl_seconds, max_entries=max_entries
        )
        self._http = http_client or BookingHttpClient(timeout_seconds=timeout_seconds)
        self._locations = ExpiringLruStore[str, tuple[Mapping[str, Any], ...]](
            ttl_seconds=offer_ttl_seconds, max_entries=1
        )

    @property
    def mode(self) -> TravelMode:
        return TravelMode.FLIGHT

    @property
    def provider(self) -> str:
        return "booking"

    @property
    def seller(self) -> Seller:
        return BOOKING_SELLER

    async def search_locations(
        self, query: str, *, limit: int = 10
    ) -> tuple[TravelLocation, ...]:
        rows = await self._fetch_locations()
        needle = normalized_text(query)
        locations: list[TravelLocation] = []
        for row in rows:
            code = bounded_text(row.get("code"), maximum=12).upper()
            name = bounded_text(row.get("cityTitle") or row.get("label"), maximum=120)
            searchable = normalized_text(
                f"{name} {row.get('cityEnglishTitle', '')} {code} {row.get('label', '')}"
            )
            if not code or not name or (needle and needle not in searchable):
                continue
            locations.append(
                TravelLocation(
                    code=code,
                    name=name,
                    mode=self.mode,
                    kind=LocationKind.AIRPORT,
                    popular=bool(row.get("isFeatured")),
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
            raise ValueError("BookingFlightAdapter only accepts flight searches.")
        if request.return_date is not None:
            raise AdapterUnavailableError(
                "پرواز رفت‌وبرگشت بوکینگ باید به‌صورت دو جست‌وجوی یک‌طرفه انجام شود."
            )
        preferences = (
            request.preferences
            if isinstance(request.preferences, FlightSearchPreferences)
            else FlightSearchPreferences(mode=TravelMode.FLIGHT)
        )
        rows = await self._fetch_locations()
        origin = self._resolve_location(request.origin, rows)
        destination = self._resolve_location(request.destination, rows)
        if origin[0] == destination[0]:
            raise AdapterUnavailableError("مبدأ و مقصد پرواز نمی‌توانند یکسان باشند.")
        is_international = origin[2] or destination[2]
        payload = {
            "itineraries": [
                {
                    "originLocation": origin[0],
                    "destinationLocation": destination[0],
                    "departureDate": request.departure_date.isoformat(),
                    "returnDate": None,
                }
            ],
            "adultQuantity": request.passengers.adults,
            "childQuantity": request.passengers.children,
            "infantQuantity": request.passengers.infants,
            "cabinType": None,
            "searchType": 1 if is_international else 2,
        }
        try:
            response = await self._http.request_json(
                BOOKING_FLIGHT_SEARCH_URL, method="POST", payload=payload
            )
        except AdapterUnavailableError:
            raise
        except Exception as exc:  # pragma: no cover - network boundary
            logger.warning("Booking flight search failed", exc_info=exc)
            raise AdapterUnavailableError("امکان دریافت اطلاعات پرواز از بوکینگ وجود ندارد.") from exc
        result = response.get("result") if isinstance(response, Mapping) else None
        if result is None and self._is_no_availability_response(response):
            return ()
        raw_rows = result.get("itineraries") if isinstance(result, Mapping) else None
        if not isinstance(raw_rows, list):
            raise AdapterUnavailableError("نتایج پرواز بوکینگ معتبر نبود.")
        provider_rows = mapping_rows_or_raise(
            raw_rows, invalid_message="ساختار نتایج پرواز بوکینگ نامعتبر بود."
        )
        redirect_url = self._redirect_url(request=request, origin=origin, destination=destination)
        offers: list[ProviderOffer] = []
        malformed_rows = 0
        for row in provider_rows:
            try:
                offer = self._parse_offer(row, request=request, origin=origin, destination=destination, preferences=preferences)
            except (ProviderRowError, ValueError, TypeError, OverflowError) as exc:
                malformed_rows += 1
                logger.warning("Skipping malformed Booking flight row", extra={"error_type": type(exc).__name__})
                continue
            if offer is None:
                continue
            self._remember_offer(offer, redirect_url)
            offers.append(offer)
        if provider_rows and malformed_rows == len(provider_rows):
            raise AdapterUnavailableError("ساختار همهٔ نتایج پرواز بوکینگ نامعتبر بود.")
        return tuple(offers)

    async def _fetch_locations(self) -> tuple[Mapping[str, Any], ...]:
        cached = self._locations.get("airports")
        if cached is not None:
            return cached
        response = await self._http.request_json(BOOKING_FLIGHT_AIRPORTS_URL)
        rows = response.get("result") if isinstance(response, Mapping) else None
        if not isinstance(rows, list):
            raise AdapterUnavailableError("فهرست فرودگاه‌های بوکینگ معتبر نبود.")
        locations = tuple(mapping_rows_or_raise(rows, invalid_message="ساختار فهرست فرودگاه‌های بوکینگ نامعتبر بود."))
        self._locations.set("airports", locations)
        return locations

    @classmethod
    def _resolve_location(
        cls,
        value: str,
        rows: tuple[Mapping[str, Any], ...],
    ) -> tuple[str, str, bool]:
        needle = normalized_text(value)
        matches: dict[str, tuple[str, str, bool]] = {}
        for row in rows:
            code = bounded_text(row.get("code"), maximum=12).upper()
            name = bounded_text(row.get("cityTitle") or row.get("label"), maximum=120)
            english = bounded_text(row.get("cityEnglishTitle"), maximum=120)
            if code and name and needle in {normalized_text(code), normalized_text(name), normalized_text(english), normalized_text(row.get("label"))}:
                matches[code] = (code, name, row.get("isInternational") is True)
        if len(matches) != 1:
            raise AdapterUnavailableError("شناسهٔ شهر پرواز در فهرست بوکینگ پیدا نشد.")
        return next(iter(matches.values()))

    def _parse_offer(
        self, row: Mapping[str, Any], *, request: SearchRequest, origin: tuple[str, str, bool], destination: tuple[str, str, bool], preferences: FlightSearchPreferences
    ) -> ProviderOffer | None:
        if row.get("isFlightSaleable") is False:
            return None
        if row.get("isFlightSaleable") is not True:
            raise ProviderRowError("flight availability is missing")
        source_id = bounded_text(row.get("id"), maximum=20_000)
        flights = row.get("flights")
        if not source_id or not isinstance(flights, list) or not flights:
            raise ProviderRowError("flight identity or flights are missing")
        valid_flights = [item for item in flights if isinstance(item, Mapping)]
        if len(valid_flights) != len(flights):
            raise ProviderRowError("flight rows are malformed")
        segments: list[Mapping[str, Any]] = []
        for flight in valid_flights:
            nested = flight.get("flightsSegments")
            if not isinstance(nested, list) or not nested or not all(isinstance(item, Mapping) for item in nested):
                raise ProviderRowError("flight segments are missing")
            segments.extend(nested)
        first, last = segments[0], segments[-1]
        departure = parse_datetime(first.get("departureDateTime"))
        arrival = parse_datetime(last.get("arrivalDateTime"))
        if departure is None or arrival is None or arrival <= departure or departure.date() != request.departure_date:
            raise ProviderRowError("flight timestamps are invalid")
        total_rials = number(row.get("totalPriceIncludeCommission") or row.get("totalPrice"))
        if total_rials is None or total_rials <= 0:
            raise ProviderRowError("flight fare is invalid")
        stops = max(0, len(segments) - 1) + sum(max(0, round(number(item.get("stops")) or 0)) for item in valid_flights)
        if preferences.nonstop_only and stops:
            return None
        ticket_type = row.get("ticketType")
        if ticket_type not in {0, 1}:
            raise ProviderRowError("flight fare type is unknown")
        fare_type = "charter" if ticket_type == 1 else "system"
        if preferences.fare_type is not None and preferences.fare_type != fare_type:
            return None
        airline = bounded_text(first.get("airlineTitle") or first.get("marketingAirlineTitle"), maximum=100)
        airline_code = bounded_text(first.get("airlineCode") or first.get("marketingAirlineCode"), maximum=3).upper()
        operator_logo_url = alibaba_airline_logo_url(airline_code)
        flight_number = bounded_text(first.get("flightNumber"), maximum=20)
        cabin = bounded_text(first.get("cabinType") or valid_flights[0].get("cabinType"), maximum=40)
        dep_code = bounded_text(first.get("departureAirportLocationCode"), maximum=4).upper()
        arr_code = bounded_text(last.get("arrivalAirportLocationCode"), maximum=4).upper()
        if not airline or not flight_number or not cabin or len(dep_code) != 3 or len(arr_code) != 3:
            raise ProviderRowError("flight carrier fields are missing")
        remaining = [number(item.get("remain")) for item in valid_flights]
        remaining_seats = min(round(value) for value in remaining if value is not None) if remaining and all(value is not None and float(value).is_integer() and value >= request.passengers.total for value in remaining) else None
        if remaining_seats is None:
            return None
        baggage = self._baggage_kg(first.get("baggageAllowance", {}).get("adult") if isinstance(first.get("baggageAllowance"), Mapping) else first.get("baggages"))
        return ProviderOffer(
            source_offer_id=source_id,
            origin=origin[1],
            destination=destination[1],
            departure_at=departure,
            arrival_at=arrival,
            price=Money(amount=round(total_rials / 10)),
            attributes=OfferAttributes(
                operator=airline,
                operator_code=airline_code or None,
                operator_logo_url=operator_logo_url,
                operator_logo_alt=f"نشان شرکت {airline}",
                operator_logo_fallback=airline[:2],
                service_number=flight_number,
                vehicle_class=cabin,
                ticket_type=fare_type,
                stops=stops,
                baggage_allowance_kg=baggage,
            ),
            mode_details=FlightDetails(mode=TravelMode.FLIGHT, origin_airport_code=dep_code, destination_airport_code=arr_code, airline=airline, flight_number=flight_number, fare_type=fare_type, cabin_class=cabin, baggage_allowance_kg=baggage),
            capabilities=[],
            remaining_seats=remaining_seats,
            last_updated_at=datetime.now(TEHRAN_TIMEZONE),
        )

    @staticmethod
    def _baggage_kg(value: Any) -> int | None:
        amount = number(value)
        return max(0, min(200, round(amount))) if amount is not None else None

    @staticmethod
    def _redirect_url(
        *,
        request: SearchRequest,
        origin: tuple[str, str, bool],
        destination: tuple[str, str, bool],
    ) -> str:
        query = urlencode({"adt": request.passengers.adults, "chd": request.passengers.children, "inf": request.passengers.infants, "cabinType": 1, "departureDate": request.departure_date.isoformat()})
        return f"https://www.booking.ir/flights/search/{origin[0].lower()}-{destination[0].lower()}?{query}"

    @staticmethod
    def _is_no_availability_response(response: Any) -> bool:
        if not isinstance(response, Mapping) or response.get("statusCode") != 200:
            return False
        messages = response.get("messages")
        if not isinstance(messages, list):
            return False
        return any(
            isinstance(message, Mapping)
            and "پرواز" in bounded_text(message.get("message"), maximum=300)
            and "یافت نشد" in bounded_text(message.get("message"), maximum=300)
            for message in messages
        )
