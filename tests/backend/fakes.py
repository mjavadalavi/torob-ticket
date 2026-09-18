from __future__ import annotations

from datetime import datetime, timedelta, timezone

from app.domain.capabilities import Capability, RefundRules, Seat, SeatMap
from app.domain.itinerary import (
    BusDetails,
    FlightDetails,
    OfferAttributes,
    TrainDetails,
)
from app.domain.location import LocationKind, TravelLocation
from app.domain.offer import Money, OfferDetails, ProviderOffer, Seller
from app.domain.travel import SearchRequest, TravelMode
from app.ports.travel_adapter import TravelAdapter

TEHRAN_TIMEZONE = timezone(timedelta(hours=3, minutes=30))


class FakeTravelAdapter(TravelAdapter):
    """Deterministic contract double. It is test-only and never registered at runtime."""

    def __init__(
        self,
        *,
        mode: TravelMode,
        provider: str,
        price_delta: int = 0,
    ) -> None:
        self._mode = mode
        self._provider = provider
        self._price_delta = price_delta
        self._seller = Seller(
            id=provider,
            name={"test_a": "فروشنده آزمون الف", "test_b": "فروشنده آزمون ب"}.get(
                provider,
                "فروشنده آزمون",
            ),
            rating=4.5,
            review_count=10,
        )
        self._details: dict[str, OfferDetails] = {}

    @property
    def mode(self) -> TravelMode:
        return self._mode

    @property
    def provider(self) -> str:
        return self._provider

    @property
    def seller(self) -> Seller:
        return self._seller

    async def search(self, request: SearchRequest) -> tuple[ProviderOffer, ...]:
        offers: list[ProviderOffer] = []
        durations = {
            TravelMode.FLIGHT: (80, 95, 110),
            TravelMode.TRAIN: (540, 570, 600),
            TravelMode.BUS: (660, 690, 720),
        }[self.mode]
        base_price = {
            TravelMode.FLIGHT: 4_000_000,
            TravelMode.TRAIN: 1_300_000,
            TravelMode.BUS: 650_000,
        }[self.mode]
        for index, duration in enumerate(durations):
            departure = datetime.combine(
                request.departure_date,
                datetime.min.time(),
                tzinfo=TEHRAN_TIMEZONE,
            ) + timedelta(hours=8 + index * 2)
            details = self._mode_details(index, request)
            attributes = OfferAttributes(
                operator=["شرکت یک", "شرکت دو", "شرکت سه"][index],
                service_number=str(100 + index),
                vehicle_class="استاندارد",
                ticket_type="system",
                stops=0,
                baggage_allowance_kg=20 if self.mode is TravelMode.FLIGHT else None,
            )
            offer = ProviderOffer(
                source_offer_id=f"{self.mode.value}-{index}",
                origin=request.origin,
                destination=request.destination,
                departure_at=departure,
                arrival_at=departure + timedelta(minutes=duration),
                price=Money(amount=base_price + index * 100_000 + self._price_delta),
                attributes=attributes,
                mode_details=details,
                capabilities=[
                    Capability.REFUND_RULES,
                    Capability.TOROB_GUARANTEE,
                    Capability.TOROB_PAY,
                    *([Capability.SEAT_SELECTION] if self.mode is TravelMode.BUS else []),
                    *([Capability.VEHICLE_TRANSPORT] if self.mode is TravelMode.TRAIN else []),
                ],
                remaining_seats=8,
                cancellation_summary="قوانین آزمون",
                refundable=True,
                last_updated_at=departure - timedelta(minutes=1),
            )
            offers.append(offer)
            self._details[offer.source_offer_id] = OfferDetails(
                seller_offer_id=offer.source_offer_id,
                mode=self.mode,
                attributes=attributes,
                mode_details=details,
                capabilities=offer.capabilities,
                remaining_seats=offer.remaining_seats,
                cancellation_summary=offer.cancellation_summary,
                refundable=offer.refundable,
                last_updated_at=offer.last_updated_at,
            )
        return tuple(offers)

    async def search_locations(
        self,
        query: str,
        *,
        limit: int = 10,
    ) -> tuple[TravelLocation, ...]:
        kind = {
            TravelMode.FLIGHT: LocationKind.AIRPORT,
            TravelMode.TRAIN: LocationKind.RAILWAY_STATION,
            TravelMode.BUS: LocationKind.BUS_STATION,
        }[self.mode]
        candidates = (("THR", "تهران"), ("MHD", "مشهد"), ("SYZ", "شیراز"))
        normalized = query.replace("\u200c", "").casefold()
        return tuple(
            TravelLocation(
                code=code,
                name=name,
                mode=self.mode,
                kind=kind,
                popular=code in {"THR", "MHD"},
                providers=[self.provider],
            )
            for code, name in candidates
            if not normalized or normalized in name.replace("\u200c", "").casefold()
        )[:limit]

    async def get_details(self, offer_id: str) -> OfferDetails:
        return self._details[offer_id]

    async def get_refund_rules(self, offer_id: str) -> RefundRules:
        details = await self.get_details(offer_id)
        return RefundRules(
            offer_id=offer_id,
            refundable=bool(details.refundable),
            summary=details.cancellation_summary or "قوانین آزمون",
        )

    async def get_seat_map(self, offer_id: str) -> SeatMap:
        await self.get_details(offer_id)
        return SeatMap(
            offer_id=offer_id,
            seats=[
                Seat(number="1", row=1, column=1, available=True),
                Seat(number="2", row=1, column=2, available=False),
            ],
        )

    def build_redirect_url(self, source_offer_id: str) -> str:
        return f"https://www.alibaba.ir/{self.mode.value}/{source_offer_id}"

    def _mode_details(self, index: int, request: SearchRequest):
        if self.mode is TravelMode.FLIGHT:
            return FlightDetails(
                mode=TravelMode.FLIGHT,
                origin_airport_code=request.origin,
                destination_airport_code=request.destination,
                airline=["شرکت یک", "شرکت دو", "شرکت سه"][index],
                flight_number=str(100 + index),
                fare_type="system",
                cabin_class="اکونومی",
                baggage_allowance_kg=20,
            )
        if self.mode is TravelMode.TRAIN:
            return TrainDetails(
                mode=TravelMode.TRAIN,
                railway_company=["شرکت یک", "شرکت دو", "شرکت سه"][index],
                train_number=str(100 + index),
                class_name="چهار تخته",
                compartment_capacity=4,
                private_compartment_available=True,
                women_only_available=True,
                vehicle_transport_available=True,
            )
        return BusDetails(
            mode=TravelMode.BUS,
            origin_terminal="پایانه مبدأ آزمون",
            destination_terminal="پایانه مقصد آزمون",
            company=["شرکت یک", "شرکت دو", "شرکت سه"][index],
            service_number=str(100 + index),
            bus_class="VIP",
            seat_selection_available=True,
            capacity=25,
            cancellation_policy="قوانین آزمون",
        )
