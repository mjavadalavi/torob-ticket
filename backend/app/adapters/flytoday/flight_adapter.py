from __future__ import annotations

import asyncio
import logging
from collections.abc import Mapping
from datetime import datetime
from typing import Any
from urllib.parse import urlencode

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
    FLYTODAY_FLIGHT_LOCATION_URL,
    FLYTODAY_FLIGHT_SEARCH_URL,
    FLYTODAY_SELLER,
)
from app.adapters.shared.branding import alibaba_airline_logo_url
from app.adapters.shared.parsing import ProviderRowError, mapping_rows_or_raise
from app.core.errors import AdapterUnavailableError
from app.domain.capabilities import Capability
from app.domain.itinerary import FlightDetails, OfferAttributes
from app.domain.location import LocationKind, TravelLocation
from app.domain.offer import Money, ProviderOffer, Seller
from app.domain.travel import FlightSearchPreferences, SearchRequest, TravelMode
from app.ports.location_search import SupportsLocationSearch
from app.ports.travel_adapter import TravelAdapter

logger = logging.getLogger(__name__)


class FlyTodayFlightAdapter(
    FlyTodayOfferStore,
    TravelAdapter,
    SupportsLocationSearch,
):
    """Verified FlyToday domestic-flight web API integration."""

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
        return TravelMode.FLIGHT

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
        rows = await self._fetch_location_rows(
            query,
            path="https://www.flytodayir.com/flight",
        )
        needle = normalized_text(query)
        locations: list[TravelLocation] = []
        seen: set[str] = set()
        for row in rows:
            code = self._iata(row.get("iata"))
            city_name = bounded_text(row.get("cityName"), maximum=120)
            name = city_name or bounded_text(row.get("name"), maximum=120)
            searchable = normalized_text(
                f"{code or ''} {name} {row.get('name', '')}"
            )
            if (
                code is None
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
                    kind=(
                        LocationKind.AIRPORT
                    ),
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
            raise ValueError("FlyTodayFlightAdapter only accepts flight searches.")
        if request.return_date is not None:
            raise AdapterUnavailableError(
                "پرواز رفت‌وبرگشت فلای‌تودی باید به‌صورت دو جست‌وجوی "
                "یک‌طرفه انجام شود."
            )
        preferences = (
            request.preferences
            if isinstance(request.preferences, FlightSearchPreferences)
            else FlightSearchPreferences(mode=TravelMode.FLIGHT)
        )
        provisional_path = "https://www.flytodayir.com" + self._result_path(
            request=request,
            origin_code="thr",
            destination_code="mhd",
        )
        origin, destination = await asyncio.gather(
            self._resolve_airport(request.origin, path=provisional_path),
            self._resolve_airport(request.destination, path=provisional_path),
        )
        if origin[0] == destination[0]:
            raise AdapterUnavailableError("مبدأ و مقصد پرواز نمی‌توانند یکسان باشند.")

        result_path = self._result_path(
            request=request,
            origin_code=origin[0],
            destination_code=destination[0],
        )
        result_url = f"https://www.flytodayir.com{result_path}"
        payload = {
            "pricingSourceType": 0,
            "adultCount": request.passengers.adults,
            "childCount": request.passengers.children,
            "infantCount": request.passengers.infants,
            "travelPreference": {
                "cabinType": "Y",
                "maxStopsQuantity": "All",
                "airTripType": "OneWay",
            },
            "originDestinationInformations": [
                {
                    "departureDateTime": request.departure_date.isoformat(),
                    "destinationLocationCode": destination[0],
                    "destinationType": "City",
                    "originLocationCode": origin[0],
                    "originType": "City",
                }
            ],
            "isJalali": True,
        }
        try:
            response = await self._http.request_json(
                FLYTODAY_FLIGHT_SEARCH_URL,
                method="POST",
                payload=payload,
                path=result_url,
            )
        except AdapterUnavailableError:
            raise
        except Exception as exc:  # pragma: no cover - network boundary
            logger.warning("FlyToday flight search failed", exc_info=exc)
            raise AdapterUnavailableError(
                "امکان دریافت اطلاعات پرواز از فلای‌تودی وجود ندارد."
            ) from exc

        if not isinstance(response, Mapping):
            raise AdapterUnavailableError("پاسخ جست‌وجوی پرواز فلای‌تودی معتبر نبود.")
        raw_rows = response.get("pricedItineraries")
        if not isinstance(raw_rows, list):
            raise AdapterUnavailableError("نتایج پرواز فلای‌تودی معتبر نبود.")
        rows = mapping_rows_or_raise(
            raw_rows,
            invalid_message="ساختار نتایج پرواز فلای‌تودی نامعتبر بود.",
        )
        search_id = bounded_text(response.get("searchId"), maximum=80)
        additional_data = response.get("additionalData")
        if not search_id or not isinstance(additional_data, Mapping):
            raise AdapterUnavailableError("شناسه یا دادهٔ تکمیلی فلای‌تودی معتبر نبود.")

        airline_names = self._airline_names(additional_data)
        airport_names = self._airport_names(additional_data)
        offers: list[ProviderOffer] = []
        malformed_rows = 0
        for row in rows:
            try:
                offer = self._parse_offer(
                    row,
                    request=request,
                    preferences=preferences,
                    search_id=search_id,
                    origin=origin,
                    destination=destination,
                    airline_names=airline_names,
                    airport_names=airport_names,
                )
            except (ValueError, TypeError, OverflowError) as exc:
                malformed_rows += 1
                logger.warning(
                    "Skipping malformed FlyToday flight row",
                    extra={"error_type": type(exc).__name__},
                )
                continue
            if offer is None:
                continue
            self._remember_offer(
                offer,
                result_url,
            )
            offers.append(offer)
        if rows and malformed_rows == len(rows):
            raise AdapterUnavailableError(
                "ساختار همهٔ نتایج پرواز فلای‌تودی نامعتبر بود."
            )
        return tuple(offers)

    async def _fetch_location_rows(
        self,
        query: str,
        *,
        path: str,
    ) -> list[Mapping[str, Any]]:
        response = await self._http.request_json(
            FLYTODAY_FLIGHT_LOCATION_URL,
            method="POST",
            payload={
                "searchTerm": query,
                "pageNumber": 1,
                "pageSize": 25,
                "isDomestic": True,
                "includeCountry": False,
            },
            path=path,
        )
        rows = response.get("locations") if isinstance(response, Mapping) else None
        if not isinstance(rows, list):
            raise AdapterUnavailableError(
                "فهرست فرودگاه‌های فلای‌تودی معتبر نبود."
            )
        return mapping_rows_or_raise(
            rows,
            invalid_message="ساختار فهرست فرودگاه‌های فلای‌تودی نامعتبر بود.",
        )

    async def _resolve_airport(
        self,
        value: str,
        *,
        path: str,
    ) -> tuple[str, str]:
        rows = await self._fetch_location_rows(value, path=path)
        needle = normalized_text(value)
        matches: dict[str, tuple[str, str]] = {}
        for row in rows:
            code = self._iata(row.get("iata"))
            city_name = bounded_text(row.get("cityName"), maximum=120)
            airport_name = bounded_text(row.get("name"), maximum=120)
            candidates = {
                normalized_text(code),
                normalized_text(city_name),
                normalized_text(airport_name),
            }
            if code and city_name and needle in candidates:
                matches[code] = (code, city_name)
        if len(matches) != 1:
            raise AdapterUnavailableError(
                "کد فرودگاه این شهر در پاسخ تأییدشدهٔ فلای‌تودی پیدا نشد."
            )
        return next(iter(matches.values()))

    def _parse_offer(
        self,
        row: Mapping[str, Any],
        *,
        request: SearchRequest,
        preferences: FlightSearchPreferences,
        search_id: str,
        origin: tuple[str, str],
        destination: tuple[str, str],
        airline_names: Mapping[str, str],
        airport_names: Mapping[str, str],
    ) -> ProviderOffer | None:
        options = row.get("originDestinationOptions")
        option = options[0] if isinstance(options, list) and len(options) == 1 else None
        segments = (
            option.get("flightSegments")
            if isinstance(option, Mapping)
            else None
        )
        valid_segments = (
            [segment for segment in segments if isinstance(segment, Mapping)]
            if isinstance(segments, list)
            else []
        )
        if not valid_segments or len(valid_segments) != len(segments or []):
            raise ProviderRowError("flight segments are missing or malformed")

        first = valid_segments[0]
        last = valid_segments[-1]
        route_origin = self._iata(first.get("departureAirportCityId"))
        route_destination = self._iata(last.get("arrivalAirportCityId"))
        departure = parse_datetime(first.get("departureDateTime"))
        arrival = parse_datetime(last.get("arrivalDateTime"))
        if (
            route_origin != origin[0]
            or route_destination != destination[0]
            or departure is None
            or arrival is None
            or arrival <= departure
            or departure.date() != request.departure_date
        ):
            raise ProviderRowError("flight route or timestamps are invalid")

        previous_destination: str | None = None
        previous_arrival: datetime | None = None
        for segment in valid_segments:
            segment_origin = self._iata(segment.get("departureAirportLocationCode"))
            segment_destination = self._iata(
                segment.get("arrivalAirportLocationCode")
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
                    previous_destination is not None
                    and segment_origin != previous_destination
                )
                or (
                    previous_arrival is not None
                    and segment_departure < previous_arrival
                )
            ):
                raise ProviderRowError("flight segments are not continuous")
            previous_destination = segment_destination
            previous_arrival = segment_arrival

        airline_code = bounded_text(
            first.get("marketingAirlineCode"), maximum=3
        ).upper()
        airline = airline_names.get(airline_code) or airline_code
        flight_number = bounded_text(first.get("flightNumber"), maximum=20)
        cabin_class = bounded_text(
            first.get("cabinClassNameLocal") or first.get("cabinClassName"),
            maximum=40,
        )
        if not airline or not flight_number or not cabin_class:
            raise ProviderRowError("flight carrier fields are missing")

        fare_type = "charter" if row.get("isCharter") is True else "system"
        if preferences.fare_type is not None and preferences.fare_type != fare_type:
            return None
        stops = max(0, len(valid_segments) - 1) + sum(
            max(0, round(number(segment.get("stopQuantity")) or 0))
            for segment in valid_segments
        )
        if preferences.nonstop_only and stops:
            return None

        pricing = row.get("airItineraryPricingInfo")
        total_fare = (
            pricing.get("itinTotalFare")
            if isinstance(pricing, Mapping)
            else None
        )
        total_rials = (
            number(total_fare.get("totalFare"))
            if isinstance(total_fare, Mapping)
            else None
        )
        if total_rials is None or total_rials <= 0:
            raise ProviderRowError("flight total fare is invalid")

        capacities = [number(segment.get("seatsRemaining")) for segment in valid_segments]
        if any(
            capacity is None
            or not float(capacity).is_integer()
            or capacity < request.passengers.total
            for capacity in capacities
        ):
            return None
        remaining_seats = min(round(capacity) for capacity in capacities if capacity is not None)

        source_key = bounded_text(row.get("key"), maximum=256)
        fare_source = bounded_text(row.get("fareSourceCode"), maximum=20_000)
        if not source_key and not fare_source:
            raise ProviderRowError("flight offer identity is missing")
        source_offer_id = f"{search_id}:{source_key or fare_source}"

        baggage_kg = self._baggage_kg(first.get("baggage"))
        pay_later = row.get("payLater")
        capabilities = (
            [Capability.INSTALLMENT_PAYMENT]
            if isinstance(pay_later, Mapping)
            and pay_later.get("hasPayLater") is True
            else []
        )
        canonical_origin = airport_names.get(origin[0], origin[1])
        canonical_destination = airport_names.get(destination[0], destination[1])
        return ProviderOffer(
            source_offer_id=source_offer_id,
            origin=canonical_origin,
            destination=canonical_destination,
            departure_at=departure,
            arrival_at=arrival,
            price=Money(amount=round(total_rials / 10)),
            attributes=OfferAttributes(
                operator=airline,
                operator_code=airline_code or None,
                operator_logo_url=alibaba_airline_logo_url(airline_code),
                service_number=flight_number,
                vehicle_class=cabin_class,
                ticket_type=fare_type,
                stops=stops,
                baggage_allowance_kg=baggage_kg,
            ),
            mode_details=FlightDetails(
                mode=TravelMode.FLIGHT,
                origin_airport_code=origin[0],
                destination_airport_code=destination[0],
                airline=airline,
                flight_number=flight_number,
                fare_type=fare_type,
                cabin_class=cabin_class,
                baggage_allowance_kg=baggage_kg,
            ),
            capabilities=capabilities,
            remaining_seats=remaining_seats,
            cancellation_summary=None,
            refundable=None,
            last_updated_at=datetime.now(TEHRAN_TIMEZONE),
        )

    @staticmethod
    def _airline_names(additional_data: Mapping[str, Any]) -> Mapping[str, str]:
        rows = additional_data.get("airlines")
        if not isinstance(rows, list):
            return {}
        return {
            bounded_text(row.get("iata"), maximum=3).upper(): bounded_text(
                row.get("nameLocal") or row.get("name"), maximum=100
            )
            for row in rows
            if isinstance(row, Mapping)
            and bounded_text(row.get("iata"), maximum=3)
            and bounded_text(row.get("nameLocal") or row.get("name"), maximum=100)
        }

    @staticmethod
    def _airport_names(additional_data: Mapping[str, Any]) -> Mapping[str, str]:
        rows = additional_data.get("airports")
        if not isinstance(rows, list):
            return {}
        return {
            bounded_text(row.get("cityId"), maximum=4).upper(): bounded_text(
                row.get("cityLocal"), maximum=120
            )
            for row in rows
            if isinstance(row, Mapping)
            and bounded_text(row.get("cityId"), maximum=4)
            and bounded_text(row.get("cityLocal"), maximum=120)
        }

    @staticmethod
    def _baggage_kg(value: Any) -> int | None:
        amount = number(value)
        if amount is None:
            return None
        text = normalized_text(value)
        if "kg" not in text and "کیلو" not in text:
            return None
        return max(0, min(200, round(amount)))

    @staticmethod
    def _iata(value: Any) -> str | None:
        code = bounded_text(value, maximum=4).upper()
        return code if len(code) == 3 and code.isascii() and code.isalpha() else None

    @staticmethod
    def _result_path(
        *,
        request: SearchRequest,
        origin_code: str,
        destination_code: str,
    ) -> str:
        query = urlencode(
            {
                "departure": f"{origin_code.lower()},1",
                "arrival": f"{destination_code.lower()},1",
                "departureDate": request.departure_date.isoformat(),
                "adt": request.passengers.adults,
                "chd": request.passengers.children,
                "inf": request.passengers.infants,
                "cabin": 1,
                "isDomestic": "true",
                "isAnyWhere": "false",
            }
        )
        return f"/flight/search?{query}"
