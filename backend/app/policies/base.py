from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass

from app.domain.offer import NormalizedOffer, OfferGroup, RecommendationReason
from app.domain.travel import SearchIntent


@dataclass(frozen=True, slots=True)
class RankingContext:
    minimum_price: int
    maximum_price: int
    minimum_duration: int | None
    maximum_duration: int | None

    @staticmethod
    def inverse(value: int, minimum: int, maximum: int) -> float:
        if minimum == maximum:
            return 1.0
        return 1 - ((value - minimum) / (maximum - minimum))

    def price_score(self, amount: int) -> float:
        return self.inverse(amount, self.minimum_price, self.maximum_price)

    def duration_score(self, duration_minutes: int | None) -> float | None:
        if (
            duration_minutes is None
            or self.minimum_duration is None
            or self.maximum_duration is None
        ):
            return None
        return self.inverse(
            duration_minutes,
            self.minimum_duration,
            self.maximum_duration,
        )


def context_for(groups: list[OfferGroup]) -> RankingContext:
    seller_offers = [offer for group in groups for offer in group.seller_offers]
    prices = [offer.price.amount for offer in seller_offers]
    durations = [
        offer.duration_minutes
        for offer in seller_offers
        if offer.duration_minutes is not None
    ]
    return RankingContext(
        min(prices),
        max(prices),
        min(durations) if durations else None,
        max(durations) if durations else None,
    )


@dataclass(frozen=True, slots=True)
class ScoredOffer:
    score: float
    offer: OfferGroup
    recommended_seller_offer: NormalizedOffer
    reasons: list[RecommendationReason]


class RankingPolicy(ABC):
    @property
    @abstractmethod
    def intent(self) -> SearchIntent:
        raise NotImplementedError

    @abstractmethod
    def score(self, group: OfferGroup, context: RankingContext) -> ScoredOffer:
        raise NotImplementedError
