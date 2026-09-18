from __future__ import annotations

from typing import Annotated, Literal

from pydantic import AnyHttpUrl, Field, model_validator

from app.domain.travel import ApiModel, TravelMode


class OfferAttributes(ApiModel):
    operator: str = Field(min_length=1, max_length=100)
    operator_code: str | None = Field(default=None, min_length=1, max_length=40)
    operator_logo_url: AnyHttpUrl | None = None
    operator_logo_alt: str | None = Field(default=None, min_length=1, max_length=140)
    operator_logo_fallback: str | None = Field(
        default=None,
        min_length=1,
        max_length=4,
    )
    service_number: str | None = Field(default=None, max_length=40)
    vehicle_class: str | None = Field(default=None, max_length=80)
    ticket_type: str | None = Field(default=None, max_length=40)
    stops: int | None = Field(default=None, ge=0, le=20)
    baggage_allowance_kg: int | None = Field(default=None, ge=0, le=200)

    @model_validator(mode="after")
    def populate_logo_accessibility_metadata(self) -> OfferAttributes:
        self.operator_logo_alt = (
            self.operator_logo_alt or f"نشان شرکت {self.operator}"
        )
        visible = "".join(
            character for character in self.operator if character.isalnum()
        )
        self.operator_logo_fallback = (
            self.operator_logo_fallback or visible[:2] or "؟"
        )
        return self


class FlightDetails(ApiModel):
    mode: Literal[TravelMode.FLIGHT]
    origin_airport_code: str = Field(min_length=3, max_length=4)
    destination_airport_code: str = Field(min_length=3, max_length=4)
    airline: str = Field(min_length=1, max_length=100)
    flight_number: str = Field(min_length=1, max_length=20)
    fare_type: Literal["system", "charter"]
    cabin_class: str = Field(min_length=1, max_length=40)
    baggage_allowance_kg: int | None = Field(default=None, ge=0, le=200)


class TrainDetails(ApiModel):
    mode: Literal[TravelMode.TRAIN]
    railway_company: str = Field(min_length=1, max_length=100)
    train_number: str = Field(min_length=1, max_length=20)
    class_name: str = Field(min_length=1, max_length=80)
    compartment_capacity: int | None = Field(default=None, ge=1, le=12)
    private_compartment_available: bool | None = None
    women_only_available: bool | None = None
    vehicle_transport_available: bool | None = None


class BusDetails(ApiModel):
    mode: Literal[TravelMode.BUS]
    origin_terminal: str = Field(min_length=1, max_length=120)
    destination_terminal: str = Field(min_length=1, max_length=120)
    company: str = Field(min_length=1, max_length=100)
    service_number: str | None = Field(default=None, min_length=1, max_length=40)
    bus_class: str = Field(min_length=1, max_length=80)
    seat_selection_available: bool | None = None
    capacity: int | None = Field(default=None, ge=1, le=100)
    cancellation_policy: str | None = Field(default=None, max_length=240)


TravelDetails = Annotated[
    FlightDetails | TrainDetails | BusDetails,
    Field(discriminator="mode"),
]
