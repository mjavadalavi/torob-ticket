from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from app.adapters.shared.http import AsyncJsonHttpClient


class BookingHttpClient:
    """Async boundary for Booking.ir's verified flight APIs."""

    def __init__(self, *, timeout_seconds: float = 5.0) -> None:
        self._transport = AsyncJsonHttpClient(
            provider_label="بوکینگ",
            timeout_seconds=timeout_seconds,
            default_headers={
                "Accept": "application/json",
                "Content-Type": "application/json",
                "Origin": "https://www.booking.ir",
                "Referer": "https://www.booking.ir/",
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
            url, method=method, payload=payload, query=query
        )

    async def aclose(self) -> None:
        await self._transport.aclose()
