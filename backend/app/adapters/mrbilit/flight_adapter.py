from __future__ import annotations

import asyncio
import logging
from collections.abc import Mapping
from datetime import datetime
from typing import Any
from urllib.parse import urlencode

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
    MRBILIT_FLIGHT_AIRPORTS_URL,
    MRBILIT_FLIGHT_SEARCH_URL,
    MRBILIT_SELLER,
)
from app.adapters.shared.branding import (
    MRBILIT_LOGO_HOSTS,
    alibaba_airline_logo_url,
    airline_code,
    first_trusted_logo_url,
)
from app.adapters.shared.parsing import ProviderRowError, mapping_rows_or_raise
from app.core.errors import AdapterUnavailableError
from app.domain.capabilities import Capability
from app.domain.itinerary import FlightDetails, OfferAttributes
from app.domain.location import LocationKind, TravelLocation
from app.domain.offer import Money, ProviderOffer, Seller
from app.domain.travel import FlightSearchPreferences, SearchRequest, TravelMode
from app.ports.capabilities import SupportsRefundRules
from app.ports.location_search import SupportsLocationSearch
from app.ports.travel_adapter import TravelAdapter

logger = logging.getLogger(__name__)


class MrBilitFlightAdapter(
    MrBilitOfferStore,
    TravelAdapter,
    SupportsRefundRules,
    SupportsLocationSearch,
):
    """Verified MrBilit domestic-flight web API integration."""

    def __init__(
        self,
        *,
        timeout_seconds: float = 5.0,
        offer_ttl_seconds: int = 900,
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

    @property
    def mode(self) -> TravelMode:
        return TravelMode.FLIGHT

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
        rows = await self._fetch_airport_rows(query)
        needle = normalized_text(query)
        locations: list[TravelLocation] = []
        seen: set[str] = set()
        for row in rows:
            code = self._iata(row.get("CityIataCode"))
            name = bounded_text(row.get("PersianTitle"), maximum=120)
            searchable = normalized_text(
                f"{code or ''} {name} {row.get('Title', '')}"
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
                    kind=LocationKind.AIRPORT,
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
            raise ValueError("MrBilitFlightAdapter only accepts flight searches.")
        if request.return_date is not None:
            raise AdapterUnavailableError(
                "پرواز رفت‌وبرگشت مستربلیط باید به‌صورت دو جست‌وجوی "
                "یک‌طرفه انجام شود."
            )
        preferences = (
            request.preferences
            if isinstance(request.preferences, FlightSearchPreferences)
            else FlightSearchPreferences(mode=TravelMode.FLIGHT)
        )
        origin, destination = await asyncio.gather(
            self._resolve_airport(request.origin),
            self._resolve_airport(request.destination),
        )
        if origin[0] == destination[0]:
            raise AdapterUnavailableError("مبدأ و مقصد پرواز نمی‌توانند یکسان باشند.")

        payload = {
            "AdultCount": request.passengers.adults,
            "ChildCount": request.passengers.children,
            "InfantCount": request.passengers.infants,
            "CabinClass": "All",
            "Routes": [
                {
                    "OriginCode": origin[0],
                    "DestinationCode": destination[0],
                    "DepartureDate": request.departure_date.isoformat(),
                }
            ],
            "Baggage": True,
            "IncludeFlightsWithHigherCapacity": False,
        }
        try:
            rows = await self._fetch_rows(payload)
        except AdapterUnavailableError:
            raise
        except Exception as exc:  # pragma: no cover - network boundary
            logger.warning("MrBilit flight search failed", exc_info=exc)
            raise AdapterUnavailableError(
                "امکان دریافت اطلاعات پرواز از مستربلیط وجود ندارد."
            ) from exc

        offers: list[ProviderOffer] = []
        malformed_rows = 0
        for row in rows:
            try:
                parsed = self._parse_offers(
                    row,
                    request=request,
                    preferences=preferences,
                    origin=origin,
                    destination=destination,
                )
            except (ValueError, TypeError, OverflowError) as exc:
                malformed_rows += 1
                logger.warning(
                    "Skipping malformed MrBilit flight row",
                    extra={"error_type": type(exc).__name__},
                )
                continue
            for offer in parsed:
                self._remember_offer(
                    offer,
                    self._redirect_url(
                        request=request,
                        origin_code=origin[0],
                        destination_code=destination[0],
                    ),
                )
                offers.append(offer)
        if rows and malformed_rows == len(rows):
            raise AdapterUnavailableError(
                "ساختار همهٔ نتایج پرواز مستربلیط نامعتبر بود."
            )
        return tuple(offers)

    async def _fetch_airport_rows(
        self,
        query: str,
    ) -> list[Mapping[str, Any]]:
        response = await self._http.request_json(
            MRBILIT_FLIGHT_AIRPORTS_URL,
            query={"term": query},
        )
        if not isinstance(response, list):
            raise AdapterUnavailableError("فهرست فرودگاه‌های مستربلیط معتبر نبود.")
        return mapping_rows_or_raise(
            response,
            invalid_message="ساختار فهرست فرودگاه‌های مستربلیط نامعتبر بود.",
        )

    async def _resolve_airport(self, value: str) -> tuple[str, str]:
        rows = await self._fetch_airport_rows(value)
        needle = normalized_text(value)
        city_matches: dict[str, tuple[str, str]] = {}
        airport_matches: dict[str, tuple[str, str]] = {}
        for row in rows:
            city_code = self._iata(row.get("CityIataCode"))
            city_name = bounded_text(row.get("PersianTitle"), maximum=120)
            city_candidates = {
                normalized_text(city_code or ""),
                normalized_text(city_name),
                normalized_text(bounded_text(row.get("Title"), maximum=120)),
                normalized_text(
                    bounded_text(row.get("Code"), maximum=16).removesuffix("ALL")
                ),
            }
            if city_code and city_name and needle in city_candidates:
                city_matches[city_code] = (city_code, city_name)
            airports = row.get("Airports")
            if not isinstance(airports, list):
                continue
            for airport in airports:
                if not isinstance(airport, Mapping):
                    continue
                airport_code = self._iata(airport.get("Code"))
                airport_name = bounded_text(
                    airport.get("CityPersianTitle"), maximum=120
                )
                candidates = {
                    normalized_text(airport_code or ""),
                    normalized_text(airport_name),
                    normalized_text(
                        bounded_text(airport.get("CityEnglishTitle"), maximum=120)
                    ),
                }
                if airport_code and airport_name and needle in candidates:
                    airport_matches[airport_code] = (airport_code, airport_name)
        matches = city_matches or airport_matches
        if len(matches) != 1:
            raise AdapterUnavailableError(
                "کد فرودگاه این شهر در فهرست تأییدشدهٔ مستربلیط نیست."
            )
        return next(iter(matches.values()))

    async def _fetch_rows(
        self,
        payload: Mapping[str, Any],
    ) -> list[Mapping[str, Any]]:
        response = await self._http.request_json(
            MRBILIT_FLIGHT_SEARCH_URL,
            method="POST",
            payload=payload,
            json_patch=True,
        )
        rows = response.get("Flights") if isinstance(response, Mapping) else None
        if not isinstance(rows, list):
            raise AdapterUnavailableError("پاسخ جست‌وجوی پرواز مستربلیط معتبر نبود.")
        return mapping_rows_or_raise(
            rows,
            invalid_message="ساختار نتایج پرواز مستربلیط نامعتبر بود.",
        )

    def _parse_offers(
        self,
        row: Mapping[str, Any],
        *,
        request: SearchRequest,
        preferences: FlightSearchPreferences,
        origin: tuple[str, str],
        destination: tuple[str, str],
    ) -> list[ProviderOffer]:
        segments = row.get("Segments")
        segment = segments[0] if isinstance(segments, list) and len(segments) == 1 else None
        legs = segment.get("Legs") if isinstance(segment, Mapping) else None
        valid_legs = (
            [leg for leg in legs if isinstance(leg, Mapping)]
            if isinstance(legs, list)
            else []
        )
        if not valid_legs or len(valid_legs) != len(legs or []):
            raise ProviderRowError("flight legs are missing or malformed")

        first_leg = valid_legs[0]
        last_leg = valid_legs[-1]
        route_origin = self._iata(first_leg.get("OriginCode"))
        route_destination = self._iata(last_leg.get("DestinationCode"))
        departure = parse_datetime(first_leg.get("DepartureTime"))
        arrival = parse_datetime(last_leg.get("ArrivalTime"))
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
        for leg in valid_legs:
            leg_origin = self._iata(leg.get("OriginCode"))
            leg_destination = self._iata(leg.get("DestinationCode"))
            leg_departure = parse_datetime(leg.get("DepartureTime"))
            leg_arrival = parse_datetime(leg.get("ArrivalTime"))
            if (
                leg_origin is None
                or leg_destination is None
                or leg_departure is None
                or leg_arrival is None
                or leg_arrival <= leg_departure
                or (
                    previous_destination is not None
                    and leg_origin != previous_destination
                )
                or (
                    previous_arrival is not None
                    and leg_departure < previous_arrival
                )
            ):
                raise ProviderRowError("flight legs are not continuous")
            previous_destination = leg_destination
            previous_arrival = leg_arrival

        airline_value = first_leg.get("Airline")
        airline = bounded_text(
            airline_value.get("PersianTitle")
            if isinstance(airline_value, Mapping)
            else None,
            maximum=100,
        )
        verified_airline_code = airline_code(
            first_leg.get("AirlineCode")
            or (
                airline_value.get("IataCode")
                if isinstance(airline_value, Mapping)
                else None
            )
        )
        operator_logo_url = alibaba_airline_logo_url(verified_airline_code) or first_trusted_logo_url(
            airline_value.get("Logo")
            if isinstance(airline_value, Mapping)
            else None,
            allowed_hosts=MRBILIT_LOGO_HOSTS,
        )
        flight_number = bounded_text(first_leg.get("FlightNumber"), maximum=20)
        if not airline or not flight_number:
            raise ProviderRowError("flight carrier fields are missing")

        explicit_stops = sum(
            max(0, round(number(leg.get("Stops")) or 0)) for leg in valid_legs
        )
        stops = max(0, len(valid_legs) - 1) + explicit_stops
        if preferences.nonstop_only and stops:
            return []

        prices = row.get("Prices")
        if not isinstance(prices, list) or not prices:
            raise ProviderRowError("flight prices are missing")
        offers: list[ProviderOffer] = []
        for price in prices:
            if not isinstance(price, Mapping):
                continue
            offer = self._parse_price(
                price,
                request=request,
                preferences=preferences,
                origin=origin,
                destination=destination,
                departure=departure,
                arrival=arrival,
                airline=airline,
                airline_code_value=verified_airline_code,
                operator_logo_url=operator_logo_url,
                flight_number=flight_number,
                stops=stops,
            )
            if offer is not None:
                offers.append(offer)
        return offers

    def _parse_price(
        self,
        price: Mapping[str, Any],
        *,
        request: SearchRequest,
        preferences: FlightSearchPreferences,
        origin: tuple[str, str],
        destination: tuple[str, str],
        departure: datetime,
        arrival: datetime,
        airline: str,
        airline_code_value: str | None,
        operator_logo_url: Any,
        flight_number: str,
        stops: int,
    ) -> ProviderOffer | None:
        source_offer_id = bounded_text(price.get("ProposalId"), maximum=20_000)
        capacity = number(price.get("Capacity"))
        if (
            not source_offer_id
            or capacity is None
            or not float(capacity).is_integer()
            or capacity < request.passengers.total
        ):
            return None

        fares = price.get("PassengerFares")
        if not isinstance(fares, list):
            raise ProviderRowError("flight passenger fares are missing")
        fare_by_type = {
            bounded_text(fare.get("PaxType"), maximum=3).upper(): number(
                fare.get("TotalFare")
            )
            for fare in fares
            if isinstance(fare, Mapping)
        }
        required = {
            "ADL": request.passengers.adults,
            "CHD": request.passengers.children,
            "INF": request.passengers.infants,
        }
        total_rials = 0.0
        for pax_type, count in required.items():
            if not count:
                continue
            fare = fare_by_type.get(pax_type)
            if fare is None or fare <= 0:
                raise ProviderRowError("flight passenger fare is invalid")
            total_rials += fare * count

        fare_type = "charter" if price.get("IsCharter") is True else "system"
        if preferences.fare_type is not None and preferences.fare_type != fare_type:
            return None
        cabin_class = bounded_text(
            price.get("CabinClassDisplayName") or price.get("CabinClass"),
            maximum=40,
        )
        if not cabin_class:
            raise ProviderRowError("flight cabin class is missing")

        baggage = (
            number(price.get("Baggage"))
            if bounded_text(price.get("BaggageType"), maximum=12).upper() == "KG"
            else None
        )
        baggage_kg = (
            max(0, min(200, round(baggage))) if baggage is not None else None
        )
        refund_summary = bounded_text(price.get("FareRules"), maximum=240) or None
        refundable = None
        capabilities: list[Capability] = []
        if refund_summary:
            refundable = "غیرقابل" not in normalized_text(refund_summary)
            capabilities.append(Capability.REFUND_RULES)

        return ProviderOffer(
            source_offer_id=source_offer_id,
            origin=origin[1],
            destination=destination[1],
            departure_at=departure,
            arrival_at=arrival,
            price=Money(amount=round(total_rials / 10)),
            attributes=OfferAttributes(
                operator=airline,
                operator_code=airline_code_value,
                operator_logo_url=operator_logo_url,
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
            remaining_seats=round(capacity),
            cancellation_summary=refund_summary,
            refundable=refundable,
            last_updated_at=datetime.now(TEHRAN_TIMEZONE),
        )

    @staticmethod
    def _iata(value: Any) -> str | None:
        code = bounded_text(value, maximum=4).upper()
        return code if len(code) == 3 and code.isascii() and code.isalpha() else None

    @staticmethod
    def _redirect_url(
        *,
        request: SearchRequest,
        origin_code: str,
        destination_code: str,
    ) -> str:
        query = urlencode(
            {
                "departureDate": request.departure_date.isoformat(),
                "adultCount": request.passengers.adults,
                "childCount": request.passengers.children,
                "infantCount": request.passengers.infants,
            }
        )
        return (
            f"https://mrbilit.com/flights/{origin_code}-{destination_code}?{query}"
        )
