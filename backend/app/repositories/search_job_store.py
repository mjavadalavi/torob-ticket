from __future__ import annotations

import asyncio
from collections import OrderedDict
from collections.abc import Callable
from dataclasses import replace
from datetime import UTC, datetime
from time import monotonic
from typing import ClassVar

from app.domain.search_job import (
    SearchJobFailure,
    SearchJobRecord,
    SearchJobStatus,
)
from app.ports.search_job_store import SearchJobCapacityError
from app.schemas.search import SearchResponse

MonotonicClock = Callable[[], float]
WallClock = Callable[[], datetime]


class InMemorySearchJobStore:
    """Concurrency-safe, process-local storage with fixed capacity and TTL.

    Active searches are never evicted merely to admit newer work. Once capacity is
    full, the oldest terminal record is discarded first; if every record is active,
    admission is rejected. TTL applies only after a job reaches a terminal state and
    is intentionally not extended by polling.
    """

    _TERMINAL_STATUSES: ClassVar[set[SearchJobStatus]] = {
        SearchJobStatus.COMPLETED,
        SearchJobStatus.FAILED,
    }

    def __init__(
        self,
        *,
        ttl_seconds: float = 300,
        max_entries: int = 200,
        monotonic_clock: MonotonicClock = monotonic,
        wall_clock: WallClock | None = None,
    ) -> None:
        self._ttl_seconds = max(0.001, ttl_seconds)
        self._max_entries = max(1, max_entries)
        self._monotonic_clock = monotonic_clock
        self._wall_clock = wall_clock or (lambda: datetime.now(UTC))
        self._jobs: OrderedDict[str, tuple[SearchJobRecord, float]] = OrderedDict()
        self._lock = asyncio.Lock()

    async def create(self, search_id: str) -> SearchJobRecord:
        async with self._lock:
            now = self._monotonic_clock()
            self._purge_expired(now)
            if search_id in self._jobs:
                raise ValueError(f"Duplicate search job identifier: {search_id}.")
            self._make_capacity_available()

            wall_time = self._wall_clock()
            record = SearchJobRecord(
                search_id=search_id,
                status=SearchJobStatus.QUEUED,
                created_at=wall_time,
                updated_at=wall_time,
            )
            self._jobs[search_id] = (record, now + self._ttl_seconds)
            return record

    async def mark_running(self, search_id: str) -> SearchJobRecord | None:
        return await self._transition(
            search_id,
            allowed_from={SearchJobStatus.QUEUED},
            status=SearchJobStatus.RUNNING,
        )

    async def mark_completed(
        self,
        search_id: str,
        result: SearchResponse,
    ) -> SearchJobRecord | None:
        if result.search_id != search_id:
            raise ValueError("A completed result must retain its search job identifier.")
        return await self._transition(
            search_id,
            allowed_from={SearchJobStatus.RUNNING},
            status=SearchJobStatus.COMPLETED,
            result=result,
        )

    async def mark_failed(
        self,
        search_id: str,
        error: SearchJobFailure,
    ) -> SearchJobRecord | None:
        return await self._transition(
            search_id,
            allowed_from={SearchJobStatus.QUEUED, SearchJobStatus.RUNNING},
            status=SearchJobStatus.FAILED,
            error=error,
        )

    async def get(self, search_id: str) -> SearchJobRecord | None:
        async with self._lock:
            now = self._monotonic_clock()
            self._purge_expired(now)
            stored = self._jobs.get(search_id)
            return stored[0] if stored is not None else None

    async def clear(self) -> None:
        async with self._lock:
            self._jobs.clear()

    async def _transition(
        self,
        search_id: str,
        *,
        allowed_from: set[SearchJobStatus],
        status: SearchJobStatus,
        result: SearchResponse | None = None,
        error: SearchJobFailure | None = None,
    ) -> SearchJobRecord | None:
        async with self._lock:
            now = self._monotonic_clock()
            self._purge_expired(now)
            stored = self._jobs.get(search_id)
            if stored is None:
                return None
            current, _ = stored
            if current.status not in allowed_from:
                return None
            updated = replace(
                current,
                status=status,
                updated_at=self._wall_clock(),
                result=result,
                error=error,
            )
            self._jobs[search_id] = (updated, now + self._ttl_seconds)
            return updated

    def _make_capacity_available(self) -> None:
        if len(self._jobs) < self._max_entries:
            return
        terminal_id = next(
            (
                search_id
                for search_id, (record, _) in self._jobs.items()
                if record.status in self._TERMINAL_STATUSES
            ),
            None,
        )
        if terminal_id is None:
            raise SearchJobCapacityError
        self._jobs.pop(terminal_id)

    def _purge_expired(self, now: float) -> None:
        expired_ids = [
            search_id
            for search_id, (record, expires_at) in self._jobs.items()
            if record.status in self._TERMINAL_STATUSES and expires_at <= now
        ]
        for search_id in expired_ids:
            self._jobs.pop(search_id, None)
