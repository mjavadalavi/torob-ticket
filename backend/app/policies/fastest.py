from app.domain.offer import OfferGroup, RecommendationReason
from app.domain.travel import SearchIntent
from app.policies.base import RankingContext, RankingPolicy, ScoredOffer


class FastestPolicy(RankingPolicy):
    @property
    def intent(self) -> SearchIntent:
        return SearchIntent.FASTEST

    def score(self, group: OfferGroup, context: RankingContext) -> ScoredOffer:
        known_duration_offers = [
            offer for offer in group.seller_offers if offer.duration_minutes is not None
        ]
        seller_offer = (
            min(
                known_duration_offers,
                key=lambda offer: (offer.duration_minutes, offer.price.amount, offer.id),
            )
            if known_duration_offers
            else min(
                group.seller_offers,
                key=lambda offer: (offer.price.amount, offer.id),
            )
        )
        duration_score = context.duration_score(seller_offer.duration_minutes)
        if duration_score is None or context.minimum_duration is None:
            return ScoredOffer(0, group, seller_offer, [])
        reason = (
            RecommendationReason.SHORTEST_TRAVEL_TIME
            if seller_offer.duration_minutes == context.minimum_duration
            else RecommendationReason.SHORT_TRAVEL_TIME
        )
        return ScoredOffer(duration_score * 100, group, seller_offer, [reason])
