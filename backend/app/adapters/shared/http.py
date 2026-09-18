from __future__ import annotations

import asyncio
import json
from collections.abc import Awaitable, Callable, Mapping
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime
from typing import Any

import httpx

from app.core.errors import AdapterUnavailableError


_RETRYABLE_STATUS_CODES = frozenset({429, 502, 503, 504})
AsyncSleep = Callable[[float], Awaitable[None]]
WallClock = Callable[[], datetime]


class AsyncJsonHttpClient:
    """Pooled, bounded JSON transport for public OTA web APIs.

    One instance should be shared by all adapters for the same provider. The
    application lifespan must call :meth:`aclose` during shutdown.
    """

    def __init__(
        self,
        *,
        provider_label: str,
        default_headers: Mapping[str, str],
        timeout_seconds: float = 5.0,
        max_concurrency: int = 8,
        max_retries: int = 1,
        retry_backoff_seconds: float = 0.1,
        transport: httpx.AsyncBaseTransport | None = None,
        sleep: AsyncSleep = asyncio.sleep,
        wall_clock: WallClock | None = None,
    ) -> None:
        total = max(0.5, timeout_seconds)
        concurrency = max(1, max_concurrency)
        self._provider_label = provider_label
        self._total_timeout_seconds = total
        self._semaphore = asyncio.Semaphore(concurrency)
        self._max_retries = max(0, max_retries)
        self._retry_backoff_seconds = max(0.0, retry_backoff_seconds)
        self._sleep = sleep
        self._wall_clock = wall_clock or (lambda: datetime.now(UTC))
        self._client = httpx.AsyncClient(
            headers=dict(default_headers),
            timeout=httpx.Timeout(
                connect=min(total, 3.0),
                read=total,
                write=min(total, 3.0),
                pool=min(total, 1.0),
            ),
            limits=httpx.Limits(
                max_connections=concurrency,
                max_keepalive_connections=max(1, concurrency // 2),
                keepalive_expiry=30.0,
            ),
            follow_redirects=False,
            transport=transport,
        )

    async def request_json(
        self,
        url: str,
        *,
        method: str = "GET",
        payload: Mapping[str, Any] | None = None,
        query: Mapping[str, Any] | None = None,
        headers: Mapping[str, str] | None = None,
    ) -> Any:
        try:
            response = await self._request_response(
                url,
                method=method,
                payload=payload,
                query=query,
                headers=headers,
            )
            return response.json()
        except asyncio.CancelledError:
            raise
        except (TimeoutError, httpx.TimeoutException) as exc:
            raise AdapterUnavailableError(
                f"زمان دریافت پاسخ از {self._provider_label} به پایان رسید."
            ) from exc
        except httpx.HTTPStatusError as exc:
            raise AdapterUnavailableError(
                f"{self._provider_label} پاسخ HTTP "
                f"{exc.response.status_code} برگرداند."
            ) from exc
        except httpx.RequestError as exc:
            raise AdapterUnavailableError(
                f"ارتباط با {self._provider_label} برقرار نشد."
            ) from exc
        except (UnicodeDecodeError, json.JSONDecodeError, ValueError) as exc:
            raise AdapterUnavailableError(
                f"پاسخ {self._provider_label} JSON معتبر نبود."
            ) from exc

    async def request_text(
        self,
        url: str,
        *,
        method: str = "GET",
        payload: Mapping[str, Any] | None = None,
        query: Mapping[str, Any] | None = None,
        headers: Mapping[str, str] | None = None,
    ) -> str:
        """Fetch a provider response whose verified contract is HTML/text."""
        try:
            response = await self._request_response(
                url,
                method=method,
                payload=payload,
                query=query,
                headers=headers,
            )
            return response.text
        except asyncio.CancelledError:
            raise
        except (TimeoutError, httpx.TimeoutException) as exc:
            raise AdapterUnavailableError(
                f"زمان دریافت پاسخ از {self._provider_label} به پایان رسید."
            ) from exc
        except httpx.HTTPStatusError as exc:
            raise AdapterUnavailableError(
                f"{self._provider_label} پاسخ HTTP "
                f"{exc.response.status_code} برگرداند."
            ) from exc
        except httpx.RequestError as exc:
            raise AdapterUnavailableError(
                f"ارتباط با {self._provider_label} برقرار نشد."
            ) from exc

    async def _request_response(
        self,
        url: str,
        *,
        method: str,
        payload: Mapping[str, Any] | None,
        query: Mapping[str, Any] | None,
        headers: Mapping[str, str] | None,
    ) -> httpx.Response:
        """Send a bounded read request with one small transient retry by default.

        Provider searches are read-only even when an OTA exposes them as POST.
        Retrying is therefore safe here, while purchase/reservation operations do
        not use this transport.  The single outer deadline includes admission,
        every attempt, and retry waiting so a rate-limited provider can never make
        the aggregate search wait without bound.
        """

        retries_used = 0
        try:
            # Include time spent waiting for our concurrency slot and backoff in
            # the total deadline. Each backoff releases the provider slot first.
            async with asyncio.timeout(self._total_timeout_seconds):
                while True:
                    try:
                        async with self._semaphore:
                            response = await self._client.request(
                                method,
                                url,
                                json=payload,
                                params=query,
                                headers=headers,
                            )
                    except httpx.RequestError:
                        if retries_used >= self._max_retries:
                            raise
                        delay = self._fallback_retry_delay(retries_used)
                        retries_used += 1
                        await self._sleep(delay)
                        continue

                    if (
                        response.status_code in _RETRYABLE_STATUS_CODES
                        and retries_used < self._max_retries
                    ):
                        delay = self._retry_delay(response, retries_used)
                        retries_used += 1
                        await self._sleep(delay)
                        continue

                    response.raise_for_status()
                    return response
        except asyncio.CancelledError:
            raise
        except (TimeoutError, httpx.TimeoutException) as exc:
            raise AdapterUnavailableError(
                f"زمان دریافت پاسخ از {self._provider_label} به پایان رسید."
            ) from exc
        except httpx.HTTPStatusError as exc:
            raise AdapterUnavailableError(
                f"{self._provider_label} پاسخ HTTP "
                f"{exc.response.status_code} برگرداند."
            ) from exc
        except httpx.RequestError as exc:
            raise AdapterUnavailableError(
                f"ارتباط با {self._provider_label} برقرار نشد."
            ) from exc

    def _retry_delay(self, response: httpx.Response, retries_used: int) -> float:
        value = response.headers.get("Retry-After", "").strip()
        if value:
            try:
                return max(0.0, float(value))
            except ValueError:
                try:
                    retry_at = parsedate_to_datetime(value)
                    if retry_at.tzinfo is None:
                        retry_at = retry_at.replace(tzinfo=UTC)
                    now = self._wall_clock()
                    if now.tzinfo is None:
                        now = now.replace(tzinfo=UTC)
                    return max(0.0, (retry_at - now.astimezone(UTC)).total_seconds())
                except (TypeError, ValueError, OverflowError):
                    pass
        return self._fallback_retry_delay(retries_used)

    def _fallback_retry_delay(self, retries_used: int) -> float:
        return self._retry_backoff_seconds * (2**retries_used)

    async def aclose(self) -> None:
        await self._client.aclose()
