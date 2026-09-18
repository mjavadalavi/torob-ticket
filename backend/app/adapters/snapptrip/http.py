from __future__ import annotations

from collections.abc import Mapping
from typing import Any
from uuid import uuid4

from app.adapters.shared.http import AsyncJsonHttpClient


class SnappTripHttpClient:
    """Async HTTP boundary using SnappTrip's public web-client headers."""

    def __init__(self, *, timeout_seconds: float = 5.0) -> None:
        self._transport = AsyncJsonHttpClient(
            provider_label="اسنپ‌تریپ",
            timeout_seconds=timeout_seconds,
            default_headers={
                "Accept": "application/json",
                "Accept-Language": "fa",
                "Origin": "https://www.snapptrip.com",
                "Referer": "https://www.snapptrip.com/",
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
        flight_api: bool = False,
    ) -> Any:
        headers: dict[str, str] = {}
        if flight_api:
            headers["User-Tracking-Key"] = str(uuid4())
            headers["channel"] = "website"
        return await self._transport.request_json(
            url,
            method=method,
            payload=payload,
            query=query,
            headers=headers or None,
        )

    async def aclose(self) -> None:
        await self._transport.aclose()
