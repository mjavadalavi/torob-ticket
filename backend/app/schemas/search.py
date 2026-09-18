from __future__ import annotations

from pydantic import Field

from app.domain.offer import OfferGroup
from app.domain.travel import ApiModel, SearchIntent, TravelMode


class ProviderFailure(ApiModel):
    provider: str
    message: str


class SearchLegResponse(ApiModel):
    total: int = Field(ge=0)
    providers_queried: int = Field(ge=0)
    providers_succeeded: int = Field(ge=0)
    provider_failures: list[ProviderFailure] = Field(default_factory=list)
    offers: list[OfferGroup]


class SearchResponse(ApiModel):
    search_id: str
    mode: TravelMode
    intent: SearchIntent
    total: int = Field(ge=0)
    providers_queried: int = Field(ge=0)
    providers_succeeded: int = Field(ge=0)
    provider_failures: list[ProviderFailure] = Field(default_factory=list)
    offers: list[OfferGroup]
    return_leg: SearchLegResponse | None = None
