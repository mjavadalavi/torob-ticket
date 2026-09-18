from __future__ import annotations

from pydantic import Field

from app.domain.location import TravelLocation
from app.domain.travel import ApiModel, TravelMode


class LocationProviderFailure(ApiModel):
    provider: str
    message: str


class LocationSearchResponse(ApiModel):
    mode: TravelMode
    query: str
    total: int = Field(ge=0)
    providers_queried: int = Field(ge=0)
    providers_succeeded: int = Field(ge=0)
    provider_failures: list[LocationProviderFailure] = Field(default_factory=list)
    locations: list[TravelLocation]

