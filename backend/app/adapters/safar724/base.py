from __future__ import annotations

from app.adapters.shared.context import ExpiringLruStore
from app.core.errors import ResourceNotFoundError
from app.domain.capabilities import RefundRules
from app.domain.offer import OfferDetails, ProviderOffer


class Safar724OfferStore:
    """Bounded offer context for Safar724 results and refund rules."""

    def __init__(self, *, offer_ttl_seconds: int, max_entries: int) -> None:
        self._redirects = ExpiringLruStore[str, str](
            ttl_seconds=offer_ttl_seconds,
            max_entries=max_entries,
        )
        self._details = ExpiringLruStore[str, OfferDetails](
            ttl_seconds=offer_ttl_seconds,
            max_entries=max_entries,
        )
        self._refund_rules = ExpiringLruStore[str, RefundRules](
            ttl_seconds=offer_ttl_seconds,
            max_entries=max_entries,
        )

    def _remember_offer(self, offer: ProviderOffer, redirect_url: str) -> None:
        self._redirects.set(offer.source_offer_id, redirect_url)
        self._details.set(
            offer.source_offer_id,
            OfferDetails(
                seller_offer_id=offer.source_offer_id,
                mode=offer.mode_details.mode,
                attributes=offer.attributes,
                mode_details=offer.mode_details,
                capabilities=offer.capabilities,
                remaining_seats=offer.remaining_seats,
                cancellation_summary=offer.cancellation_summary,
                refundable=offer.refundable,
                last_updated_at=offer.last_updated_at,
            ),
        )
        if offer.refundable is not None and offer.cancellation_summary:
            self._refund_rules.set(
                offer.source_offer_id,
                RefundRules(
                    offer_id=offer.source_offer_id,
                    refundable=offer.refundable,
                    summary=offer.cancellation_summary,
                ),
            )

    async def get_details(self, offer_id: str) -> OfferDetails:
        details = self._details.get(offer_id)
        if details is None:
            raise ResourceNotFoundError(
                "جزئیات این پیشنهاد در حافظهٔ جست‌وجوی سفر ۷۲۴ پیدا نشد."
            )
        return details

    async def get_refund_rules(self, offer_id: str) -> RefundRules:
        await self.get_details(offer_id)
        rules = self._refund_rules.get(offer_id)
        if rules is None:
            raise ResourceNotFoundError(
                "قانون استرداد این پیشنهاد سفر ۷۲۴ پیدا نشد."
            )
        return rules

    def build_redirect_url(self, source_offer_id: str) -> str:
        redirect = self._redirects.get(source_offer_id)
        if redirect is None:
            raise ResourceNotFoundError("پیوند این پیشنهاد سفر ۷۲۴ پیدا نشد.")
        return redirect
