from __future__ import annotations

import asyncio
import logging

from app.domain.location import TravelLocation
from app.domain.travel import TravelMode
from app.ports.location_search import (
    SupportsCachedLocationSearch,
    SupportsLocationSearch,
)
from app.ports.travel_adapter import AdapterFactory
from app.schemas.locations import LocationProviderFailure, LocationSearchResponse

logger = logging.getLogger(__name__)


def _normalize(value: str) -> str:
    return (
        " ".join(value.split())
        .replace("ي", "ی")
        .replace("ك", "ک")
        .replace("\u200c", "")
        .casefold()
    )


class LocationSearchService:
    """Aggregate provider-backed location suggestions without leaking OTA UI models."""

    def __init__(
        self,
        *,
        adapter_factory: AdapterFactory,
        timeout_seconds: float = 3.0,
    ) -> None:
        self._adapter_factory = adapter_factory
        self._timeout_seconds = max(0.1, timeout_seconds)

    async def search(
        self,
        *,
        mode: TravelMode,
        query: str,
        limit: int,
    ) -> LocationSearchResponse:
        normalized_query = " ".join(query.split())
        adapters = [
            adapter
            for adapter in self._adapter_factory.adapters_for(mode)
            if isinstance(adapter, SupportsLocationSearch)
        ]

        async def query_adapter(adapter: SupportsLocationSearch):
            try:
                return await asyncio.wait_for(
                    adapter.search_locations(normalized_query, limit=limit),
                    timeout=self._timeout_seconds,
                )
            except TimeoutError:
                if not isinstance(adapter, SupportsCachedLocationSearch):
                    raise
                cached = adapter.search_cached_locations(
                    normalized_query,
                    limit=limit,
                )
                if not cached:
                    raise
                logger.info(
                    "Location adapter timed out; using its verified cache",
                    extra={"mode": mode.value, "provider": adapter.provider},
                )
                return cached

        results = await asyncio.gather(
            *(query_adapter(adapter) for adapter in adapters),
            return_exceptions=True,
        )
        failures: list[LocationProviderFailure] = []
        succeeded = 0
        merged: dict[tuple[str, str], TravelLocation] = {}

        for adapter, result in zip(adapters, results, strict=True):
            if isinstance(result, asyncio.CancelledError):
                raise result
            if isinstance(result, Exception):
                logger.info(
                    "Location adapter is unavailable",
                    extra={"mode": mode.value, "provider": adapter.provider},
                )
                failures.append(
                    LocationProviderFailure(
                        provider=adapter.provider,
                        message="دریافت فهرست شهرها از این منبع ممکن نشد.",
                    )
                )
                continue
            succeeded += 1
            for location in result:
                if location.mode is not mode:
                    continue
                # Provider codes are adapter-private identifiers. The public UI
                # submits the Persian name, so cross-provider identity must be
                # based on that neutral name instead of whichever OTA answered
                # first with a code.
                name_key = (_normalize(location.name), location.kind.value)
                current = merged.get(name_key)
                if current is None:
                    merged[name_key] = location
                    continue
                merged[name_key] = current.model_copy(
                    update={
                        "popular": current.popular or location.popular,
                        "providers": list(
                            dict.fromkeys([*current.providers, *location.providers])
                        ),
                    }
                )

        query_key = _normalize(normalized_query)

        def sort_key(item: TravelLocation) -> tuple[int, bool, str]:
            name = _normalize(item.name)
            if query_key and name == query_key:
                match_rank = 0
            elif query_key and name.startswith(query_key):
                match_rank = 1
            else:
                match_rank = 2
            return match_rank, not item.popular, item.name

        locations = sorted(
            merged.values(),
            key=sort_key,
        )[:limit]
        return LocationSearchResponse(
            mode=mode,
            query=normalized_query,
            total=len(locations),
            providers_queried=len(adapters),
            providers_succeeded=succeeded,
            provider_failures=failures,
            locations=locations,
        )
