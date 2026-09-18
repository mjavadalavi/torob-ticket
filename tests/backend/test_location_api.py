from __future__ import annotations

import asyncio

import pytest
from app.domain.location import LocationKind, TravelLocation
from app.domain.travel import TravelMode
from app.ports.travel_adapter import AdapterFactory
from app.services.location_search import LocationSearchService
from fakes import FakeTravelAdapter
from httpx import AsyncClient


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("mode", "kind"),
    [
        ("flight", "airport"),
        ("train", "railway_station"),
        ("bus", "bus_station"),
    ],
)
async def test_locations_are_mode_aware_and_merged_by_name(
    client: AsyncClient,
    mode: str,
    kind: str,
) -> None:
    response = await client.get("/api/v1/locations", params={"mode": mode})

    assert response.status_code == 200
    body = response.json()
    assert body["mode"] == mode
    assert body["providers_queried"] == 2
    assert body["providers_succeeded"] == 2
    assert body["total"] == 3
    assert body["locations"][0]["popular"] is True
    assert {location["kind"] for location in body["locations"]} == {kind}
    assert all(
        set(location["providers"]) == {"test_a", "test_b"}
        for location in body["locations"]
    )


@pytest.mark.asyncio
async def test_locations_support_persian_search(client: AsyncClient) -> None:
    response = await client.get(
        "/api/v1/locations",
        params={"mode": "flight", "q": "شی"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["query"] == "شی"
    assert [location["name"] for location in body["locations"]] == ["شیراز"]


@pytest.mark.asyncio
async def test_locations_reject_unknown_mode(client: AsyncClient) -> None:
    response = await client.get("/api/v1/locations", params={"mode": "hotel"})

    assert response.status_code == 422


class RouteLocationAdapter(FakeTravelAdapter):
    def __init__(
        self,
        *,
        provider: str,
        locations: tuple[TravelLocation, ...],
    ) -> None:
        super().__init__(mode=TravelMode.BUS, provider=provider)
        self._locations = locations

    async def search_locations(
        self,
        query: str,
        *,
        limit: int = 10,
    ) -> tuple[TravelLocation, ...]:
        del query
        return self._locations[:limit]


class BlockingCachedLocationAdapter(RouteLocationAdapter):
    def __init__(
        self,
        *,
        provider: str,
        cached_locations: tuple[TravelLocation, ...],
    ) -> None:
        super().__init__(provider=provider, locations=())
        self._cached_locations = cached_locations
        self.started = asyncio.Event()
        self.network_call_cancelled = asyncio.Event()
        self.cached_search_calls = 0

    async def search_locations(
        self,
        query: str,
        *,
        limit: int = 10,
    ) -> tuple[TravelLocation, ...]:
        del query, limit
        self.started.set()
        try:
            await asyncio.Event().wait()
        except asyncio.CancelledError:
            self.network_call_cancelled.set()
            raise
        raise AssertionError("The blocking location lookup must be cancelled.")

    def search_cached_locations(
        self,
        query: str,
        *,
        limit: int = 10,
    ) -> tuple[TravelLocation, ...]:
        del query
        self.cached_search_calls += 1
        return self._cached_locations[:limit]


def _bus_location(
    *,
    code: str,
    name: str,
    provider: str,
    popular: bool = False,
) -> TravelLocation:
    return TravelLocation(
        code=code,
        name=name,
        mode=TravelMode.BUS,
        kind=LocationKind.BUS_STATION,
        popular=popular,
        providers=[provider],
    )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("query", "expected_name", "distractor_name"),
    [
        ("بم", "بم", "بام"),
        ("کرمان", "کرمان", "کرمانشاه"),
        ("تهران", "تهران", "تهرانپارس"),
        ("اصفهان", "اصفهان", "اصفهانک"),
    ],
)
async def test_exact_persian_city_is_ranked_before_popular_fuzzy_matches(
    query: str,
    expected_name: str,
    distractor_name: str,
) -> None:
    factory = AdapterFactory()
    factory.register(
        RouteLocationAdapter(
            provider="provider_a",
            locations=(
                _bus_location(
                    code=f"{query}-a",
                    name=expected_name,
                    provider="provider_a",
                ),
                _bus_location(
                    code=f"{query}-other",
                    name=distractor_name,
                    provider="provider_a",
                    popular=True,
                ),
            ),
        )
    )
    factory.register(
        RouteLocationAdapter(
            provider="provider_b",
            locations=(
                _bus_location(
                    code=f"{query}-provider-specific-id",
                    name=expected_name,
                    provider="provider_b",
                ),
            ),
        )
    )
    service = LocationSearchService(adapter_factory=factory)

    result = await service.search(mode=TravelMode.BUS, query=query, limit=10)

    assert result.locations[0].name == expected_name
    assert result.locations[0].providers == ["provider_a", "provider_b"]
    assert [item.name for item in result.locations].count(expected_name) == 1


@pytest.mark.asyncio
async def test_provider_code_collision_does_not_merge_different_cities() -> None:
    factory = AdapterFactory()
    factory.register(
        RouteLocationAdapter(
            provider="provider_a",
            locations=(
                _bus_location(
                    code="shared-provider-code",
                    name="تهران",
                    provider="provider_a",
                ),
            ),
        )
    )
    factory.register(
        RouteLocationAdapter(
            provider="provider_b",
            locations=(
                _bus_location(
                    code="shared-provider-code",
                    name="اصفهان",
                    provider="provider_b",
                ),
            ),
        )
    )
    service = LocationSearchService(adapter_factory=factory)

    result = await service.search(mode=TravelMode.BUS, query="", limit=10)

    assert {item.name for item in result.locations} == {"تهران", "اصفهان"}


@pytest.mark.asyncio
async def test_location_timeout_uses_provider_confirmed_cached_locations() -> None:
    adapter = BlockingCachedLocationAdapter(
        provider="provider_a",
        cached_locations=(
            _bus_location(
                code="IFN",
                name="اصفهان",
                provider="provider_a",
            ),
        ),
    )
    factory = AdapterFactory()
    factory.register(adapter)
    service = LocationSearchService(adapter_factory=factory, timeout_seconds=0.1)

    result = await service.search(mode=TravelMode.BUS, query="اصفهان", limit=10)

    assert [item.name for item in result.locations] == ["اصفهان"]
    assert result.providers_succeeded == 1
    assert result.provider_failures == []
    assert adapter.cached_search_calls == 1
    assert adapter.network_call_cancelled.is_set()


@pytest.mark.asyncio
async def test_location_request_cancellation_does_not_use_cached_fallback() -> None:
    adapter = BlockingCachedLocationAdapter(
        provider="provider_a",
        cached_locations=(
            _bus_location(
                code="IFN",
                name="اصفهان",
                provider="provider_a",
            ),
        ),
    )
    factory = AdapterFactory()
    factory.register(adapter)
    service = LocationSearchService(adapter_factory=factory, timeout_seconds=60)
    request_task = asyncio.create_task(
        service.search(mode=TravelMode.BUS, query="اصفهان", limit=10)
    )
    await adapter.started.wait()

    request_task.cancel()

    with pytest.raises(asyncio.CancelledError):
        await request_task
    assert adapter.cached_search_calls == 0
    assert adapter.network_call_cancelled.is_set()
