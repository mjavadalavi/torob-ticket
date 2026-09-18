from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Sequence

from app.domain.offer import OfferDetails, ProviderOffer, Seller
from app.domain.travel import SearchRequest, TravelMode
from app.ports.redirect_provider import RedirectProvider


class TravelAdapter(RedirectProvider, ABC):
    """Port implemented by each provider and travel-mode integration."""

    @property
    @abstractmethod
    def mode(self) -> TravelMode:
        raise NotImplementedError

    @property
    @abstractmethod
    def provider(self) -> str:
        raise NotImplementedError

    @property
    @abstractmethod
    def seller(self) -> Seller:
        raise NotImplementedError

    @abstractmethod
    async def search(self, request: SearchRequest) -> Sequence[ProviderOffer]:
        raise NotImplementedError

    @abstractmethod
    async def get_details(self, offer_id: str) -> OfferDetails:
        raise NotImplementedError


class AdapterFactory:
    """Registry and factory for adapters, keyed by travel mode and provider."""

    def __init__(self) -> None:
        self._adapters: dict[TravelMode, dict[str, TravelAdapter]] = {}

    def register(self, adapter: TravelAdapter) -> None:
        adapters_for_mode = self._adapters.setdefault(adapter.mode, {})
        if adapter.provider in adapters_for_mode:
            raise ValueError(
                f"Adapter already registered for {adapter.mode.value}/{adapter.provider}."
            )
        adapters_for_mode[adapter.provider] = adapter

    def adapters_for(self, mode: TravelMode) -> tuple[TravelAdapter, ...]:
        return tuple(self._adapters.get(mode, {}).values())

    def get(self, mode: TravelMode, provider: str) -> TravelAdapter | None:
        return self._adapters.get(mode, {}).get(provider)
