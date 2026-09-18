from __future__ import annotations

import asyncio
from datetime import date

import pytest
from app.core.errors import AdapterUnavailableError, SearchQueueFullError
from app.domain.search_job import SearchJobStatus
from app.domain.travel import SearchRequest, TravelMode
from app.repositories.search_job_store import InMemorySearchJobStore
from app.schemas.search import SearchResponse
from app.services.search_jobs import AsyncSearchJobService


def request() -> SearchRequest:
    return SearchRequest(
        mode=TravelMode.FLIGHT,
        origin="THR",
        destination="MHD",
        departure_date=date(2030, 1, 15),
    )


class BlockingOrchestrator:
    def __init__(self) -> None:
        self.started = asyncio.Event()
        self.release = asyncio.Event()

    async def search(
        self,
        payload: SearchRequest,
        *,
        search_id: str | None = None,
    ) -> SearchResponse:
        assert search_id is not None
        self.started.set()
        await self.release.wait()
        return SearchResponse(
            search_id=search_id,
            mode=payload.mode,
            intent=payload.intent,
            total=0,
            providers_queried=1,
            providers_succeeded=1,
            offers=[],
        )


class FailingOrchestrator:
    def __init__(self, error: Exception) -> None:
        self.error = error

    async def search(self, *_args, **_kwargs) -> SearchResponse:
        raise self.error


async def wait_for_terminal(
    service: AsyncSearchJobService,
    search_id: str,
) -> SearchJobStatus:
    for _ in range(100):
        status = await service.get_status(search_id)
        if status.status in {SearchJobStatus.COMPLETED, SearchJobStatus.FAILED}:
            return status.status
        await asyncio.sleep(0)
    raise AssertionError("Search job did not reach a terminal state.")


@pytest.mark.asyncio
async def test_service_exposes_queued_running_and_completed_with_one_stable_id() -> None:
    orchestrator = BlockingOrchestrator()
    service = AsyncSearchJobService(
        orchestrator=orchestrator,  # type: ignore[arg-type]
        store=InMemorySearchJobStore(),
        search_id_factory=lambda: "src_00000000000000000000000000000000",
    )

    accepted = await service.submit(request())
    assert accepted.status is SearchJobStatus.QUEUED
    assert (await service.get_status(accepted.search_id)).status is SearchJobStatus.QUEUED

    await orchestrator.started.wait()
    assert (await service.get_status(accepted.search_id)).status is SearchJobStatus.RUNNING

    orchestrator.release.set()
    assert await wait_for_terminal(service, accepted.search_id) is SearchJobStatus.COMPLETED
    completed = await service.get_status(accepted.search_id)
    assert completed.result is not None
    assert completed.result.search_id == accepted.search_id
    assert completed.error is None
    await service.aclose()


@pytest.mark.asyncio
async def test_service_concurrency_limit_leaves_later_work_queued() -> None:
    orchestrator = BlockingOrchestrator()
    identifiers = iter(
        (
            "src_00000000000000000000000000000000",
            "src_11111111111111111111111111111111",
        )
    )
    service = AsyncSearchJobService(
        orchestrator=orchestrator,  # type: ignore[arg-type]
        store=InMemorySearchJobStore(),
        max_concurrent_jobs=1,
        search_id_factory=lambda: next(identifiers),
    )

    first = await service.submit(request())
    await orchestrator.started.wait()
    second = await service.submit(request())
    await asyncio.sleep(0)

    assert (await service.get_status(first.search_id)).status is SearchJobStatus.RUNNING
    assert (await service.get_status(second.search_id)).status is SearchJobStatus.QUEUED

    orchestrator.release.set()
    assert await wait_for_terminal(service, first.search_id) is SearchJobStatus.COMPLETED
    assert await wait_for_terminal(service, second.search_id) is SearchJobStatus.COMPLETED
    await service.aclose()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("error", "code", "message", "retryable"),
    (
        (
            AdapterUnavailableError("جزئیات خصوصی فروشنده"),
            "adapter_unavailable",
            "سرویس‌های فروش بلیت موقتاً در دسترس نیستند. دوباره تلاش کنید.",
            True,
        ),
        (
            RuntimeError("secret provider stack detail"),
            "search_failed",
            "جست‌وجو کامل نشد. دوباره تلاش کنید.",
            True,
        ),
    ),
)
async def test_service_exposes_only_sanitized_failure_metadata(
    error: Exception,
    code: str,
    message: str,
    retryable: bool,
) -> None:
    service = AsyncSearchJobService(
        orchestrator=FailingOrchestrator(error),  # type: ignore[arg-type]
        store=InMemorySearchJobStore(),
        search_id_factory=lambda: "src_00000000000000000000000000000000",
    )

    accepted = await service.submit(request())
    assert await wait_for_terminal(service, accepted.search_id) is SearchJobStatus.FAILED
    failed = await service.get_status(accepted.search_id)

    assert failed.result is None
    assert failed.error is not None
    assert failed.error.model_dump() == {
        "code": code,
        "message": message,
        "retryable": retryable,
    }
    assert "secret" not in failed.error.message
    assert "secret" not in failed.error.message
    await service.aclose()


@pytest.mark.asyncio
async def test_service_rejects_admission_when_bounded_store_has_only_active_jobs() -> None:
    orchestrator = BlockingOrchestrator()
    identifiers = iter(
        (
            "src_00000000000000000000000000000000",
            "src_11111111111111111111111111111111",
        )
    )
    service = AsyncSearchJobService(
        orchestrator=orchestrator,  # type: ignore[arg-type]
        store=InMemorySearchJobStore(max_entries=1),
        search_id_factory=lambda: next(identifiers),
    )
    await service.submit(request())

    with pytest.raises(SearchQueueFullError):
        await service.submit(request())

    await service.aclose()
