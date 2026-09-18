from __future__ import annotations

from collections.abc import Iterable

from app.domain.offer import OfferGroup, RecommendationReason
from app.domain.travel import SearchIntent
from app.policies import BestChoicePolicy, CheapestPolicy, FastestPolicy, RankingPolicy
from app.policies.base import context_for


class OfferRankingService:
    def __init__(self, policies: Iterable[RankingPolicy] | None = None) -> None:
        registered = policies or (BestChoicePolicy(), CheapestPolicy(), FastestPolicy())
        self._policies = {policy.intent: policy for policy in registered}

    def rank(self, groups: list[OfferGroup], intent: SearchIntent) -> list[OfferGroup]:
        if not groups:
            return []
        policy = self._policies.get(intent)
        if policy is None:
            raise ValueError(f"No ranking policy is registered for {intent.value}.")
        context = context_for(groups)
        scored = [policy.score(group, context) for group in groups]
        scored.sort(
            key=lambda item: (
                -item.score,
                item.recommended_seller_offer.price.amount,
                item.recommended_seller_offer.duration_minutes
                if item.recommended_seller_offer.duration_minutes is not None
                else float("inf"),
            )
        )
        return [
            item.offer.model_copy(
                update={
                    "origin": item.recommended_seller_offer.origin,
                    "destination": item.recommended_seller_offer.destination,
                    "departure_at": item.recommended_seller_offer.departure_at,
                    "arrival_at": item.recommended_seller_offer.arrival_at,
                    "duration_minutes": item.recommended_seller_offer.duration_minutes,
                    "attributes": item.recommended_seller_offer.attributes,
                    "mode_details": item.recommended_seller_offer.mode_details,
                    "recommended_seller_offer_id": item.recommended_seller_offer.id,
                    "recommended_price": item.recommended_seller_offer.price,
                    "recommended_capabilities": item.recommended_seller_offer.capabilities,
                    "rank": index,
                    "score": round(item.score, 2),
                    "recommendation_reasons": item.reasons,
                    "recommendation_summary": self._summary(
                        item.reasons,
                        item.recommended_seller_offer.seller.name,
                    ),
                }
            )
            for index, item in enumerate(scored, start=1)
        ]

    @staticmethod
    def _summary(reasons: list[RecommendationReason], seller_name: str) -> str:
        labels = {
            RecommendationReason.LOW_PRICE: "قیمت مناسب",
            RecommendationReason.LOWEST_PRICE: "کمترین قیمت نهایی",
            RecommendationReason.SHORT_TRAVEL_TIME: "مدت سفر کوتاه",
            RecommendationReason.SHORTEST_TRAVEL_TIME: "کوتاه‌ترین مدت سفر",
            RecommendationReason.DIRECT: "سفر مستقیم",
            RecommendationReason.HIGH_SELLER_TRUST: "فروشنده با امتیاز بالا",
            RecommendationReason.TOROB_GUARANTEE: "تضمین ترب",
            RecommendationReason.REFUND_RULES: "قوانین استرداد شفاف",
        }
        readable = [labels[reason] for reason in reasons]
        if not readable:
            return f"پیشنهاد {seller_name} با داده‌های قابل‌مقایسهٔ موجود انتخاب شده است."
        if len(readable) == 1:
            explanation = readable[0]
        else:
            explanation = "، ".join(readable[:-1]) + " و " + readable[-1]
        return f"پیشنهاد {seller_name}: {explanation}."
