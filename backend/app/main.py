from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.adapters import register_live_adapters
from app.api.router import router
from app.core.config import Settings, settings
from app.core.errors import ApplicationError
from app.ports.travel_adapter import AdapterFactory
from app.repositories.offer_repository import InMemoryOfferRepository
from app.repositories.search_job_store import InMemorySearchJobStore
from app.schemas.health import HealthResponse
from app.services.location_search import LocationSearchService
from app.services.nearby_dates import NearbyDateSearchService
from app.services.normalization import OfferNormalizer
from app.services.offer_grouping import OfferGroupingService
from app.services.offer_ranking import OfferRankingService
from app.services.provider_support import ProviderSupportService
from app.services.search_jobs import AsyncSearchJobService
from app.services.search_orchestrator import SearchOrchestrator

logger = logging.getLogger(__name__)


@asynccontextmanager
async def _application_lifespan(application: FastAPI):
    try:
        yield
    finally:
        search_job_service = getattr(application.state, "search_job_service", None)
        if search_job_service is not None:
            await search_job_service.aclose()
        resources = getattr(application.state, "adapter_resources", None)
        if resources is not None:
            await resources.aclose()


def create_app(app_settings: Settings = settings) -> FastAPI:
    if app_settings.api_worker_count != 1:
        raise RuntimeError(
            "The in-memory offer repository requires exactly one API worker. "
            "Use a shared OfferRepository implementation before scaling workers."
        )
    application = FastAPI(
        title=app_settings.project_name,
        version="1.0.0",
        lifespan=_application_lifespan,
        description=(
            "A stable comparison API for flight, train, and bus offers. "
            "Checkout remains on the selected OTA website."
        ),
    )
    application.add_middleware(
        CORSMiddleware,
        allow_origins=list(app_settings.cors_origins),
        allow_credentials=False,
        allow_methods=["GET", "POST", "OPTIONS"],
        allow_headers=["*"],
    )

    adapter_factory = AdapterFactory()
    resources = register_live_adapters(
        adapter_factory,
        timeout_seconds=app_settings.adapter_timeout_seconds,
        offer_ttl_seconds=app_settings.offer_ttl_seconds,
        max_entries=app_settings.offer_repository_max_entries,
    )
    application.state.adapter_factory = adapter_factory
    application.state.adapter_resources = resources
    application.state.provider_support_service = ProviderSupportService()
    application.state.location_search_service = LocationSearchService(
        adapter_factory=adapter_factory,
        timeout_seconds=app_settings.location_timeout_seconds,
    )
    repository = InMemoryOfferRepository(
        ttl_seconds=app_settings.offer_ttl_seconds,
        max_entries=app_settings.offer_repository_max_entries,
    )
    application.state.offer_repository = repository
    orchestrator = SearchOrchestrator(
        adapter_factory=adapter_factory,
        repository=repository,
        normalizer=OfferNormalizer(),
        grouping_service=OfferGroupingService(),
        ranking_service=OfferRankingService(),
        adapter_timeout_seconds=app_settings.adapter_timeout_seconds,
        max_concurrent_searches=app_settings.search_max_concurrency,
        search_admission_timeout_seconds=(
            app_settings.search_admission_timeout_seconds
        ),
        adapter_search_cache_ttl_seconds=min(
            app_settings.adapter_search_cache_ttl_seconds,
            float(app_settings.offer_ttl_seconds),
        ),
        adapter_search_cache_max_entries=(
            app_settings.adapter_search_cache_max_entries
        ),
        redirect_hosts_by_provider=app_settings.redirect_hosts_by_provider,
    )
    application.state.search_orchestrator = orchestrator
    application.state.nearby_date_search_service = NearbyDateSearchService(
        orchestrator=orchestrator,
    )
    application.state.search_job_store = InMemorySearchJobStore(
        ttl_seconds=app_settings.search_job_ttl_seconds,
        max_entries=app_settings.search_job_max_entries,
    )
    application.state.search_job_service = AsyncSearchJobService(
        orchestrator=orchestrator,
        store=application.state.search_job_store,
        max_concurrent_jobs=min(
            app_settings.search_job_max_concurrency,
            app_settings.search_max_concurrency,
        ),
    )

    @application.exception_handler(ApplicationError)
    async def handle_application_error(
        _request: Request,
        error: ApplicationError,
    ) -> JSONResponse:
        return JSONResponse(
            status_code=error.status_code,
            content={"error": {"code": error.code, "message": error.message}},
        )

    @application.get(
        "/health",
        tags=["operations"],
        response_model=HealthResponse,
        operation_id="healthCheck",
        summary="Check service health",
    )
    async def health() -> HealthResponse:
        return HealthResponse(status="ok", environment=app_settings.environment)

    application.include_router(router, prefix=app_settings.api_prefix, tags=["travel"])
    return application


app = create_app()
