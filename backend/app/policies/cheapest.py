from app.domain.offer import OfferGroup, RecommendationReason
from app.domain.travel import SearchIntent
from app.policies.base import RankingContext, RankingPolicy, ScoredOffer


class CheapestPolicy(RankingPolicy):
    @property
    def intent(self) -> SearchIntent:
        return SearchIntent.CHEAPEST

    def score(self, group: OfferGroup, context: RankingContext) -> ScoredOffer:
        seller_offer = min(
            group.seller_offers,
            key=lambda offer: (offer.price.amount, offer.id),
        )
        reason = (
            RecommendationReason.LOWEST_PRICE
            if seller_offer.price.amount == context.minimum_price
            else RecommendationReason.LOW_PRICE
        )
        return ScoredOffer(
            context.price_score(seller_offer.price.amount) * 100,
            group,
            seller_offer,
            [reason],
        )
