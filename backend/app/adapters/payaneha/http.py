from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from app.adapters.shared.http import AsyncJsonHttpClient


class PayanehaHttpClient:
    """Async boundary for Payaneha's verified JSON and HTML endpoints."""

    def __init__(self, *, timeout_seconds: float = 5.0) -> None:
        self._transport = AsyncJsonHttpClient(
            provider_label="پایانه‌ها",
            timeout_seconds=timeout_seconds,
            default_headers={
                "Accept": "text/html,application/json",
                "Accept-Language": "fa-IR,fa;q=0.9",
                "Referer": "https://www.payaneha.com/",
                "User-Agent": "Mozilla/5.0 TorobTravelComparison/1.0",
                "X-Requested-With": "XMLHttpRequest",
            },
        )

    async def request_json(
        self,
        url: str,
        *,
        method: str = "GET",
        payload: Mapping[str, Any] | None = None,
        query: Mapping[str, Any] | None = None,
    ) -> Any:
        return await self._transport.request_json(
            url, method=method, payload=payload, query=query
        )

    async def request_text(
        self,
        url: str,
        *,
        method: str = "GET",
        payload: Mapping[str, Any] | None = None,
        query: Mapping[str, Any] | None = None,
    ) -> str:
        return await self._transport.request_text(
            url, method=method, payload=payload, query=query
        )

    async def aclose(self) -> None:
        await self._transport.aclose()
