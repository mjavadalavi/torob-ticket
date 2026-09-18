from __future__ import annotations

import sys
from collections.abc import AsyncIterator
from pathlib import Path

import pytest_asyncio
from httpx import ASGITransport, AsyncClient

BACKEND_ROOT = Path(__file__).resolve().parents[2] / "backend"
sys.path.insert(0, str(BACKEND_ROOT))

from app.domain.travel import TravelMode
from app.main import create_app
from app.ports.travel_adapter import AdapterFactory
from app.repositories.offer_repository import InMemoryOfferRepository
from app.repositories.search_job_store import InMemorySearchJobStore
from app.services.location_search import LocationSearchService
from app.services.nearby_dates import NearbyDateSearchService
from app.services.normalization import OfferNormalizer
from app.services.offer_grouping import OfferGroupingService
from app.services.offer_ranking import OfferRankingService
from app.services.search_jobs import AsyncSearchJobService
from app.services.search_orchestrator import SearchOrchestrator
from fakes import FakeTravelAdapter


@pytest_asyncio.fixture
async def client() -> AsyncIterator[AsyncClient]:
    application = create_app()
    factory = AdapterFactory()
    for mode in TravelMode:
        factory.register(FakeTravelAdapter(mode=mode, provider="test_a"))
        factory.register(
            FakeTravelAdapter(mode=mode, provider="test_b", price_delta=50_000)
        )
    orchestrator = SearchOrchestrator(
        adapter_factory=factory,
        repository=InMemoryOfferRepository(),
        normalizer=OfferNormalizer(),
        grouping_service=OfferGroupingService(),
        ranking_service=OfferRankingService(),
        redirect_hosts_by_provider={
            "test_a": ("www.alibaba.ir",),
            "test_b": ("www.alibaba.ir",),
        },
    )
    application.state.search_orchestrator = orchestrator
    application.state.nearby_date_search_service = NearbyDateSearchService(
        orchestrator=orchestrator,
    )
    application.state.search_job_store = InMemorySearchJobStore()
    search_job_service = AsyncSearchJobService(
        orchestrator=orchestrator,
        store=application.state.search_job_store,
    )
    application.state.search_job_service = search_job_service
    application.state.adapter_factory = factory
    application.state.location_search_service = LocationSearchService(
        adapter_factory=factory,
    )
    transport = ASGITransport(app=application)
    async with AsyncClient(transport=transport, base_url="http://testserver") as http_client:
        yield http_client
    await search_job_service.aclose()
