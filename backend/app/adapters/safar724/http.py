from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from app.adapters.shared.http import AsyncJsonHttpClient


class Safar724HttpClient:
    """Async boundary for Safar724's verified public JSON APIs."""

    def __init__(self, *, timeout_seconds: float = 5.0) -> None:
        self._transport = AsyncJsonHttpClient(
            provider_label="سفر ۷۲۴",
            timeout_seconds=timeout_seconds,
            default_headers={
                "Accept": "application/json",
                "Accept-Language": "fa",
                "Referer": "https://safar724.com/",
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
