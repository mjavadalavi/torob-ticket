from __future__ import annotations

from typing import Protocol, runtime_checkable

from app.domain.capabilities import RefundRules, SeatMap, VehicleTransport


@runtime_checkable
class SupportsSeatSelection(Protocol):
    async def get_seat_map(self, offer_id: str) -> SeatMap: ...


@runtime_checkable
class SupportsRefundRules(Protocol):
    async def get_refund_rules(self, offer_id: str) -> RefundRules: ...


@runtime_checkable
class SupportsVehicleTransport(Protocol):
    async def get_vehicle_transport(self, offer_id: str) -> VehicleTransport: ...
