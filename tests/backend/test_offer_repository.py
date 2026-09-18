from __future__ import annotations

from datetime import date

import pytest
from app.domain.travel import SearchRequest, TravelMode
from app.repositories import offer_repository as repository_module
from app.repositories.offer_repository import InMemoryOfferRepository
from app.services.normalization import OfferNormalizer
from app.services.offer_grouping import OfferGroupingService
from fakes import FakeTravelAdapter


async def _offer_groups():
    adapter = FakeTravelAdapter(mode=TravelMode.FLIGHT, provider="test_a")
    request = SearchRequest(
        mode=TravelMode.FLIGHT,
        origin="THR",
        destination="MHD",
        departure_date=date(2030, 1, 15),
    )
    provider_offers = await adapter.search(request)
    normalizer = OfferNormalizer()
    normalized = [
        normalizer.normalize(adapter=adapter, provider_offer=offer)
        for offer in provider_offers
    ]
    return OfferGroupingService().group(normalized, passenger_count=1)


@pytest.mark.asyncio
async def test_repository_enforces_capacity_and_evicts_the_least_recently_used(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    now = [100.0]
    monkeypatch.setattr(repository_module, "monotonic", lambda: now[0])
    groups = await _offer_groups()
    repository = InMemoryOfferRepository(ttl_seconds=10, max_entries=2)

    await repository.save_all(groups[:2])
    assert await repository.get(groups[0].id) == groups[0]
    await repository.save_all([groups[2]])

    assert await repository.get(groups[1].id) is None
    assert await repository.get(groups[0].id) == groups[0]
    assert await repository.get(groups[2].id) == groups[2]

    now[0] = 111.0
    assert await repository.get(groups[0].id) is None
    assert await repository.get(groups[2].id) is None


@pytest.mark.asyncio
async def test_repository_rejects_one_search_larger_than_its_capacity() -> None:
    groups = await _offer_groups()
    repository = InMemoryOfferRepository(max_entries=2)

    with pytest.raises(ValueError, match="repository capacity"):
        await repository.save_all(groups)
