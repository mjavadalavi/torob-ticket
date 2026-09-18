from __future__ import annotations

from collections.abc import Iterable
from typing import Protocol

from app.domain.offer import OfferGroup


class OfferRepository(Protocol):
    """Storage port for short-lived grouped offers used by follow-up actions."""

    async def save_all(self, offers: Iterable[OfferGroup]) -> None: ...

    async def get(self, offer_id: str) -> OfferGroup | None: ...
