from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from app.adapters.shared.http import AsyncJsonHttpClient


class FlyTodayHttpClient:
    """Async boundary for FlyToday's verified public web-client APIs."""

    def __init__(self, *, timeout_seconds: float = 5.0) -> None:
        self._transport = AsyncJsonHttpClient(
            provider_label="فلای‌تودی",
            timeout_seconds=timeout_seconds,
            default_headers={
                "Accept": "application/json",
                "Accept-Language": "fa",
                "Content-Type": "application/json",
                "Origin": "https://www.flytodayir.com",
                "Referer": "https://www.flytodayir.com/",
                "User-Agent": "Mozilla/5.0 TorobTravelComparison/1.0",
                "X-App": "www.flytodayir.com",
                "x-currency": "IRR",
                "x-origin": "https://www.flytodayir.com",
            },
        )

    async def request_json(
        self,
        url: str,
        *,
        method: str = "GET",
        payload: Mapping[str, Any] | None = None,
        query: Mapping[str, Any] | None = None,
        path: str,
        headers: Mapping[str, str] | None = None,
    ) -> Any:
        request_headers = {"X-Path": path}
        if headers is not None:
            request_headers.update(headers)
        return await self._transport.request_json(
            url,
            method=method,
            payload=payload,
            query=query,
            headers=request_headers,
        )

    async def aclose(self) -> None:
        await self._transport.aclose()
