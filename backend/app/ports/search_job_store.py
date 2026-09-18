from __future__ import annotations

from typing import Protocol

from app.domain.search_job import SearchJobFailure, SearchJobRecord
from app.schemas.search import SearchResponse


class SearchJobCapacityError(Exception):
    """Raised when all bounded store slots belong to active searches."""


class SearchJobStore(Protocol):
    """Atomic state storage for short-lived asynchronous searches."""

    async def create(self, search_id: str) -> SearchJobRecord: ...

    async def mark_running(self, search_id: str) -> SearchJobRecord | None: ...

    async def mark_completed(
        self,
        search_id: str,
        result: SearchResponse,
    ) -> SearchJobRecord | None: ...

    async def mark_failed(
        self,
        search_id: str,
        error: SearchJobFailure,
    ) -> SearchJobRecord | None: ...

    async def get(self, search_id: str) -> SearchJobRecord | None: ...

