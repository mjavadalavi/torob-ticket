from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from app.adapters.shared.http import AsyncJsonHttpClient


class MrBilitHttpClient:
    """Async boundary for MrBilit's verified public web-client APIs."""

    def __init__(self, *, timeout_seconds: float = 5.0) -> None:
        self._transport = AsyncJsonHttpClient(
            provider_label="مستربلیط",
            timeout_seconds=timeout_seconds,
            default_headers={
                "Accept": "application/json",
                "Accept-Language": "fa",
                "Origin": "https://mrbilit.com",
                "Referer": "https://mrbilit.com/",
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
        json_patch: bool = False,
    ) -> Any:
        headers = (
            {"Content-Type": "application/json-patch+json"}
            if json_patch
            else None
        )
        return await self._transport.request_json(
            url,
            method=method,
            payload=payload,
            query=query,
            headers=headers,
        )

    async def aclose(self) -> None:
        await self._transport.aclose()
