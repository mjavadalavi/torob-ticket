from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

from app.domain.offer import NormalizedOffer, ProviderOffer

if TYPE_CHECKING:
    from app.ports.travel_adapter import TravelAdapter


class OfferNormalizerPort(Protocol):
    def normalize(
        self,
        *,
        adapter: TravelAdapter,
        provider_offer: ProviderOffer,
    ) -> NormalizedOffer: ...
