from __future__ import annotations

from app.adapters.shared.context import ExpiringLruStore
from app.core.errors import ResourceNotFoundError
from app.domain.offer import OfferDetails, ProviderOffer


class PayanehaOfferStore:
    """Bounded context for Payaneha result redirects and details."""

    def __init__(self, *, offer_ttl_seconds: int, max_entries: int) -> None:
        self._redirects = ExpiringLruStore[str, str](
            ttl_seconds=offer_ttl_seconds, max_entries=max_entries
        )
        self._details = ExpiringLruStore[str, OfferDetails](
            ttl_seconds=offer_ttl_seconds, max_entries=max_entries
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

    async def get_details(self, offer_id: str) -> OfferDetails:
        details = self._details.get(offer_id)
        if details is None:
            raise ResourceNotFoundError("جزئیات پیشنهاد پایانه‌ها پیدا نشد.")
        return details

    def build_redirect_url(self, source_offer_id: str) -> str:
        redirect = self._redirects.get(source_offer_id)
        if redirect is None:
            raise ResourceNotFoundError("پیوند پیشنهاد پایانه‌ها پیدا نشد.")
        return redirect
