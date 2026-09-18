from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Path, Query, Request, Response, status

from app.api.dependencies import (
    get_location_search_service,
    get_nearby_date_search_service,
    get_orchestrator,
    get_provider_support_service,
    get_search_job_service,
)
from app.domain.capabilities import RefundRules, SeatMap
from app.domain.offer import OfferDetails, OfferGroup
from app.domain.travel import SearchRequest, TravelMode
from app.schemas.locations import LocationSearchResponse
from app.schemas.nearby_dates import NearbyDatesResponse
from app.schemas.offers import RedirectPreview
from app.schemas.search import SearchResponse
from app.schemas.search_jobs import SearchJobAccepted, SearchJobStatusResponse
from app.services.location_search import LocationSearchService
from app.services.nearby_dates import NearbyDateSearchService
from app.services.provider_support import (
    ProviderSupportResponse,
    ProviderSupportService,
)
from app.services.search_jobs import AsyncSearchJobService
from app.services.search_orchestrator import SearchOrchestrator

router = APIRouter()


@router.get(
    "/providers",
    response_model=ProviderSupportResponse,
    operation_id="listProviderSupport",
    summary="List provider integration support",
    description=(
        "Returns the audited integration status for every requested OTA in one "
        "travel mode. This is integration eligibility, not real-time seller uptime; "
        "search responses report current failures in provider_failures."
    ),
)
async def list_provider_support(
    service: Annotated[
        ProviderSupportService,
        Depends(get_provider_support_service),
    ],
    mode: Annotated[TravelMode, Query()],
) -> ProviderSupportResponse:
    return service.list_for_mode(mode)


@router.get(
    "/locations",
    response_model=LocationSearchResponse,
    operation_id="searchLocations",
    summary="Search valid travel locations",
    description=(
        "Returns provider-confirmed origin and destination choices for the selected "
        "travel mode. No guessed or generic city list is returned."
    ),
)
async def search_locations(
    service: Annotated[LocationSearchService, Depends(get_location_search_service)],
    mode: Annotated[TravelMode, Query()],
    q: Annotated[str, Query(max_length=64)] = "",
    limit: Annotated[int, Query(ge=1, le=20)] = 10,
) -> LocationSearchResponse:
    return await service.search(mode=mode, query=q, limit=limit)


@router.post(
    "/search",
    response_model=SearchResponse,
    operation_id="searchOffers",
    status_code=status.HTTP_200_OK,
    summary="Search and compare travel offers",
    description=(
        "Queries all adapters registered for the selected travel mode, normalizes their "
        "offers, groups identical journeys, and ranks the groups by user intent."
    ),
)
async def search_offers(
    payload: SearchRequest,
    orchestrator: Annotated[SearchOrchestrator, Depends(get_orchestrator)],
) -> SearchResponse:
    return await orchestrator.search(payload)


@router.post(
    "/nearby-dates",
    response_model=NearbyDatesResponse,
    operation_id="searchNearbyDates",
    status_code=status.HTTP_200_OK,
    summary="Check prices around a selected travel date",
    description=(
        "Queries the registered live providers for the two previous dates, the "
        "selected date, and the two following dates. A date is marked sold out only "
        "when every queried provider answered successfully with no bookable offer; "
        "partial provider failures remain explicitly unknown."
    ),
)
async def search_nearby_dates(
    payload: SearchRequest,
    service: Annotated[
        NearbyDateSearchService,
        Depends(get_nearby_date_search_service),
    ],
) -> NearbyDatesResponse:
    return await service.search(payload)


@router.post(
    "/search-jobs",
    response_model=SearchJobAccepted,
    operation_id="createSearchJob",
    status_code=status.HTTP_202_ACCEPTED,
    summary="Start a background travel search",
    description=(
        "Creates a bounded background job and immediately returns its stable search "
        "identifier. Poll the job resource until it completes or fails."
    ),
    responses={
        status.HTTP_202_ACCEPTED: {
            "headers": {
                "Location": {
                    "description": "URL of the newly created search job.",
                    "schema": {"type": "string"},
                },
                "Retry-After": {
                    "description": "Suggested minimum polling delay in seconds.",
                    "schema": {"type": "integer", "minimum": 1},
                },
            }
        }
    },
)
async def create_search_job(
    payload: SearchRequest,
    request: Request,
    response: Response,
    service: Annotated[AsyncSearchJobService, Depends(get_search_job_service)],
) -> SearchJobAccepted:
    accepted = await service.submit(payload)
    response.headers["Location"] = str(
        request.url_for("get_search_job", search_id=accepted.search_id)
    )
    response.headers["Retry-After"] = "1"
    return accepted


@router.get(
    "/search-jobs/{search_id}",
    response_model=SearchJobStatusResponse,
    operation_id="getSearchJob",
    summary="Get background search status",
    description=(
        "Returns queued or running state, the normalized SearchResponse after "
        "completion, or sanitized failure metadata."
    ),
)
async def get_search_job(
    search_id: Annotated[str, Path(min_length=8, max_length=80)],
    service: Annotated[AsyncSearchJobService, Depends(get_search_job_service)],
) -> SearchJobStatusResponse:
    return await service.get_status(search_id)


@router.get(
    "/offers/{offer_id}",
    response_model=OfferGroup,
    operation_id="getOffer",
    summary="Get one grouped travel offer",
    description="Returns the journey and all currently known seller offers for comparison.",
)
async def get_offer(
    offer_id: Annotated[str, Path(min_length=5, max_length=80)],
    orchestrator: Annotated[SearchOrchestrator, Depends(get_orchestrator)],
) -> OfferGroup:
    return await orchestrator.get_offer(offer_id)


@router.get(
    "/offers/{offer_id}/details",
    response_model=OfferDetails,
    operation_id="getOfferDetails",
    summary="Get provider-backed offer details",
    description="Returns current details supplied by the selected provider.",
)
async def get_offer_details(
    offer_id: Annotated[str, Path(min_length=5, max_length=80)],
    seller_offer_id: Annotated[
        str,
        Query(min_length=5, max_length=80, description="Seller offer ID."),
    ],
    orchestrator: Annotated[SearchOrchestrator, Depends(get_orchestrator)],
) -> OfferDetails:
    return await orchestrator.get_offer_details(
        offer_id=offer_id,
        seller_offer_id=seller_offer_id,
    )


@router.get(
    "/offers/{offer_id}/refund-rules",
    response_model=RefundRules,
    operation_id="getOfferRefundRules",
    summary="Get verified refund rules",
    description="Returns refund rules supplied by the selected provider.",
)
async def get_refund_rules(
    offer_id: Annotated[str, Path(min_length=5, max_length=80)],
    seller_offer_id: Annotated[
        str,
        Query(min_length=5, max_length=80, description="Seller offer ID."),
    ],
    orchestrator: Annotated[SearchOrchestrator, Depends(get_orchestrator)],
) -> RefundRules:
    return await orchestrator.get_refund_rules(
        offer_id=offer_id,
        seller_offer_id=seller_offer_id,
    )


@router.get(
    "/offers/{offer_id}/seat-map",
    response_model=SeatMap,
    operation_id="getOfferSeatMap",
    summary="Get a verified seat map",
    description="Returns the provider seat map for offers that support selection.",
)
async def get_seat_map(
    offer_id: Annotated[str, Path(min_length=5, max_length=80)],
    seller_offer_id: Annotated[
        str,
        Query(min_length=5, max_length=80, description="Seller offer ID."),
    ],
    orchestrator: Annotated[SearchOrchestrator, Depends(get_orchestrator)],
) -> SeatMap:
    return await orchestrator.get_seat_map(
        offer_id=offer_id,
        seller_offer_id=seller_offer_id,
    )


@router.get(
    "/offers/{offer_id}/redirect",
    response_model=RedirectPreview,
    operation_id="previewOfferRedirect",
    summary="Preview an OTA redirect",
    description=(
        "Returns an external OTA destination for a selected seller offer. Current "
        "adapters return seller search pages, so the client must ask the user to "
        "recheck price and availability before checkout."
    ),
)
async def preview_redirect(
    offer_id: Annotated[str, Path(min_length=5, max_length=80)],
    seller_offer_id: Annotated[
        str,
        Query(min_length=5, max_length=80, description="Seller offer ID from search results."),
    ],
    orchestrator: Annotated[SearchOrchestrator, Depends(get_orchestrator)],
) -> RedirectPreview:
    return await orchestrator.preview_redirect(
        offer_id=offer_id,
        seller_offer_id=seller_offer_id,
    )
