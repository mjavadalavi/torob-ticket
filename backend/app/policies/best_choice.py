from app.domain.capabilities import Capability
from app.domain.offer import NormalizedOffer, OfferGroup, RecommendationReason
from app.domain.travel import SearchIntent
from app.policies.base import RankingContext, RankingPolicy, ScoredOffer


class BestChoicePolicy(RankingPolicy):
    @property
    def intent(self) -> SearchIntent:
        return SearchIntent.BEST

    def score(self, group: OfferGroup, context: RankingContext) -> ScoredOffer:
        candidates = [
            self._score_seller_offer(offer, context)
            for offer in group.seller_offers
        ]
        score, seller_offer, reasons = max(
            candidates,
            key=lambda candidate: (
                candidate[0],
                -candidate[1].price.amount,
                candidate[1].id,
            ),
        )
        return ScoredOffer(score, group, seller_offer, reasons[:4])

    @staticmethod
    def _score_seller_offer(
        offer: NormalizedOffer,
        context: RankingContext,
    ) -> tuple[float, NormalizedOffer, list[RecommendationReason]]:
        price_score = context.price_score(offer.price.amount)
        duration_score = context.duration_score(offer.duration_minutes)
        trust_score = offer.seller.rating / 5 if offer.seller.rating is not None else None
        protection_score = sum(
            capability in offer.capabilities
            for capability in (
                Capability.TOROB_GUARANTEE,
                Capability.REFUND_RULES,
                Capability.TOROB_PAY,
            )
        ) / 3

        # Missing duration or reputation is unknown, not a zero-quality signal.
        # Renormalizing active weights prevents incomplete provider data from
        # being treated as the worst possible value.
        weighted_components = [(0.40, price_score), (0.15, protection_score)]
        if duration_score is not None:
            weighted_components.append((0.25, duration_score))
        if trust_score is not None:
            weighted_components.append((0.20, trust_score))
        active_weight = sum(weight for weight, _ in weighted_components)
        score = (
            sum(weight * value for weight, value in weighted_components)
            / active_weight
            * 100
        )

        reasons: list[RecommendationReason] = []
        if price_score >= 0.65:
            reasons.append(RecommendationReason.LOW_PRICE)
        if duration_score is not None and duration_score >= 0.65:
            reasons.append(RecommendationReason.SHORT_TRAVEL_TIME)
        if offer.attributes.stops == 0:
            reasons.append(RecommendationReason.DIRECT)
        if trust_score is not None and trust_score >= 0.85:
            reasons.append(RecommendationReason.HIGH_SELLER_TRUST)
        if Capability.TOROB_GUARANTEE in offer.capabilities:
            reasons.append(RecommendationReason.TOROB_GUARANTEE)
        if Capability.REFUND_RULES in offer.capabilities:
            reasons.append(RecommendationReason.REFUND_RULES)
        return score, offer, reasons
