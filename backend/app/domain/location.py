from __future__ import annotations

from enum import StrEnum

from pydantic import Field

from app.domain.travel import ApiModel, TravelMode


class LocationKind(StrEnum):
    AIRPORT = "airport"
    RAILWAY_STATION = "railway_station"
    BUS_STATION = "bus_station"


class TravelLocation(ApiModel):
    """A provider-confirmed location that can be submitted to travel search."""

    code: str = Field(min_length=1, max_length=32)
    name: str = Field(min_length=2, max_length=120)
    mode: TravelMode
    kind: LocationKind
    popular: bool = False
    providers: list[str] = Field(min_length=1)

