from __future__ import annotations

from datetime import date

import pytest
from app.core.errors import AdapterUnavailableError
from app.domain.travel import SearchRequest, TravelMode
from app.ports.travel_adapter import AdapterFactory
from app.repositories.offer_repository import InMemoryOfferRepository
from app.services.nearby_dates import NearbyDateSearchService
from app.services.normalization import OfferNormalizer
from app.services.offer_grouping import OfferGroupingService
from app.services.offer_ranking import OfferRankingService
from app.services.search_orchestrator import SearchOrchestrator
from fakes import FakeTravelAdapter
from httpx import AsyncClient


def _payload() -> dict[str, object]:
    return {
        "mode": "train",
        "origin": "تهران",
        "destination": "اصفهان",
        "departure_date": "2030-01-15",
        "passengers": {"adults": 1, "children": 0, "infants": 0},
        "intent": "best",
    }


@pytest.mark.asyncio
async def test_nearby_dates_returns_five_real_price_summaries(
    client: AsyncClient,
) -> None:
    response = await client.post("/api/v1/nearby-dates", json=_payload())

    assert response.status_code == 200
    body = response.json()
    assert body["mode"] == "train"
    assert body["origin"] == "تهران"
    assert body["destination"] == "اصفهان"
    assert body["selected_date"] == "2030-01-15"
    assert [item["offset_days"] for item in body["dates"]] == [-2, -1, 0, 1, 2]
    assert [item["date"] for item in body["dates"]] == [
        "2030-01-13",
        "2030-01-14",
        "2030-01-15",
        "2030-01-16",
        "2030-01-17",
    ]
    assert {item["status"] for item in body["dates"]} == {"available"}
    assert all(item["minimum_price"]["amount"] == 1_300_000 for item in body["dates"])
    assert all(item["providers_succeeded"] == 2 for item in body["dates"])


class DateAwareAdapter(FakeTravelAdapter):
    async def search(self, request: SearchRequest):
        if request.departure_date == date(2030, 1, 14):
            return ()
        if request.departure_date == date(2030, 1, 16):
            raise AdapterUnavailableError("provider is unavailable")
        return await super().search(request)


def _service_for(adapter: FakeTravelAdapter) -> NearbyDateSearchService:
    factory = AdapterFactory()
    factory.register(adapter)
    orchestrator = SearchOrchestrator(
        adapter_factory=factory,
        repository=InMemoryOfferRepository(),
        normalizer=OfferNormalizer(),
        grouping_service=OfferGroupingService(),
        ranking_service=OfferRankingService(),
        redirect_hosts_by_provider={"test_a": ("www.alibaba.ir",)},
    )
    return NearbyDateSearchService(
        orchestrator=orchestrator,
        today_provider=lambda: date(2030, 1, 14),
    )


@pytest.mark.asyncio
async def test_nearby_dates_distinguishes_past_sold_out_and_provider_failure() -> None:
    service = _service_for(
        DateAwareAdapter(mode=TravelMode.TRAIN, provider="test_a")
    )
    request = SearchRequest(
        mode=TravelMode.TRAIN,
        origin="تهران",
        destination="اصفهان",
        departure_date=date(2030, 1, 15),
    )

    result = await service.search(request)

    assert [item.status.value for item in result.dates] == [
        "past",
        "sold_out",
        "available",
        "provider_unavailable",
        "available",
    ]
    assert result.dates[0].minimum_price is None
    assert result.dates[1].providers_succeeded == 1
    assert result.dates[1].offer_count == 0
    assert result.dates[2].minimum_price is not None
    assert result.dates[3].minimum_price is None
    assert result.dates[3].providers_queried == 1
    assert result.dates[3].providers_succeeded == 0
    assert [failure.provider for failure in result.dates[3].provider_failures] == [
        "test_a"
    ]


class EmptyAdapter(FakeTravelAdapter):
    async def search(self, request: SearchRequest):
        del request
        return ()


class UnavailableAdapter(FakeTravelAdapter):
    async def search(self, request: SearchRequest):
        del request
        raise AdapterUnavailableError("provider is unavailable")


class RecordingAdapter(FakeTravelAdapter):
    def __init__(self, *, mode: TravelMode, provider: str) -> None:
        super().__init__(mode=mode, provider=provider)
        self.requests: list[SearchRequest] = []

    async def search(self, request: SearchRequest):
        self.requests.append(request)
        return await super().search(request)


@pytest.mark.asyncio
async def test_nearby_dates_probe_only_the_round_trip_departure_leg() -> None:
    adapter = RecordingAdapter(mode=TravelMode.FLIGHT, provider="test_a")
    service = _service_for(adapter)
    request = SearchRequest(
        mode=TravelMode.FLIGHT,
        origin="THR",
        destination="MHD",
        departure_date=date(2030, 1, 16),
        return_date=date(2030, 1, 22),
    )

    result = await service.search(request)

    assert len(result.dates) == 5
    assert len(adapter.requests) == 5
    assert all(item.return_date is None for item in adapter.requests)
    assert {(item.origin, item.destination) for item in adapter.requests} == {
        ("THR", "MHD")
    }
    assert {item.departure_date for item in adapter.requests} == {
        date(2030, 1, 14),
        date(2030, 1, 15),
        date(2030, 1, 16),
        date(2030, 1, 17),
        date(2030, 1, 18),
    }


@pytest.mark.asyncio
async def test_nearby_date_does_not_claim_sold_out_after_partial_failure() -> None:
    factory = AdapterFactory()
    factory.register(EmptyAdapter(mode=TravelMode.BUS, provider="answered_empty"))
    factory.register(
        UnavailableAdapter(mode=TravelMode.BUS, provider="failed_provider")
    )
    orchestrator = SearchOrchestrator(
        adapter_factory=factory,
        repository=InMemoryOfferRepository(),
        normalizer=OfferNormalizer(),
        grouping_service=OfferGroupingService(),
        ranking_service=OfferRankingService(),
        redirect_hosts_by_provider={
            "answered_empty": ("www.alibaba.ir",),
            "failed_provider": ("www.alibaba.ir",),
        },
    )
    service = NearbyDateSearchService(
        orchestrator=orchestrator,
        today_provider=lambda: date(2030, 1, 13),
    )
    request = SearchRequest(
        mode=TravelMode.BUS,
        origin="بم",
        destination="کرمان",
        departure_date=date(2030, 1, 15),
    )

    result = await service.search(request)

    assert {item.status.value for item in result.dates} == {
        "availability_unknown"
    }
    assert all(item.providers_queried == 2 for item in result.dates)
    assert all(item.providers_succeeded == 1 for item in result.dates)
    assert all(item.minimum_price is None for item in result.dates)
