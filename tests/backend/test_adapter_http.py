from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from email.utils import format_datetime

import httpx
import pytest
from app.adapters.registry import LiveAdapterResources
from app.adapters.shared.http import AsyncJsonHttpClient
from app.adapters.shared.parsing import mapping_rows_or_raise
from app.core.errors import AdapterUnavailableError


def make_client(
    handler,
    *,
    timeout_seconds: float = 1.0,
    max_concurrency: int = 2,
    max_retries: int = 1,
    retry_backoff_seconds: float = 0.1,
    sleep=asyncio.sleep,
    wall_clock=None,
) -> AsyncJsonHttpClient:
    return AsyncJsonHttpClient(
        provider_label="test provider",
        default_headers={"Accept": "application/json"},
        timeout_seconds=timeout_seconds,
        max_concurrency=max_concurrency,
        max_retries=max_retries,
        retry_backoff_seconds=retry_backoff_seconds,
        transport=httpx.MockTransport(handler),
        sleep=sleep,
        wall_clock=wall_clock,
    )


@pytest.mark.asyncio
async def test_http_client_bounds_provider_concurrency() -> None:
    release = asyncio.Event()
    capacity_reached = asyncio.Event()
    active = 0
    peak_active = 0

    async def handler(_request: httpx.Request) -> httpx.Response:
        nonlocal active, peak_active
        active += 1
        peak_active = max(peak_active, active)
        if active == 2:
            capacity_reached.set()
        try:
            await release.wait()
            return httpx.Response(200, json={"ok": True})
        finally:
            active -= 1

    client = make_client(handler, max_concurrency=2)
    tasks = [
        asyncio.create_task(client.request_json(f"https://ota.test/{index}"))
        for index in range(6)
    ]
    try:
        await asyncio.wait_for(capacity_reached.wait(), timeout=0.5)
        await asyncio.sleep(0)
        assert peak_active == 2
        release.set()
        assert await asyncio.gather(*tasks) == [{"ok": True}] * 6
    finally:
        release.set()
        await asyncio.gather(*tasks, return_exceptions=True)
        await client.aclose()


@pytest.mark.asyncio
async def test_http_client_applies_total_deadline() -> None:
    async def handler(_request: httpx.Request) -> httpx.Response:
        await asyncio.sleep(10)
        return httpx.Response(200, json={"ok": True})

    client = make_client(handler, timeout_seconds=0.5)
    try:
        with pytest.raises(AdapterUnavailableError, match="به پایان رسید"):
            await client.request_json("https://ota.test/slow")
    finally:
        await client.aclose()


@pytest.mark.asyncio
async def test_http_client_propagates_cancellation() -> None:
    started = asyncio.Event()
    transport_cancelled = asyncio.Event()

    async def handler(_request: httpx.Request) -> httpx.Response:
        started.set()
        try:
            await asyncio.sleep(10)
        finally:
            transport_cancelled.set()
        return httpx.Response(200, json={"ok": True})

    client = make_client(handler)
    task = asyncio.create_task(client.request_json("https://ota.test/cancel"))
    try:
        await asyncio.wait_for(started.wait(), timeout=0.5)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        assert transport_cancelled.is_set()
    finally:
        if not task.done():
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)
        await client.aclose()


@pytest.mark.asyncio
async def test_http_client_retries_429_after_retry_after_seconds() -> None:
    requests = 0
    delays: list[float] = []

    async def handler(_request: httpx.Request) -> httpx.Response:
        nonlocal requests
        requests += 1
        if requests == 1:
            return httpx.Response(429, headers={"Retry-After": "2"})
        return httpx.Response(200, json={"ok": True})

    async def record_sleep(delay: float) -> None:
        delays.append(delay)

    client = make_client(handler, sleep=record_sleep)
    try:
        assert await client.request_json("https://ota.test/rate-limited") == {
            "ok": True
        }
        assert requests == 2
        assert delays == [2.0]
    finally:
        await client.aclose()


@pytest.mark.asyncio
async def test_http_client_honors_retry_after_http_date() -> None:
    requests = 0
    delays: list[float] = []
    now = datetime(2030, 1, 15, 10, 0, tzinfo=UTC)

    async def handler(_request: httpx.Request) -> httpx.Response:
        nonlocal requests
        requests += 1
        if requests == 1:
            return httpx.Response(
                503,
                headers={
                    "Retry-After": format_datetime(
                        datetime(2030, 1, 15, 10, 0, 3, tzinfo=UTC),
                        usegmt=True,
                    )
                },
            )
        return httpx.Response(200, json={"ok": True})

    async def record_sleep(delay: float) -> None:
        delays.append(delay)

    client = make_client(
        handler,
        sleep=record_sleep,
        wall_clock=lambda: now,
    )
    try:
        assert await client.request_json("https://ota.test/unavailable") == {"ok": True}
        assert requests == 2
        assert delays == [3.0]
    finally:
        await client.aclose()


@pytest.mark.asyncio
async def test_http_client_uses_bounded_backoff_for_transient_connection_error() -> None:
    requests = 0
    delays: list[float] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        nonlocal requests
        requests += 1
        if requests == 1:
            raise httpx.ConnectError("connection reset", request=request)
        return httpx.Response(200, json={"ok": True})

    async def record_sleep(delay: float) -> None:
        delays.append(delay)

    client = make_client(
        handler,
        retry_backoff_seconds=0.25,
        sleep=record_sleep,
    )
    try:
        assert await client.request_json("https://ota.test/reset") == {"ok": True}
        assert requests == 2
        assert delays == [0.25]
    finally:
        await client.aclose()


@pytest.mark.asyncio
async def test_http_client_does_not_retry_non_transient_http_error() -> None:
    requests = 0

    async def handler(_request: httpx.Request) -> httpx.Response:
        nonlocal requests
        requests += 1
        return httpx.Response(403)

    client = make_client(handler, max_retries=3)
    try:
        with pytest.raises(AdapterUnavailableError, match="HTTP 403"):
            await client.request_json("https://ota.test/forbidden")
        assert requests == 1
    finally:
        await client.aclose()


def test_non_empty_payload_without_mapping_rows_is_parse_drift() -> None:
    with pytest.raises(AdapterUnavailableError, match="schema changed"):
        mapping_rows_or_raise(
            ["unexpected", 42, None],
            invalid_message="schema changed",
        )


@pytest.mark.asyncio
async def test_live_adapter_resources_close_all_provider_pools() -> None:
    closed: list[str] = []

    class StubClient:
        def __init__(self, name: str) -> None:
            self.name = name

        async def aclose(self) -> None:
            await asyncio.sleep(0)
            closed.append(self.name)

    resources = LiveAdapterResources(
        alibaba=StubClient("alibaba"),  # type: ignore[arg-type]
        booking=StubClient("booking"),  # type: ignore[arg-type]
        flytoday=StubClient("flytoday"),  # type: ignore[arg-type]
        mrbilit=StubClient("mrbilit"),  # type: ignore[arg-type]
        payaneha=StubClient("payaneha"),  # type: ignore[arg-type]
        safar724=StubClient("safar724"),  # type: ignore[arg-type]
        snapptrip=StubClient("snapptrip"),  # type: ignore[arg-type]
    )

    await resources.aclose()

    assert set(closed) == {
        "alibaba",
        "booking",
        "flytoday",
        "mrbilit",
        "payaneha",
        "safar724",
        "snapptrip",
    }
