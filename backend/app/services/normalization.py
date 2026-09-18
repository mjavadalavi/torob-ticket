from __future__ import annotations

from collections.abc import Mapping
from hashlib import sha256

from app.domain.offer import NormalizedOffer, ProviderOffer
from app.domain.travel import TravelMode
from app.ports.travel_adapter import TravelAdapter
from app.services.journey_identity import (
    DEFAULT_JOURNEY_IDENTITY_STRATEGIES,
    JourneyIdentityStrategy,
)


def _stable_id(prefix: str, value: str) -> str:
    return f"{prefix}_{sha256(value.encode('utf-8')).hexdigest()[:20]}"


class OfferNormalizer:
    def __init__(
        self,
        strategies: Mapping[TravelMode, JourneyIdentityStrategy] | None = None,
    ) -> None:
        self._strategies = strategies or DEFAULT_JOURNEY_IDENTITY_STRATEGIES

    def normalize(
        self,
        *,
        adapter: TravelAdapter,
        provider_offer: ProviderOffer,
    ) -> NormalizedOffer:
        if provider_offer.mode_details.mode is not adapter.mode:
            raise ValueError(
                "Adapter mode does not match the provider offer's typed details."
            )
        duration_minutes = (
            int(
                (provider_offer.arrival_at - provider_offer.departure_at).total_seconds()
                // 60
            )
            if provider_offer.arrival_at is not None
            else None
        )
        journey_key = self._journey_key(adapter.mode, provider_offer)
        seller_offer_key = (
            f"{adapter.mode.value}|{adapter.provider}|{provider_offer.source_offer_id}"
        )
        return NormalizedOffer(
            id=_stable_id("sel", seller_offer_key),
            source_offer_id=provider_offer.source_offer_id,
            provider=adapter.provider,
            mode=adapter.mode,
            seller=adapter.seller,
            origin=provider_offer.origin,
            destination=provider_offer.destination,
            departure_at=provider_offer.departure_at,
            arrival_at=provider_offer.arrival_at,
            duration_minutes=duration_minutes,
            price=provider_offer.price,
            attributes=provider_offer.attributes,
            mode_details=provider_offer.mode_details,
            capabilities=provider_offer.capabilities,
            remaining_seats=provider_offer.remaining_seats,
            cancellation_summary=provider_offer.cancellation_summary,
            refundable=provider_offer.refundable,
            last_updated_at=provider_offer.last_updated_at,
            redirect_provider=adapter.provider,
            redirect_url=adapter.build_redirect_url(provider_offer.source_offer_id),
            journey_key=journey_key,
        )

    def _journey_key(self, mode: TravelMode, offer: ProviderOffer) -> str:
        strategy = self._strategies.get(mode)
        if strategy is None:
            raise ValueError(
                f"No journey identity strategy is registered for {mode.value}."
            )
        return "|".join((mode.value, *strategy.components(offer)))


def stable_group_id(journey_key: str) -> str:
    return _stable_id("off", journey_key)
