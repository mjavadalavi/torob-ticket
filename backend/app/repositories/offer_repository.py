from __future__ import annotations

import asyncio
from collections import OrderedDict
from collections.abc import Iterable
from time import monotonic

from app.domain.offer import OfferGroup


class InMemoryOfferRepository:
    """Process-local cache for live search results awaiting comparison/redirect."""

    def __init__(self, *, ttl_seconds: int = 900, max_entries: int = 5_000) -> None:
        self._offers: OrderedDict[str, tuple[OfferGroup, float]] = OrderedDict()
        self._ttl_seconds = max(1, ttl_seconds)
        self._max_entries = max(1, max_entries)
        self._lock = asyncio.Lock()

    async def save_all(self, offers: Iterable[OfferGroup]) -> None:
        incoming = list(offers)
        if len(incoming) > self._max_entries:
            raise ValueError(
                "One search cannot contain more offers than the repository capacity."
            )
        async with self._lock:
            now = monotonic()
            self._purge_expired(now)
            for offer in incoming:
                self._offers[offer.id] = (offer, now + self._ttl_seconds)
                self._offers.move_to_end(offer.id)
            while len(self._offers) > self._max_entries:
                self._offers.popitem(last=False)

    async def get(self, offer_id: str) -> OfferGroup | None:
        async with self._lock:
            item = self._offers.get(offer_id)
            if item is None:
                return None
            offer, expires_at = item
            if expires_at <= monotonic():
                self._offers.pop(offer_id, None)
                return None
            self._offers.move_to_end(offer_id)
            return offer

    async def clear(self) -> None:
        async with self._lock:
            self._offers.clear()

    def _purge_expired(self, now: float) -> None:
        expired_ids = [
            offer_id
            for offer_id, (_, expires_at) in self._offers.items()
            if expires_at <= now
        ]
        for offer_id in expired_ids:
            self._offers.pop(offer_id, None)
