from __future__ import annotations

import asyncio
import logging
from collections.abc import Mapping
from datetime import datetime
from typing import Any
from urllib.parse import quote, urlencode

from app.adapters.alibaba.http import AlibabaHttpClient
from app.adapters.alibaba.parsing import (
    TEHRAN_TIMEZONE,
    gregorian_to_jalali,
    number,
    parse_datetime,
)
from app.adapters.alibaba.spec import (
    ALIBABA_DOMESTIC_AIRPORTS,
    ALIBABA_FLIGHT_AVAILABILITY_URL,
    ALIBABA_SELLER,
    AlibabaAirport,
)
from app.adapters.shared.branding import airline_code, alibaba_airline_logo_url
from app.adapters.shared.context import ExpiringLruStore
from app.adapters.shared.parsing import ProviderRowError, mapping_rows_or_raise
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


class AlibabaFlightAdapter(TravelAdapter, SupportsRefundRules, SupportsLocationSearch):
    """Verified Alibaba domestic-flight integration."""

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
        self._refund_rules = ExpiringLruStore[str, RefundRules](
            ttl_seconds=offer_ttl_seconds,
            max_entries=max_entries,
        )

    @property
    def mode(self) -> TravelMode:
        return TravelMode.FLIGHT

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
        normalized_query = (
            " ".join(query.split())
            .replace("ي", "ی")
            .replace("ك", "ک")
            .replace("\u200c", "")
            .casefold()
        )
        unique: dict[str, AlibabaAirport] = {}
        for airport in ALIBABA_DOMESTIC_AIRPORTS.values():
            unique.setdefault(airport.code, airport)
        matching = [
            airport
            for airport in unique.values()
            if not normalized_query
            or normalized_query
            in f"{airport.name} {airport.code}".replace("\u200c", "").casefold()
        ]
        matching.sort(key=lambda airport: airport.name)
        return tuple(
            TravelLocation(
                code=airport.code,
                name=airport.name,
                mode=self.mode,
                kind=LocationKind.AIRPORT,
                popular=True,
                providers=[self.provider],
            )
            for airport in matching[: max(1, limit)]
        )

    async def search(self, request: SearchRequest) -> tuple[ProviderOffer, ...]:
        if request.mode is not self.mode:
            raise ValueError("AlibabaFlightAdapter only accepts flight searches.")
        if request.return_date is not None:
            raise AdapterUnavailableError(
                "مقایسهٔ رفت‌وبرگشت پرواز هنوز با قرارداد "
                "تأییدشدهٔ علی‌بابا "
                "پیاده نشده است."
            )
        origin = self._airport(request.origin)
        destination = self._airport(request.destination)
        preferences = (
            request.preferences
            if isinstance(request.preferences, FlightSearchPreferences)
            else FlightSearchPreferences(mode=TravelMode.FLIGHT)
        )
        payload = {
            "origin": origin.code,
            "destination": destination.code,
            "departureDate": request.departure_date.isoformat(),
            "returnDate": None,
            "adult": request.passengers.adults,
            "child": request.passengers.children,
            "infant": request.passengers.infants,
        }
        try:
            rows = await self._fetch_rows(payload)
        except AdapterUnavailableError:
            raise
        except Exception as exc:  # pragma: no cover - network boundary
            logger.warning("Alibaba flight search failed", exc_info=exc)
            raise AdapterUnavailableError(
                "امکان دریافت اطلاعات پرواز از علی‌بابا "
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
                    "Skipping malformed Alibaba flight row",
                    extra={"error_type": type(exc).__name__},
                )
                continue
            if offer is not None:
                offers.append(offer)
                self._remember_details(offer)
        if rows and malformed_rows == len(rows):
            raise AdapterUnavailableError(
                "ساختار همهٔ نتایج پرواز علی‌بابا نامعتبر بود."
            )
        return tuple(offers)

    async def get_details(self, offer_id: str) -> OfferDetails:
        details = self._details.get(offer_id)
        if details is None:
            raise ResourceNotFoundError(
                "جزئیات این پرواز در حافظهٔ جست‌وجوی "
                "علی‌بابا "
                "پیدا نشد."
            )
        return details

    async def get_refund_rules(self, offer_id: str) -> RefundRules:
        await self.get_details(offer_id)
        rules = self._refund_rules.get(offer_id)
        if rules is None:
            raise AdapterUnavailableError(
                "قانون استرداد این پیشنهاد از علی‌بابا "
                "دریافت نشده است."
            )
        return rules

    @staticmethod
    def _airport(value: str) -> AlibabaAirport:
        key = value.strip().upper() if value.isascii() else value.strip()
        airport = ALIBABA_DOMESTIC_AIRPORTS.get(key)
        if airport is None:
            raise AdapterUnavailableError(
                "کد فرودگاه این مسیر در فهرست تأییدشدهٔ "
                "علی‌بابا نیست."
            )
        return airport

    async def _fetch_rows(self, payload: Mapping[str, Any]) -> list[Mapping[str, Any]]:
        created = await self._http.request_json(
            ALIBABA_FLIGHT_AVAILABILITY_URL,
            method="POST",
            payload=payload,
        )
        if not isinstance(created, Mapping) or created.get("success") is not True:
            raise AdapterUnavailableError(
                "جست‌وجوی پرواز علی‌بابا ناموفق بود."
            )
        result = created.get("result")
        request_id = result.get("requestId") if isinstance(result, Mapping) else None
        if not request_id:
            raise AdapterUnavailableError(
                "علی‌بابا شناسهٔ جست‌وجو برنگرداند."
            )

        last_result: Mapping[str, Any] | None = None
        for attempt in range(5):
            response = await self._http.request_json(
                f"{ALIBABA_FLIGHT_AVAILABILITY_URL}/"
                f"{quote(str(request_id), safe='')}",
            )
            if isinstance(response, Mapping) and response.get("success") is True:
                candidate = response.get("result")
                if isinstance(candidate, Mapping):
                    last_result = candidate
                    rows = candidate.get("departing")
                    if isinstance(rows, list) and (
                        rows or candidate.get("isCompleted") is True
                    ):
                        return mapping_rows_or_raise(
                            rows,
                            invalid_message=(
                                "ساختار نتایج پرواز علی‌بابا نامعتبر بود."
                            ),
                        )
            if attempt < 4:
                await asyncio.sleep(0.2)
        if last_result is not None and last_result.get("isCompleted") is True:
            return []
        raise AdapterUnavailableError(
            "نتیجهٔ جست‌وجوی علی‌بابا کامل نشد."
        )

    def _parse_offer(
        self,
        row: Mapping[str, Any],
        *,
        request: SearchRequest,
        preferences: FlightSearchPreferences,
        origin: AlibabaAirport,
        destination: AlibabaAirport,
    ) -> ProviderOffer | None:
        if not self._is_available(row):
            return None
        source_offer_id = row.get("proposalId")
        departure = parse_datetime(row.get("leaveDateTime"))
        arrival = parse_datetime(row.get("arrivalDateTime"))
        airline = str(row.get("airlineName") or "").strip()
        verified_airline_code = airline_code(row.get("airlineCode"))
        flight_number = str(row.get("flightNumber") or "").strip()
        cabin_class = str(row.get("classTypeName") or "").strip()
        if (
            not source_offer_id
            or departure is None
            or arrival is None
            or arrival <= departure
            or not airline
            or not flight_number
            or not cabin_class
        ):
            raise ProviderRowError("required flight fields are missing")

        row_origin = str(row.get("origin") or "").strip().upper()
        row_destination = str(row.get("destination") or "").strip().upper()
        if (
            row_origin != origin.code
            or row_destination != destination.code
            or departure.date() != request.departure_date
        ):
            raise ProviderRowError("flight route or departure date does not match search")

        has_connection = bool(row.get("hasConnection"))
        is_charter = bool(row.get("isCharter"))
        fare_type = "charter" if is_charter else "system"
        if preferences.nonstop_only and has_connection:
            return None
        if preferences.fare_type is not None and preferences.fare_type != fare_type:
            return None

        total_rials = self._total_price_rials(row, request)
        if total_rials is None:
            return None
        if total_rials < 0:
            raise ProviderRowError("flight price cannot be negative")
        baggage = number(row.get("maxAllowedBaggage"))
        remaining = number(row.get("seat"))
        refundable = bool(row.get("isRefundable")) if "isRefundable" in row else None
        source_offer_id = str(source_offer_id)
        refund_summary = self._refund_summary(row, refundable)
        capabilities = (
            [Capability.REFUND_RULES]
            if refundable is not None and refund_summary is not None
            else []
        )
        if capabilities:
            self._remember_refund_rules(
                RefundRules(
                    offer_id=source_offer_id,
                    refundable=bool(refundable),
                    summary=refund_summary,
                )
            )
        self._remember_redirect(
            source_offer_id,
            request=request,
            origin_code=row_origin,
            destination_code=row_destination,
        )
        return ProviderOffer(
            source_offer_id=source_offer_id,
            origin=origin.name,
            destination=destination.name,
            departure_at=departure,
            arrival_at=arrival,
            price=Money(amount=round(total_rials / 10)),
            attributes=OfferAttributes(
                operator=airline,
                operator_code=verified_airline_code,
                operator_logo_url=alibaba_airline_logo_url(
                    verified_airline_code
                ),
                service_number=flight_number,
                vehicle_class=cabin_class,
                ticket_type=fare_type,
                stops=(1 if has_connection else 0),
                baggage_allowance_kg=(
                    max(0, min(200, round(baggage))) if baggage is not None else None
                ),
            ),
            mode_details=FlightDetails(
                mode=TravelMode.FLIGHT,
                origin_airport_code=row_origin,
                destination_airport_code=row_destination,
                airline=airline,
                flight_number=flight_number,
                fare_type=fare_type,
                cabin_class=cabin_class,
                baggage_allowance_kg=(
                    max(0, min(200, round(baggage))) if baggage is not None else None
                ),
            ),
            capabilities=capabilities,
            remaining_seats=(
                max(0, round(remaining)) if remaining is not None else None
            ),
            cancellation_summary=(
                refund_summary[:237] + "..."
                if refund_summary and len(refund_summary) > 240
                else refund_summary
            ),
            refundable=refundable,
            last_updated_at=datetime.now(TEHRAN_TIMEZONE),
        )

    @staticmethod
    def _is_available(row: Mapping[str, Any]) -> bool:
        """Apply only availability signals verified in Alibaba responses."""

        if "seat" in row:
            remaining = number(row.get("seat"))
            if remaining is not None and remaining <= 0:
                return False
        if "status" in row:
            status = row.get("status")
            if isinstance(status, str) and status.strip().upper() in {"C", "X"}:
                return False
        return not (
            "isAllowedToBuy" in row and row.get("isAllowedToBuy") is False
        )

    @staticmethod
    def _total_price_rials(
        row: Mapping[str, Any],
        request: SearchRequest,
    ) -> float | None:
        adult = number(row.get("priceAdult"))
        child = number(row.get("priceChild"))
        infant = number(row.get("priceInfant"))
        if adult is None:
            return None
        if request.passengers.children and child is None:
            return None
        if request.passengers.infants and infant is None:
            return None
        return (
            (adult * request.passengers.adults)
            + ((child or 0) * request.passengers.children)
            + ((infant or 0) * request.passengers.infants)
        )

    @staticmethod
    def _refund_summary(
        row: Mapping[str, Any],
        refundable: bool | None,
    ) -> str | None:
        if refundable is False:
            return "این بلیت غیرقابل‌استرداد است."
        raw_rules = row.get("crcn")
        if isinstance(raw_rules, Mapping):
            parts = [
                f"{str(period).strip()}: {str(penalty).strip()} جریمه"
                for period, penalty in raw_rules.items()
                if str(period).strip() and str(penalty).strip()
            ]
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
                "adult": request.passengers.adults,
                "child": request.passengers.children,
                "infant": request.passengers.infants,
                "departing": gregorian_to_jalali(request.departure_date),
            }
        )
        self._redirects.set(
            source_offer_id,
            f"https://www.alibaba.ir/flights/{origin_code}-{destination_code}?{query}"
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
            raise ResourceNotFoundError(
                "پیوند این پیشنهاد علی‌بابا پیدا نشد."
            )
        return redirect
