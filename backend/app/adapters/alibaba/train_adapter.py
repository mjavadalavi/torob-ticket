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
    ALIBABA_SELLER,
    ALIBABA_TRAIN_AVAILABILITY_URL,
    ALIBABA_TRAIN_STATIONS,
    AlibabaTrainStation,
)
from app.adapters.shared.branding import (
    ALIBABA_LOGO_HOSTS,
    first_trusted_logo_url,
    train_operator_logo_url,
)
from app.adapters.shared.context import ExpiringLruStore
from app.adapters.shared.parsing import ProviderRowError, mapping_rows_or_raise
from app.core.errors import AdapterUnavailableError, ResourceNotFoundError
from app.domain.itinerary import OfferAttributes, TrainDetails
from app.domain.location import LocationKind, TravelLocation
from app.domain.offer import Money, OfferDetails, ProviderOffer, Seller
from app.domain.travel import SearchRequest, TrainSearchPreferences, TravelMode
from app.ports.location_search import SupportsLocationSearch
from app.ports.travel_adapter import TravelAdapter

logger = logging.getLogger(__name__)


class AlibabaTrainAdapter(TravelAdapter, SupportsLocationSearch):
    """Verified Alibaba train integration using its public web-search API."""

    def __init__(
        self,
        *,
        timeout_seconds: float = 5.0,
        offer_ttl_seconds: int = 900,
        max_entries: int = 5_000,
        http_client: AlibabaHttpClient | None = None,
    ) -> None:
        self._timeout_seconds = max(0.5, timeout_seconds)
        self._http = http_client or AlibabaHttpClient(
            timeout_seconds=self._timeout_seconds
        )
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
        return TravelMode.TRAIN

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
        unique: dict[str, AlibabaTrainStation] = {}
        for station in ALIBABA_TRAIN_STATIONS.values():
            unique.setdefault(station.code, station)
        matching = [
            station
            for station in unique.values()
            if not normalized_query
            or normalized_query
            in f"{station.name} {station.code}".replace("\u200c", "").casefold()
        ]
        matching.sort(key=lambda station: station.name)
        return tuple(
            TravelLocation(
                code=station.code,
                name=station.name,
                mode=self.mode,
                kind=LocationKind.RAILWAY_STATION,
                providers=[self.provider],
            )
            for station in matching[: max(1, limit)]
        )

    async def search(self, request: SearchRequest) -> tuple[ProviderOffer, ...]:
        if request.mode is not self.mode:
            raise ValueError("AlibabaTrainAdapter only accepts train searches.")
        if request.return_date is not None:
            raise AdapterUnavailableError(
                "مقایسهٔ رفت‌وبرگشت قطار هنوز با قرارداد تأییدشدهٔ علی‌بابا پیاده نشده است."
            )
        origin = self._station(request.origin)
        destination = self._station(request.destination)
        preferences = (
            request.preferences
            if isinstance(request.preferences, TrainSearchPreferences)
            else TrainSearchPreferences(mode=TravelMode.TRAIN)
        )
        if preferences.vehicle_transport:
            raise AdapterUnavailableError(
                "حمل خودرو برای قطارهای علی‌بابا با قرارداد زنده تأیید نشده است."
            )
        if origin.id == destination.id:
            raise AdapterUnavailableError("مبدأ و مقصد قطار نمی‌توانند یکسان باشند.")
        payload = {
            "origin": origin.code,
            "destination": destination.code,
            "departureDate": request.departure_date.isoformat(),
            "returnDate": None,
            "passengerCount": request.passengers.total,
            "isExclusiveCompartment": preferences.exclusive_compartment,
            "ticketType": {
                "family": "Family",
                "female": "Female",
                "male": "Male",
            }[preferences.passenger_type],
        }
        try:
            rows = await self._fetch_rows(payload)
        except AdapterUnavailableError:
            raise
        except Exception as exc:  # pragma: no cover - network boundary
            logger.warning("Alibaba train search failed", exc_info=exc)
            raise AdapterUnavailableError(
                "امکان دریافت اطلاعات قطار از علی‌بابا وجود ندارد."
            ) from exc

        offers: list[ProviderOffer] = []
        malformed_rows = 0
        for row in rows:
            try:
                offer = self._parse_offer(row, request, preferences, origin, destination)
            except (ValueError, TypeError, OverflowError) as exc:
                malformed_rows += 1
                logger.warning(
                    "Skipping malformed Alibaba train row",
                    extra={"error_type": type(exc).__name__},
                )
                continue
            if offer is not None:
                offers.append(offer)
                self._remember_details(offer)
        if rows and malformed_rows == len(rows):
            raise AdapterUnavailableError(
                "ساختار همهٔ نتایج قطار علی‌بابا نامعتبر بود."
            )
        return tuple(offers)

    async def get_details(self, offer_id: str) -> OfferDetails:
        details = self._details.get(offer_id)
        if details is None:
            raise ResourceNotFoundError(
                "جزئیات این پیشنهاد در حافظهٔ جست‌وجوی علی‌بابا پیدا نشد."
            )
        return details

    @staticmethod
    def _station(value: str) -> AlibabaTrainStation:
        key = value.strip().upper() if value.isascii() else value.strip()
        station = ALIBABA_TRAIN_STATIONS.get(key)
        if station is None:
            raise AdapterUnavailableError(
                "شناسهٔ ایستگاه این مسیر هنوز از علی‌بابا تأیید نشده است."
            )
        return station

    async def _fetch_rows(self, payload: Mapping[str, Any]) -> list[Mapping[str, Any]]:
        created = await self._http.request_json(
            ALIBABA_TRAIN_AVAILABILITY_URL,
            method="POST",
            payload=payload,
        )
        if not isinstance(created, Mapping) or created.get("success") is not True:
            raise AdapterUnavailableError("جست‌وجوی قطار علی‌بابا ناموفق بود.")
        result = created.get("result")
        request_id = result.get("requestId") if isinstance(result, Mapping) else None
        if not request_id:
            raise AdapterUnavailableError("علی‌بابا شناسهٔ جست‌وجو برنگرداند.")

        last_result: Mapping[str, Any] | None = None
        for attempt in range(5):
            response = await self._http.request_json(
                f"{ALIBABA_TRAIN_AVAILABILITY_URL}/{quote(str(request_id), safe='')}",
                method="GET",
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
                                "ساختار نتایج قطار علی‌بابا نامعتبر بود."
                            ),
                        )
            if attempt < 4:
                await asyncio.sleep(0.2)
        if last_result is not None and last_result.get("isCompleted") is True:
            return []
        raise AdapterUnavailableError("نتیجهٔ جست‌وجوی علی‌بابا کامل نشد.")

    def _parse_offer(
        self,
        row: Mapping[str, Any],
        request: SearchRequest,
        preferences: TrainSearchPreferences,
        origin: AlibabaTrainStation,
        destination: AlibabaTrainStation,
    ) -> ProviderOffer | None:
        departure = parse_datetime(row.get("departureDateTime"))
        arrival = parse_datetime(row.get("arrivalDateTime"))
        cost_rials = number(row.get("cost"))
        proposal_id = row.get("proposalId")
        raw_origin_code = row.get("originCode") or row.get("orginCode")
        raw_destination_code = row.get("destinationCode")
        if (
            departure is None
            or arrival is None
            or arrival <= departure
            or cost_rials is None
            or cost_rials < 0
            or proposal_id is None
        ):
            raise ProviderRowError("required train fields are missing or invalid")
        if (
            departure.date() != request.departure_date
            or not self._same_station_code(raw_origin_code, origin.code)
            or not self._same_station_code(raw_destination_code, destination.code)
        ):
            return None

        source_offer_id = str(proposal_id)
        company_name = str(row.get("companyName") or "").strip()
        company_code = str(row.get("companyCode") or "").strip()[:40] or None
        company_logo_url = train_operator_logo_url(company_name) or first_trusted_logo_url(
            row.get("companyLogo"),
            row.get("logoUrl"),
            row.get("logo"),
            allowed_hosts=ALIBABA_LOGO_HOSTS,
        ) or train_operator_logo_url(company_name)
        wagon_name = str(row.get("wagonName") or "").strip()
        train_number = str(row.get("trainNumber") or "").strip()
        if not company_name or not wagon_name or not train_number:
            raise ProviderRowError("required train labels are missing")
        compartment_capacity = number(row.get("compartmentCapacity"))
        remaining = number(row.get("seat")) if "seat" in row else None
        if remaining is not None and remaining < 0:
            return None
        refund_known = "nonRefundable" in row
        non_refundable = bool(row.get("nonRefundable")) if refund_known else None
        origin_code = str(raw_origin_code).strip().upper()
        destination_code = str(raw_destination_code).strip().upper()
        self._remember_redirect(
            source_offer_id,
            request=request,
            preferences=preferences,
            origin_code=origin_code,
            destination_code=destination_code,
        )
        return ProviderOffer(
            source_offer_id=source_offer_id,
            # Provider route codes stay inside the redirect boundary. The
            # normalized contract exposes human-readable Persian locations.
            origin=origin.name,
            destination=destination.name,
            departure_at=departure,
            arrival_at=arrival,
            # Alibaba's verified `cost` value is the per-passenger fare. The
            # public comparison contract consistently exposes party totals.
            price=Money(
                amount=round(cost_rials / 10) * request.passengers.total,
            ),
            attributes=OfferAttributes(
                operator=company_name,
                operator_code=company_code,
                operator_logo_url=company_logo_url,
                service_number=train_number,
                vehicle_class=wagon_name,
                ticket_type=(
                    "charter" if bool(row.get("isCharter")) else "system"
                ) if "isCharter" in row else None,
                stops=0,
            ),
            mode_details=TrainDetails(
                mode=TravelMode.TRAIN,
                railway_company=company_name,
                train_number=train_number,
                class_name=wagon_name,
                compartment_capacity=(
                    max(1, min(12, round(compartment_capacity)))
                    if compartment_capacity
                    else None
                ),
                private_compartment_available=(
                    bool(row.get("isExclusiveCompartmentAvailable"))
                    if "isExclusiveCompartmentAvailable" in row
                    else None
                ),
                women_only_available=None,
                vehicle_transport_available=None,
            ),
            capabilities=[],
            remaining_seats=(round(remaining) if remaining is not None else None),
            cancellation_summary=(
                "این بلیت غیرقابل‌استرداد است."
                if non_refundable is True
                else None
            ),
            refundable=(not non_refundable if non_refundable is not None else None),
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
        preferences: TrainSearchPreferences,
        origin_code: str,
        destination_code: str,
    ) -> None:
        query = urlencode(
            {
                "adult": request.passengers.adults,
                "child": request.passengers.children,
                "infant": request.passengers.infants,
                "departing": gregorian_to_jalali(request.departure_date),
                "ticketType": {
                    "family": "Family",
                    "female": "Female",
                    "male": "Male",
                }[preferences.passenger_type],
                "isExclusive": str(preferences.exclusive_compartment).lower(),
            }
        )
        self._redirects.set(
            source_offer_id,
            f"https://www.alibaba.ir/train/{origin_code}-{destination_code}?{query}"
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
            raise ResourceNotFoundError("پیوند این پیشنهاد علی‌بابا پیدا نشد.")
        return redirect
