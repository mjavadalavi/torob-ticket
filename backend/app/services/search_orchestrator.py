from __future__ import annotations

import asyncio
import logging
from collections import OrderedDict
from collections.abc import Callable, Collection, Mapping, Sequence
from dataclasses import dataclass
from time import monotonic
from urllib.parse import urlparse
from uuid import uuid4

from app.core.errors import AdapterUnavailableError, ResourceNotFoundError
from app.domain.capabilities import Capability, RefundRules, SeatMap
from app.domain.offer import NormalizedOffer, OfferDetails, OfferGroup, ProviderOffer
from app.domain.travel import SearchRequest, TravelMode
from app.ports.capabilities import SupportsRefundRules, SupportsSeatSelection
from app.ports.offer_normalizer import OfferNormalizerPort
from app.ports.offer_repository import OfferRepository
from app.ports.travel_adapter import AdapterFactory, TravelAdapter
from app.schemas.offers import RedirectPreview
from app.schemas.search import ProviderFailure, SearchLegResponse, SearchResponse
from app.services.offer_grouping import OfferGroupingService
from app.services.offer_ranking import OfferRankingService

logger = logging.getLogger(__name__)

MonotonicClock = Callable[[], float]


@dataclass(frozen=True, slots=True)
class _AdapterSearchKey:
    provider: str
    request_payload: str


@dataclass(slots=True)
class _InFlightAdapterSearch:
    task: asyncio.Task[tuple[ProviderOffer, ...]]
    waiters: int = 0


@dataclass(frozen=True, slots=True)
class _SearchLegResult:
    total: int
    providers_queried: int
    providers_succeeded: int
    provider_failures: list[ProviderFailure]
    offers: list[OfferGroup]


class _RawAdapterResultCache:
    """Bounded process-local cache for short-lived provider search results."""

    def __init__(
        self,
        *,
        ttl_seconds: float,
        max_entries: int,
        clock: MonotonicClock,
    ) -> None:
        self._items: OrderedDict[
            _AdapterSearchKey,
            tuple[tuple[ProviderOffer, ...], float],
        ] = OrderedDict()
        self._ttl_seconds = max(0.001, ttl_seconds)
        self._max_entries = max(1, max_entries)
        self._clock = clock

    def get(self, key: _AdapterSearchKey) -> tuple[ProviderOffer, ...] | None:
        item = self._items.get(key)
        if item is None:
            return None
        value, expires_at = item
        if expires_at <= self._clock():
            self._items.pop(key, None)
            return None
        self._items.move_to_end(key)
        return value

    def set(
        self,
        key: _AdapterSearchKey,
        value: tuple[ProviderOffer, ...],
    ) -> None:
        now = self._clock()
        self._purge_expired(now)
        self._items[key] = (value, now + self._ttl_seconds)
        self._items.move_to_end(key)
        while len(self._items) > self._max_entries:
            self._items.popitem(last=False)

    def discard(self, key: _AdapterSearchKey) -> None:
        self._items.pop(key, None)

    def _purge_expired(self, now: float) -> None:
        expired = [
            key for key, (_, expires_at) in self._items.items() if expires_at <= now
        ]
        for key in expired:
            self._items.pop(key, None)


class SearchOrchestrator:
    def __init__(
        self,
        *,
        adapter_factory: AdapterFactory,
        repository: OfferRepository,
        normalizer: OfferNormalizerPort,
        grouping_service: OfferGroupingService,
        ranking_service: OfferRankingService,
        adapter_timeout_seconds: float = 3.0,
        max_concurrent_searches: int = 16,
        search_admission_timeout_seconds: float = 0.1,
        adapter_search_cache_ttl_seconds: float = 30.0,
        adapter_search_cache_max_entries: int = 256,
        monotonic_clock: MonotonicClock = monotonic,
        redirect_hosts_by_provider: Mapping[str, Collection[str]],
    ) -> None:
        self._adapter_factory = adapter_factory
        self._repository = repository
        self._normalizer = normalizer
        self._grouping_service = grouping_service
        self._ranking_service = ranking_service
        self._adapter_timeout_seconds = max(0.1, adapter_timeout_seconds)
        self._search_admission = asyncio.Semaphore(max(1, max_concurrent_searches))
        self._search_admission_timeout_seconds = max(
            0.001,
            search_admission_timeout_seconds,
        )
        self._adapter_search_cache = _RawAdapterResultCache(
            ttl_seconds=adapter_search_cache_ttl_seconds,
            max_entries=adapter_search_cache_max_entries,
            clock=monotonic_clock,
        )
        self._in_flight_adapter_searches: dict[
            _AdapterSearchKey,
            _InFlightAdapterSearch,
        ] = {}
        self._redirect_hosts_by_provider = {
            provider.strip().casefold(): frozenset(
                host.strip().rstrip(".").casefold()
                for host in hosts
                if host.strip().rstrip(".")
            )
            for provider, hosts in redirect_hosts_by_provider.items()
            if provider.strip()
        }
        if not self._redirect_hosts_by_provider or any(
            not hosts for hosts in self._redirect_hosts_by_provider.values()
        ):
            raise ValueError(
                "Every redirect provider must have at least one trusted redirect hostname."
            )
        registered_providers = {
            adapter.provider.casefold()
            for mode in TravelMode
            for adapter in self._adapter_factory.adapters_for(mode)
        }
        configured_providers = set(self._redirect_hosts_by_provider)
        missing = sorted(registered_providers - configured_providers)
        if missing:
            raise ValueError(
                "Redirect allowlist must include every registered provider; "
                f"missing={missing}."
            )

    async def search(
        self,
        request: SearchRequest,
        *,
        search_id: str | None = None,
        persist_offers: bool = True,
        tolerate_provider_unavailability: bool = False,
    ) -> SearchResponse:
        try:
            await asyncio.wait_for(
                self._search_admission.acquire(),
                timeout=self._search_admission_timeout_seconds,
            )
        except TimeoutError as exc:
            raise AdapterUnavailableError(
                "ظرفیت جست‌وجوی زنده در حال حاضر تکمیل است؛ "
                "لطفاً چند لحظهٔ دیگر دوباره تلاش کنید."
            ) from exc

        try:
            return await self._search_admitted(
                request,
                search_id=search_id,
                persist_offers=persist_offers,
                tolerate_provider_unavailability=tolerate_provider_unavailability,
            )
        finally:
            self._search_admission.release()

    async def _search_admitted(
        self,
        request: SearchRequest,
        *,
        search_id: str | None = None,
        persist_offers: bool = True,
        tolerate_provider_unavailability: bool = False,
    ) -> SearchResponse:
        adapters = self._adapter_factory.adapters_for(request.mode)
        if not adapters:
            raise AdapterUnavailableError(
                "برای این نوع سفر هنوز منبع فروش زنده‌ای "
                "پیکربندی نشده است."
            )

        resolved_search_id = search_id or f"src_{uuid4().hex}"
        outbound_request = request.model_copy(update={"return_date": None})
        if request.return_date is None:
            outbound = await self._search_leg(
                request=outbound_request,
                adapters=adapters,
                search_id=resolved_search_id,
                leg="outbound",
            )
            return_leg = None
        else:
            return_request = request.model_copy(
                update={
                    "origin": request.destination,
                    "destination": request.origin,
                    "departure_date": request.return_date,
                    "return_date": None,
                }
            )
            outbound, inbound = await asyncio.gather(
                self._search_leg(
                    request=outbound_request,
                    adapters=adapters,
                    search_id=resolved_search_id,
                    leg="outbound",
                ),
                self._search_leg(
                    request=return_request,
                    adapters=adapters,
                    search_id=resolved_search_id,
                    leg="return",
                ),
            )
            return_leg = SearchLegResponse(
                total=inbound.total,
                providers_queried=inbound.providers_queried,
                providers_succeeded=inbound.providers_succeeded,
                provider_failures=inbound.provider_failures,
                offers=inbound.offers,
            )

        total_provider_successes = outbound.providers_succeeded + (
            return_leg.providers_succeeded if return_leg is not None else 0
        )
        if total_provider_successes == 0 and not tolerate_provider_unavailability:
            raise AdapterUnavailableError(
                "هیچ‌یک از منابع فروش این بخش در حال حاضر "
                "پاسخ نمی‌دهند."
            )

        if persist_offers:
            offers_to_save = list(outbound.offers)
            if return_leg is not None:
                offers_to_save.extend(return_leg.offers)
            await self._repository.save_all(offers_to_save)

        logger.info(
            "Travel search completed",
            extra={
                "search_id": resolved_search_id,
                "mode": request.mode.value,
                "outbound_result_count": outbound.total,
                "return_result_count": (
                    return_leg.total if return_leg is not None else None
                ),
                "outbound_provider_failures": len(outbound.provider_failures),
                "return_provider_failures": (
                    len(return_leg.provider_failures)
                    if return_leg is not None
                    else None
                ),
            },
        )
        return SearchResponse(
            search_id=resolved_search_id,
            mode=request.mode,
            intent=request.intent,
            total=outbound.total,
            providers_queried=outbound.providers_queried,
            providers_succeeded=outbound.providers_succeeded,
            provider_failures=outbound.provider_failures,
            offers=outbound.offers,
            return_leg=return_leg,
        )

    async def _search_leg(
        self,
        *,
        request: SearchRequest,
        adapters: Sequence[TravelAdapter],
        search_id: str,
        leg: str,
    ) -> _SearchLegResult:
        results = await asyncio.gather(
            *(self._search_adapter(adapter, request) for adapter in adapters),
            return_exceptions=True,
        )
        normalized: list[NormalizedOffer] = []
        failures: list[ProviderFailure] = []
        succeeded = 0

        for adapter, result in zip(adapters, results, strict=True):
            if isinstance(result, asyncio.CancelledError):
                raise result
            if isinstance(result, Exception):
                context = {"mode": request.mode.value, "provider": adapter.provider}
                if isinstance(result, AdapterUnavailableError):
                    logger.info(
                        "Travel adapter is unavailable: provider=%s reason=%s",
                        adapter.provider,
                        result.message,
                        extra={**context, "reason": result.message},
                    )
                else:
                    logger.error(
                        "Travel adapter search failed: provider=%s error_type=%s reason=%s",
                        adapter.provider,
                        type(result).__name__,
                        str(result),
                        exc_info=(type(result), result, result.__traceback__),
                        extra={
                            **context,
                            "error_type": type(result).__name__,
                            "reason": str(result),
                        },
                    )
                failures.append(
                    ProviderFailure(
                        provider=adapter.provider,
                        message=(
                            "امکان دریافت اطلاعات از این فروشنده "
                            "وجود ندارد."
                        ),
                    )
                )
                continue

            try:
                # A provider may return sold-out or partial-capacity rows in
                # its raw availability response. They are not valid offers for
                # this request and must not reach grouping/ranking.
                available_offers = [
                    offer
                    for offer in result
                    if offer.price.amount > 0
                    and (
                        offer.remaining_seats is None
                        or offer.remaining_seats >= request.passengers.total
                    )
                ]
                provider_normalized = [
                    self._normalizer.normalize(adapter=adapter, provider_offer=offer)
                    for offer in available_offers
                ]
            except Exception:
                logger.exception(
                    "Travel adapter returned malformed data: provider=%s",
                    adapter.provider,
                    extra={"provider": adapter.provider},
                )
                failures.append(
                    ProviderFailure(
                        provider=adapter.provider,
                        message=(
                            "اطلاعات دریافتی از این فروشنده "
                            "معتبر نبود."
                        ),
                    )
                )
                continue
            succeeded += 1
            normalized.extend(provider_normalized)

        grouped = self._grouping_service.group(
            normalized,
            passenger_count=request.passengers.total,
        )
        ranked = self._ranking_service.rank(grouped, request.intent)
        ranked = self._namespace_leg_offers(
            ranked,
            search_id=search_id,
            leg=leg,
        )
        return _SearchLegResult(
            total=len(ranked),
            providers_queried=len(adapters),
            providers_succeeded=succeeded,
            provider_failures=failures,
            offers=ranked,
        )

    @staticmethod
    def _namespace_leg_offers(
        offers: Sequence[OfferGroup],
        *,
        search_id: str,
        leg: str,
    ) -> list[OfferGroup]:
        if leg == "outbound":
            return [
                offer.model_copy(update={"id": f"{search_id}_{offer.id}"})
                for offer in offers
            ]

        namespaced: list[OfferGroup] = []
        for offer in offers:
            seller_ids = {
                seller_offer.id: f"{search_id}_{leg}_{seller_offer.id}"
                for seller_offer in offer.seller_offers
            }
            namespaced.append(
                offer.model_copy(
                    update={
                        "id": f"{search_id}_{leg}_{offer.id}",
                        "seller_offers": [
                            seller_offer.model_copy(
                                update={"id": seller_ids[seller_offer.id]}
                            )
                            for seller_offer in offer.seller_offers
                        ],
                        "recommended_seller_offer_id": seller_ids[
                            offer.recommended_seller_offer_id
                        ],
                    }
                )
            )
        return namespaced

    async def _search_adapter(
        self,
        adapter: TravelAdapter,
        request: SearchRequest,
    ) -> tuple[ProviderOffer, ...]:
        key = self._adapter_search_key(adapter=adapter, request=request)
        cached = self._adapter_search_cache.get(key)
        if cached is not None:
            return cached

        in_flight = self._in_flight_adapter_searches.get(key)
        if in_flight is None:
            task = asyncio.create_task(
                self._load_adapter_results(
                    key=key,
                    adapter=adapter,
                    request=request,
                )
            )
            in_flight = _InFlightAdapterSearch(task=task)
            self._in_flight_adapter_searches[key] = in_flight
            task.add_done_callback(
                lambda completed, search_key=key: self._adapter_search_finished(
                    search_key,
                    completed,
                )
            )

        in_flight.waiters += 1
        waiter_cancelled = False
        try:
            # A cancelled HTTP request must not cancel work still shared by a
            # nearby-date or main-results request.
            return await asyncio.shield(in_flight.task)
        except asyncio.CancelledError:
            waiter_cancelled = True
            raise
        finally:
            in_flight.waiters -= 1
            if waiter_cancelled and in_flight.waiters == 0:
                # If every interested request is gone, neither an in-flight nor
                # just-completed result should warm the cache.
                self._adapter_search_cache.discard(key)
                if not in_flight.task.done():
                    if self._in_flight_adapter_searches.get(key) is in_flight:
                        self._in_flight_adapter_searches.pop(key, None)
                    in_flight.task.cancel()

    async def _load_adapter_results(
        self,
        *,
        key: _AdapterSearchKey,
        adapter: TravelAdapter,
        request: SearchRequest,
    ) -> tuple[ProviderOffer, ...]:
        try:
            result: Sequence[ProviderOffer] = await asyncio.wait_for(
                adapter.search(request),
                timeout=self._adapter_timeout_seconds,
            )
        except TimeoutError as exc:
            raise AdapterUnavailableError(
                "زمان دریافت پاسخ این فروشنده به پایان رسید."
            ) from exc

        cached_result = tuple(result)
        self._adapter_search_cache.set(key, cached_result)
        return cached_result

    def _adapter_search_finished(
        self,
        key: _AdapterSearchKey,
        task: asyncio.Task[tuple[ProviderOffer, ...]],
    ) -> None:
        in_flight = self._in_flight_adapter_searches.get(key)
        if in_flight is not None and in_flight.task is task:
            self._in_flight_adapter_searches.pop(key, None)
        if not task.cancelled():
            # Retrieve failures even if all request waiters were cancelled.
            task.exception()

    @staticmethod
    def _adapter_search_key(
        *,
        adapter: TravelAdapter,
        request: SearchRequest,
    ) -> _AdapterSearchKey:
        # Intent is intentionally excluded: no adapter uses it, and ranking is
        # performed independently after provider results are normalized.
        request_payload = request.model_dump_json(exclude={"intent"})
        return _AdapterSearchKey(
            provider=adapter.provider,
            request_payload=request_payload,
        )

    async def get_offer(self, offer_id: str) -> OfferGroup:
        offer = await self._repository.get(offer_id)
        if offer is None:
            raise ResourceNotFoundError(
                "این نتیجه پیدا نشد یا زمان نگهداری آن "
                "به پایان رسیده است."
            )
        return offer

    async def get_offer_details(
        self,
        *,
        offer_id: str,
        seller_offer_id: str,
    ) -> OfferDetails:
        adapter, seller_offer = await self._resolve_adapter_offer(
            offer_id=offer_id,
            seller_offer_id=seller_offer_id,
        )
        details = await adapter.get_details(seller_offer.source_offer_id)
        return details.model_copy(update={"seller_offer_id": seller_offer.id})

    async def get_refund_rules(
        self,
        *,
        offer_id: str,
        seller_offer_id: str,
    ) -> RefundRules:
        adapter, seller_offer = await self._resolve_adapter_offer(
            offer_id=offer_id,
            seller_offer_id=seller_offer_id,
        )
        if Capability.REFUND_RULES not in seller_offer.capabilities:
            raise AdapterUnavailableError(
                "قانون استرداد برای این پیشنهاد تأیید نشده است."
            )
        if not isinstance(adapter, SupportsRefundRules):
            raise AdapterUnavailableError(
                "این فروشنده قانون استرداد قابل‌نمایش "
                "ارائه نمی‌کند."
            )
        rules = await adapter.get_refund_rules(seller_offer.source_offer_id)
        return rules.model_copy(update={"offer_id": seller_offer.id})

    async def get_seat_map(
        self,
        *,
        offer_id: str,
        seller_offer_id: str,
    ) -> SeatMap:
        adapter, seller_offer = await self._resolve_adapter_offer(
            offer_id=offer_id,
            seller_offer_id=seller_offer_id,
        )
        if Capability.SEAT_SELECTION not in seller_offer.capabilities:
            raise AdapterUnavailableError(
                "انتخاب صندلی برای این پیشنهاد تأیید نشده است."
            )
        if not isinstance(adapter, SupportsSeatSelection):
            raise AdapterUnavailableError(
                "این فروشنده انتخاب صندلی قابل‌نمایش "
                "ارائه نمی‌کند."
            )
        seat_map = await adapter.get_seat_map(seller_offer.source_offer_id)
        return seat_map.model_copy(update={"offer_id": seller_offer.id})

    async def _resolve_adapter_offer(
        self,
        *,
        offer_id: str,
        seller_offer_id: str,
    ) -> tuple[TravelAdapter, NormalizedOffer]:
        group = await self.get_offer(offer_id)
        seller_offer = next(
            (item for item in group.seller_offers if item.id == seller_offer_id),
            None,
        )
        if seller_offer is None:
            raise ResourceNotFoundError(
                "این فروشنده برای نتیجهٔ انتخاب‌شده پیدا نشد."
            )
        adapter = self._adapter_factory.get(seller_offer.mode, seller_offer.provider)
        if adapter is None:
            raise AdapterUnavailableError(
                "اتصال این فروشنده در حال حاضر فعال نیست."
            )
        return adapter, seller_offer

    async def preview_redirect(
        self,
        *,
        offer_id: str,
        seller_offer_id: str,
    ) -> RedirectPreview:
        _, seller_offer = await self._resolve_adapter_offer(
            offer_id=offer_id,
            seller_offer_id=seller_offer_id,
        )

        parsed = urlparse(str(seller_offer.redirect_url))
        if parsed.scheme != "https" or parsed.hostname is None:
            raise AdapterUnavailableError("پیوند فروشنده امن نیست.")
        hostname = parsed.hostname.rstrip(".").casefold()
        if seller_offer.redirect_provider != seller_offer.provider:
            raise AdapterUnavailableError(
                "هویت فروشندهٔ پیوند با پیشنهاد انتخاب‌شده یکسان نیست."
            )
        provider_hosts = self._redirect_hosts_by_provider.get(
            seller_offer.provider.casefold()
        )
        if provider_hosts is None or hostname not in provider_hosts:
            raise AdapterUnavailableError(
                "دامنهٔ پیوند برای این فروشنده در فهرست مجاز نیست."
            )
        return RedirectPreview(
            offer_id=offer_id,
            seller_offer_id=seller_offer.id,
            provider=seller_offer.provider,
            seller_id=seller_offer.seller.id,
            seller_name=seller_offer.seller.name,
            url=seller_offer.redirect_url,
            target_kind="seller_search",
            price_recheck_required=True,
        )
