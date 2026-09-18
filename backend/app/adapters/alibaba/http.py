from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from app.adapters.shared.http import AsyncJsonHttpClient


class AlibabaHttpClient:
    """Async HTTP boundary shared by verified Alibaba adapters."""

    def __init__(self, *, timeout_seconds: float = 5.0) -> None:
        self._transport = AsyncJsonHttpClient(
            provider_label="علی‌بابا",
            timeout_seconds=timeout_seconds,
            default_headers={
                "Accept": "application/json",
                "Accept-Language": "fa-IR,fa;q=0.9",
                "Origin": "https://www.alibaba.ir",
                "Referer": "https://www.alibaba.ir/",
                "User-Agent": "Mozilla/5.0 TorobTravelComparison/1.0",
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
            url,
            method=method,
            payload=payload,
            query=query,
        )

    async def aclose(self) -> None:
        await self._transport.aclose()
