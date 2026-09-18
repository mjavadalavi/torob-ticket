from __future__ import annotations

from enum import StrEnum

from pydantic import Field

from app.domain.travel import ApiModel


class Capability(StrEnum):
    REFUND_RULES = "refund_rules"
    SEAT_SELECTION = "seat_selection"
    VEHICLE_TRANSPORT = "vehicle_transport"
    INSTALLMENT_PAYMENT = "installment_payment"
    TOROB_GUARANTEE = "torob_guarantee"
    TOROB_PAY = "torob_pay"


class Seat(ApiModel):
    number: str = Field(min_length=1, max_length=12)
    row: int | None = Field(default=None, ge=1)
    column: int | None = Field(default=None, ge=1)
    available: bool
    price_delta: int = Field(default=0, ge=0)


class SeatMap(ApiModel):
    offer_id: str
    seats: list[Seat]


class RefundRules(ApiModel):
    offer_id: str
    refundable: bool
    summary: str = Field(min_length=1, max_length=500)


class VehicleTransport(ApiModel):
    offer_id: str
    available: bool
    summary: str | None = Field(default=None, max_length=500)


def merge_capabilities(*collections: list[Capability]) -> list[Capability]:
    return list(dict.fromkeys(item for collection in collections for item in collection))
