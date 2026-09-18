from __future__ import annotations

from collections.abc import Callable
from datetime import date, datetime
from enum import StrEnum
from typing import Annotated, Any, Literal, Self
from zoneinfo import ZoneInfo

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    ValidationInfo,
    field_validator,
    model_validator,
)

TEHRAN_TIMEZONE = ZoneInfo("Asia/Tehran")
Clock = Callable[[], datetime]


def _today_in_tehran(context: Any) -> date:
    clock: Clock | None = None
    if isinstance(context, dict):
        candidate = context.get("clock")
        if callable(candidate):
            clock = candidate

    current = clock() if clock is not None else datetime.now(TEHRAN_TIMEZONE)
    if current.tzinfo is None:
        current = current.replace(tzinfo=TEHRAN_TIMEZONE)
    return current.astimezone(TEHRAN_TIMEZONE).date()


class ApiModel(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class TravelMode(StrEnum):
    FLIGHT = "flight"
    TRAIN = "train"
    BUS = "bus"


class SearchIntent(StrEnum):
    BEST = "best"
    CHEAPEST = "cheapest"
    FASTEST = "fastest"


class PassengerCounts(ApiModel):
    adults: int = Field(default=1, ge=1, le=9)
    children: int = Field(default=0, ge=0, le=8)
    infants: int = Field(default=0, ge=0, le=8)

    @model_validator(mode="after")
    def validate_counts(self) -> Self:
        if self.adults + self.children + self.infants > 9:
            raise ValueError("The total passenger count cannot exceed 9.")
        if self.infants > self.adults:
            raise ValueError("Each infant must be accompanied by an adult.")
        return self

    @property
    def total(self) -> int:
        return self.adults + self.children + self.infants


class FlightSearchPreferences(ApiModel):
    mode: Literal[TravelMode.FLIGHT]
    nonstop_only: bool = False
    fare_type: Literal["system", "charter"] | None = None


class TrainSearchPreferences(ApiModel):
    mode: Literal[TravelMode.TRAIN]
    exclusive_compartment: bool = False
    passenger_type: Literal["family", "female", "male"] = "family"
    vehicle_transport: bool = False


class BusSearchPreferences(ApiModel):
    mode: Literal[TravelMode.BUS]
    seat_selection_required: bool = False


TravelSearchPreferences = Annotated[
    FlightSearchPreferences | TrainSearchPreferences | BusSearchPreferences,
    Field(discriminator="mode"),
]


class SearchRequest(ApiModel):
    mode: TravelMode
    origin: str = Field(min_length=2, max_length=64, examples=["THR"])
    destination: str = Field(min_length=2, max_length=64, examples=["MHD"])
    departure_date: date
    return_date: date | None = None
    passengers: PassengerCounts = Field(default_factory=PassengerCounts)
    preferences: TravelSearchPreferences | None = None
    intent: SearchIntent = SearchIntent.BEST

    @field_validator("origin", "destination")
    @classmethod
    def normalize_location(cls, value: str) -> str:
        normalized = " ".join(value.split())
        return normalized.upper() if normalized.isascii() else normalized

    @model_validator(mode="after")
    def validate_route_and_dates(self, info: ValidationInfo) -> Self:
        if self.origin.casefold() == self.destination.casefold():
            raise ValueError("Origin and destination must be different.")
        if (
            self.return_date is not None
            and self.return_date <= self.departure_date
        ):
            raise ValueError("Return date must be after departure date.")
        if self.preferences is not None and self.preferences.mode is not self.mode:
            raise ValueError("Search preferences must match the selected travel mode.")
        if (
            self.mode in {TravelMode.TRAIN, TravelMode.BUS}
            and (self.passengers.children > 0 or self.passengers.infants > 0)
        ):
            raise ValueError(
                "Child and infant pricing is not verified for train or bus searches."
            )
        if self.departure_date < _today_in_tehran(info.context):
            raise ValueError("Departure date cannot be in the past.")
        return self
