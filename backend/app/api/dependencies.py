from __future__ import annotations

from fastapi import Request

from app.services.location_search import LocationSearchService
from app.services.nearby_dates import NearbyDateSearchService
from app.services.provider_support import ProviderSupportService
from app.services.search_jobs import AsyncSearchJobService
from app.services.search_orchestrator import SearchOrchestrator


def get_orchestrator(request: Request) -> SearchOrchestrator:
    return request.app.state.search_orchestrator


def get_location_search_service(request: Request) -> LocationSearchService:
    return request.app.state.location_search_service


def get_nearby_date_search_service(request: Request) -> NearbyDateSearchService:
    return request.app.state.nearby_date_search_service


def get_provider_support_service(request: Request) -> ProviderSupportService:
    return request.app.state.provider_support_service


def get_search_job_service(request: Request) -> AsyncSearchJobService:
    return request.app.state.search_job_service
