from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from app.domain.search_job import SearchJobFailure, SearchJobStatus
from app.domain.travel import SearchIntent, TravelMode
from app.ports.search_job_store import SearchJobCapacityError
from app.repositories.search_job_store import InMemorySearchJobStore
from app.schemas.search import SearchResponse


class FakeMonotonicClock:
    def __init__(self) -> None:
        self.value = 0.0

    def __call__(self) -> float:
        return self.value

    def advance(self, seconds: float) -> None:
        self.value += seconds


class FakeWallClock:
    def __init__(self) -> None:
        self.value = datetime(2030, 1, 1, tzinfo=timezone.utc)

    def __call__(self) -> datetime:
        current = self.value
        self.value += timedelta(seconds=1)
        return current


def empty_result(search_id: str) -> SearchResponse:
    return SearchResponse(
        search_id=search_id,
        mode=TravelMode.FLIGHT,
        intent=SearchIntent.BEST,
        total=0,
        providers_queried=1,
        providers_succeeded=1,
        offers=[],
    )


@pytest.mark.asyncio
async def test_store_applies_atomic_state_transitions() -> None:
    store = InMemorySearchJobStore(wall_clock=FakeWallClock())

    queued = await store.create("src_00000000000000000000000000000000")
    running = await store.mark_running(queued.search_id)
    completed = await store.mark_completed(
        queued.search_id,
        empty_result(queued.search_id),
    )

    assert queued.status is SearchJobStatus.QUEUED
    assert running is not None and running.status is SearchJobStatus.RUNNING
    assert completed is not None and completed.status is SearchJobStatus.COMPLETED
    assert completed.result is not None
    assert completed.result.search_id == queued.search_id
    assert completed.error is None
    assert completed.created_at < completed.updated_at

    unchanged = await store.mark_failed(
        queued.search_id,
        SearchJobFailure(code="late_failure", message="Late failure.", retryable=False),
    )
    assert unchanged is None
    assert await store.get(queued.search_id) == completed


@pytest.mark.asyncio
async def test_store_requires_result_to_retain_job_identifier() -> None:
    store = InMemorySearchJobStore()
    await store.create("src_00000000000000000000000000000000")
    await store.mark_running("src_00000000000000000000000000000000")

    with pytest.raises(ValueError, match="retain"):
        await store.mark_completed(
            "src_00000000000000000000000000000000",
            empty_result("src_11111111111111111111111111111111"),
        )


@pytest.mark.asyncio
async def test_store_ttl_is_bounded_and_polling_does_not_extend_it() -> None:
    clock = FakeMonotonicClock()
    store = InMemorySearchJobStore(
        ttl_seconds=10,
        monotonic_clock=clock,
    )
    search_id = "src_00000000000000000000000000000000"
    await store.create(search_id)
    await store.mark_running(search_id)
    await store.mark_completed(search_id, empty_result(search_id))

    clock.advance(9)
    assert await store.get(search_id) is not None
    clock.advance(1)
    assert await store.get(search_id) is None


@pytest.mark.asyncio
async def test_store_does_not_expire_active_work() -> None:
    clock = FakeMonotonicClock()
    store = InMemorySearchJobStore(
        ttl_seconds=10,
        monotonic_clock=clock,
    )
    queued_id = "src_00000000000000000000000000000000"
    running_id = "src_11111111111111111111111111111111"
    await store.create(queued_id)
    await store.create(running_id)
    await store.mark_running(running_id)

    clock.advance(20)

    assert (await store.get(queued_id)).status is SearchJobStatus.QUEUED
    assert (await store.get(running_id)).status is SearchJobStatus.RUNNING


@pytest.mark.asyncio
async def test_store_never_evicts_active_jobs_to_exceed_capacity() -> None:
    store = InMemorySearchJobStore(max_entries=2)
    first = "src_00000000000000000000000000000000"
    second = "src_11111111111111111111111111111111"
    third = "src_22222222222222222222222222222222"
    await store.create(first)
    await store.create(second)

    with pytest.raises(SearchJobCapacityError):
        await store.create(third)

    await store.mark_failed(
        first,
        SearchJobFailure(code="search_failed", message="Failed.", retryable=True),
    )
    assert (await store.create(third)).search_id == third
    assert await store.get(first) is None
    assert await store.get(second) is not None
