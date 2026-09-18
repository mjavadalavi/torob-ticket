from __future__ import annotations

import asyncio
import logging
from collections.abc import Callable
from uuid import uuid4

from app.core.errors import (
    AdapterUnavailableError,
    ApplicationError,
    ResourceNotFoundError,
    SearchQueueFullError,
)
from app.domain.search_job import SearchJobFailure, SearchJobRecord
from app.domain.travel import SearchRequest
from app.ports.search_job_store import SearchJobCapacityError, SearchJobStore
from app.schemas.search_jobs import (
    SearchJobAccepted,
    SearchJobError,
    SearchJobStatusResponse,
)
from app.services.search_orchestrator import SearchOrchestrator

logger = logging.getLogger(__name__)
SearchIdFactory = Callable[[], str]


def _new_search_id() -> str:
    return f"src_{uuid4().hex}"


class AsyncSearchJobService:
    """Runs bounded search work outside the request/response lifecycle."""

    def __init__(
        self,
        *,
        orchestrator: SearchOrchestrator,
        store: SearchJobStore,
        max_concurrent_jobs: int = 8,
        search_id_factory: SearchIdFactory = _new_search_id,
    ) -> None:
        self._orchestrator = orchestrator
        self._store = store
        self._concurrency = asyncio.Semaphore(max(1, max_concurrent_jobs))
        self._search_id_factory = search_id_factory
        self._tasks: set[asyncio.Task[None]] = set()
        self._closed = False
        self._lifecycle_lock = asyncio.Lock()

    async def submit(self, request: SearchRequest) -> SearchJobAccepted:
        async with self._lifecycle_lock:
            if self._closed:
                raise SearchQueueFullError(
                    "Background search processing is not accepting new work."
                )

            search_id = self._search_id_factory()
            try:
                record = await self._store.create(search_id)
            except SearchJobCapacityError as exc:
                raise SearchQueueFullError(
                    "The background search queue is currently full."
                ) from exc

            task = asyncio.create_task(
                self._run(search_id=search_id, request=request),
                name=f"travel-search:{search_id}",
            )
            self._tasks.add(task)
            task.add_done_callback(self._tasks.discard)
        return SearchJobAccepted(search_id=search_id, status=record.status)

    async def get_status(self, search_id: str) -> SearchJobStatusResponse:
        record = await self._store.get(search_id)
        if record is None:
            raise ResourceNotFoundError(
                "This search job was not found or has expired."
            )
        return self._to_response(record)

    async def aclose(self) -> None:
        async with self._lifecycle_lock:
            self._closed = True
            tasks = tuple(self._tasks)
        for task in tasks:
            task.cancel()
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)

    async def _run(self, *, search_id: str, request: SearchRequest) -> None:
        try:
            async with self._concurrency:
                record = await self._store.mark_running(search_id)
                if record is None:
                    return
                result = await self._orchestrator.search(
                    request,
                    search_id=search_id,
                )
                await self._store.mark_completed(search_id, result)
        except asyncio.CancelledError:
            await self._store.mark_failed(
                search_id,
                SearchJobFailure(
                    code="search_cancelled",
                    message="جست‌وجو لغو شد. دوباره تلاش کنید.",
                    retryable=True,
                ),
            )
            raise
        except Exception as exc:
            failure = self._safe_failure(exc)
            if not isinstance(exc, ApplicationError):
                logger.exception(
                    "Background travel search failed",
                    extra={"search_id": search_id},
                )
            await self._store.mark_failed(search_id, failure)

    @staticmethod
    def _safe_failure(error: Exception) -> SearchJobFailure:
        if isinstance(error, AdapterUnavailableError):
            return SearchJobFailure(
                code=error.code,
                message="سرویس‌های فروش بلیت موقتاً در دسترس نیستند. دوباره تلاش کنید.",
                retryable=True,
            )
        if isinstance(error, ApplicationError):
            return SearchJobFailure(
                code=error.code,
                message="جست‌وجو کامل نشد. دوباره تلاش کنید.",
                retryable=error.status_code >= 500,
            )
        return SearchJobFailure(
            code="search_failed",
            message="جست‌وجو کامل نشد. دوباره تلاش کنید.",
            retryable=True,
        )

    @staticmethod
    def _to_response(record: SearchJobRecord) -> SearchJobStatusResponse:
        error = None
        if record.error is not None:
            error = SearchJobError(
                code=record.error.code,
                message=record.error.message,
                retryable=record.error.retryable,
            )
        return SearchJobStatusResponse(
            search_id=record.search_id,
            status=record.status,
            result=record.result,
            error=error,
        )
