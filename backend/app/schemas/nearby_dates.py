from __future__ import annotations

from datetime import date
from enum import StrEnum

from pydantic import Field

from app.domain.offer import Money
from app.domain.travel import ApiModel, TravelMode
from app.schemas.search import ProviderFailure


class NearbyDateStatus(StrEnum):
    AVAILABLE = "available"
    SOLD_OUT = "sold_out"
    AVAILABILITY_UNKNOWN = "availability_unknown"
    PROVIDER_UNAVAILABLE = "provider_unavailable"
    PAST = "past"


class NearbyDateOption(ApiModel):
    date: date
    offset_days: int = Field(ge=-2, le=2)
    status: NearbyDateStatus
    minimum_price: Money | None = None
    offer_count: int = Field(default=0, ge=0)
    providers_queried: int = Field(default=0, ge=0)
    providers_succeeded: int = Field(default=0, ge=0)
    provider_failures: list[ProviderFailure] = Field(default_factory=list)


class NearbyDatesResponse(ApiModel):
    mode: TravelMode
    origin: str
    destination: str
    selected_date: date
    dates: list[NearbyDateOption] = Field(min_length=5, max_length=5)
