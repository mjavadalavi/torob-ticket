from __future__ import annotations

from collections.abc import Sequence
from typing import Protocol, runtime_checkable

from app.domain.location import TravelLocation


@runtime_checkable
class SupportsLocationSearch(Protocol):
    async def search_locations(
        self,
        query: str,
        *,
        limit: int = 10,
    ) -> Sequence[TravelLocation]: ...


@runtime_checkable
class SupportsCachedLocationSearch(Protocol):
    """Expose provider-confirmed locations without performing network I/O."""

    def search_cached_locations(
        self,
        query: str,
        *,
        limit: int = 10,
    ) -> Sequence[TravelLocation]: ...
