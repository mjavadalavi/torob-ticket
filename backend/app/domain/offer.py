from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from pydantic import AnyHttpUrl, Field, model_validator

from app.domain.capabilities import Capability
from app.domain.itinerary import OfferAttributes, TravelDetails
from app.domain.travel import ApiModel, TravelMode


class Currency(StrEnum):
    IRT = "IRT"


class RecommendationReason(StrEnum):
    LOW_PRICE = "low_price"
    LOWEST_PRICE = "lowest_price"
    SHORT_TRAVEL_TIME = "short_travel_time"
    SHORTEST_TRAVEL_TIME = "shortest_travel_time"
    DIRECT = "direct"
    HIGH_SELLER_TRUST = "high_seller_trust"
    TOROB_GUARANTEE = "torob_guarantee"
    REFUND_RULES = "refund_rules"


class Money(ApiModel):
    amount: int = Field(ge=0, description="Whole tomans; no decimal values.")
    currency: Currency = Currency.IRT


class Seller(ApiModel):
    id: str = Field(pattern=r"^[a-z0-9_-]+$")
    name: str = Field(min_length=1, max_length=80)
    rating: float | None = Field(default=None, ge=0, le=5)
    review_count: int | None = Field(default=None, ge=0)
    logo_url: AnyHttpUrl | None = None
    logo_alt: str | None = Field(default=None, min_length=1, max_length=120)
    logo_fallback: str | None = Field(default=None, min_length=1, max_length=4)

    @model_validator(mode="after")
    def populate_logo_accessibility_metadata(self) -> Seller:
        self.logo_alt = self.logo_alt or f"نشان فروشنده {self.name}"
        self.logo_fallback = self.logo_fallback or _brand_fallback(self.name)
        return self


def _brand_fallback(name: str) -> str:
    visible = "".join(character for character in name if character.isalnum())
    return visible[:2] or "؟"


class ProviderOffer(ApiModel):
    """Provider-neutral staging model returned by a verified OTA adapter."""

    # Some verified OTA proposal tokens are signed, opaque payloads and can be
    # several kilobytes long (Alibaba bus is one example). We keep them only in
    # memory and expose hashed public IDs for our own routes.
    source_offer_id: str = Field(min_length=1, max_length=20_000)
    origin: str
    destination: str
    departure_at: datetime
    arrival_at: datetime | None = None
    price: Money
    attributes: OfferAttributes
    mode_details: TravelDetails
    capabilities: list[Capability] = Field(default_factory=list)
    remaining_seats: int | None = Field(default=None, ge=0)
    cancellation_summary: str | None = Field(default=None, max_length=240)
    refundable: bool | None = None
    last_updated_at: datetime

    @model_validator(mode="after")
    def validate_offer(self) -> ProviderOffer:
        for value in (self.departure_at, self.arrival_at, self.last_updated_at):
            if value is None:
                continue
            if value.tzinfo is None:
                raise ValueError("Offer timestamps must include a timezone.")
        if self.arrival_at is not None and self.arrival_at <= self.departure_at:
            raise ValueError("Arrival time must be after departure time.")
        self.capabilities = list(dict.fromkeys(self.capabilities))
        return self


class OfferDetails(ApiModel):
    # Adapters initially keep their opaque provider token here in memory. The
    # orchestrator replaces it with our stable public seller-offer ID before a
    # response leaves the application boundary.
    seller_offer_id: str
    mode: TravelMode
    attributes: OfferAttributes
    mode_details: TravelDetails
    capabilities: list[Capability] = Field(default_factory=list)
    remaining_seats: int | None = Field(default=None, ge=0)
    cancellation_summary: str | None = None
    refundable: bool | None = None
    last_updated_at: datetime


class NormalizedOffer(ApiModel):
    id: str
    # Provider proposal tokens may be signed and several kilobytes long. They
    # are required for provider follow-up calls, but must never be serialized
    # into search or offer responses.
    source_offer_id: str = Field(
        min_length=1,
        max_length=20_000,
        exclude=True,
        repr=False,
    )
    provider: str = Field(pattern=r"^[a-z0-9_-]+$")
    mode: TravelMode
    seller: Seller
    origin: str
    destination: str
    departure_at: datetime
    arrival_at: datetime | None = None
    duration_minutes: int | None = Field(default=None, gt=0)
    price: Money
    attributes: OfferAttributes
    mode_details: TravelDetails
    capabilities: list[Capability]
    remaining_seats: int | None = Field(default=None, ge=0)
    cancellation_summary: str | None = None
    refundable: bool | None = None
    last_updated_at: datetime
    # Redirects must be resolved through the preview endpoint so scheme and
    # hostname checks cannot be bypassed by clients.
    redirect_provider: str = Field(
        pattern=r"^[a-z0-9_-]+$",
        exclude=True,
        repr=False,
    )
    redirect_url: AnyHttpUrl = Field(exclude=True, repr=False)
    journey_key: str = Field(exclude=True, repr=False)


class OfferGroup(ApiModel):
    id: str
    mode: TravelMode
    passenger_count: int = Field(ge=1, le=9)
    origin: str
    destination: str
    departure_at: datetime
    arrival_at: datetime | None = None
    duration_minutes: int | None = Field(default=None, gt=0)
    attributes: OfferAttributes
    mode_details: TravelDetails
    available_capabilities: list[Capability]
    lowest_price: Money
    seller_count: int = Field(ge=1)
    seller_offers: list[NormalizedOffer] = Field(min_length=1)
    # Ranking is always based on one concrete seller offer. Group-level
    # availability and the lowest price remain useful comparison aggregates,
    # but must never be combined to imply that the cheapest seller provides a
    # capability advertised only by another seller.
    recommended_seller_offer_id: str
    recommended_price: Money
    recommended_capabilities: list[Capability]
    rank: int | None = Field(default=None, ge=1)
    score: float | None = Field(default=None, ge=0, le=100)
    recommendation_reasons: list[RecommendationReason] = Field(default_factory=list)
    recommendation_summary: str | None = None
