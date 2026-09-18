from __future__ import annotations

import asyncio
import logging
from collections.abc import Callable
from datetime import date, datetime, timedelta

from app.core.errors import AdapterUnavailableError
from app.domain.travel import TEHRAN_TIMEZONE, SearchRequest
from app.schemas.nearby_dates import (
    NearbyDateOption,
    NearbyDatesResponse,
    NearbyDateStatus,
)
from app.services.search_orchestrator import SearchOrchestrator

logger = logging.getLogger(__name__)


class NearbyDateSearchService:
    """Probe a five-day window without manufacturing fares or availability."""

    def __init__(
        self,
        *,
        orchestrator: SearchOrchestrator,
        max_concurrent_dates: int = 3,
        today_provider: Callable[[], date] | None = None,
    ) -> None:
        self._orchestrator = orchestrator
        self._search_admission = asyncio.Semaphore(max(1, max_concurrent_dates))
        self._today_provider = today_provider or (
            lambda: datetime.now(TEHRAN_TIMEZONE).date()
        )

    async def search(self, request: SearchRequest) -> NearbyDatesResponse:
        today = self._today_provider()

        async def probe(offset_days: int) -> NearbyDateOption:
            candidate_date = request.departure_date + timedelta(days=offset_days)
            if candidate_date < today:
                return NearbyDateOption(
                    date=candidate_date,
                    offset_days=offset_days,
                    status=NearbyDateStatus.PAST,
                )

            candidate_request = request.model_copy(
                update={
                    "departure_date": candidate_date,
                    # Nearby-date pricing is an outbound-leg probe. The return
                    # date must not make adapters perform a second-leg search.
                    "return_date": None,
                }
            )
            try:
                async with self._search_admission:
                    result = await self._orchestrator.search(
                        candidate_request,
                        persist_offers=False,
                        tolerate_provider_unavailability=True,
                    )
            except AdapterUnavailableError:
                logger.info(
                    "Nearby-date providers are unavailable",
                    extra={
                        "mode": request.mode.value,
                        "origin": request.origin,
                        "destination": request.destination,
                        "departure_date": candidate_date.isoformat(),
                    },
                )
                return NearbyDateOption(
                    date=candidate_date,
                    offset_days=offset_days,
                    status=NearbyDateStatus.PROVIDER_UNAVAILABLE,
                )

            if result.providers_succeeded == 0:
                return NearbyDateOption(
                    date=candidate_date,
                    offset_days=offset_days,
                    status=NearbyDateStatus.PROVIDER_UNAVAILABLE,
                    providers_queried=result.providers_queried,
                    provider_failures=result.provider_failures,
                )

            minimum_price = min(
                (offer.lowest_price for offer in result.offers),
                key=lambda money: money.amount,
                default=None,
            )
            if result.offers:
                status = NearbyDateStatus.AVAILABLE
            elif result.providers_succeeded == result.providers_queried:
                status = NearbyDateStatus.SOLD_OUT
            else:
                # An empty response from the providers that did answer cannot
                # prove market-wide sell-out while another provider failed.
                status = NearbyDateStatus.AVAILABILITY_UNKNOWN

            return NearbyDateOption(
                date=candidate_date,
                offset_days=offset_days,
                status=status,
                minimum_price=minimum_price,
                offer_count=result.total,
                providers_queried=result.providers_queried,
                providers_succeeded=result.providers_succeeded,
                provider_failures=result.provider_failures,
            )

        dates = await asyncio.gather(*(probe(offset) for offset in range(-2, 3)))
        return NearbyDatesResponse(
            mode=request.mode,
            origin=request.origin,
            destination=request.destination,
            selected_date=request.departure_date,
            dates=list(dates),
        )
