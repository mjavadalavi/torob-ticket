from __future__ import annotations

import asyncio
from datetime import date

import pytest
from app.core.errors import AdapterUnavailableError
from app.domain.capabilities import Capability
from app.domain.offer import Seller
from app.domain.travel import (
    FlightSearchPreferences,
    PassengerCounts,
    SearchIntent,
    SearchRequest,
    TravelMode,
)
from app.ports.travel_adapter import AdapterFactory
from app.repositories.offer_repository import InMemoryOfferRepository
from app.services.normalization import OfferNormalizer
from app.services.offer_grouping import OfferGroupingService
from app.services.offer_ranking import OfferRankingService
from app.services.search_orchestrator import SearchOrchestrator
from fakes import FakeTravelAdapter


class MixedAvailabilityAdapter(FakeTravelAdapter):
    async def search(self, request: SearchRequest):
        offers = list(await super().search(request))
        return (
            offers[0].model_copy(update={"remaining_seats": 0}),
            offers[1].model_copy(update={"remaining_seats": 1}),
            offers[2].model_copy(update={"remaining_seats": None}),
        )


class UnknownSellerRatingAdapter(FakeTravelAdapter):
    def __init__(self) -> None:
        super().__init__(mode=TravelMode.FLIGHT, provider="test_a")
        self._seller = Seller(
            id="test_a",
            name="فروشنده بدون امتیاز",
            rating=None,
            review_count=None,
        )


class UnadvertisedCapabilityAdapter(FakeTravelAdapter):
    def __init__(self) -> None:
        super().__init__(mode=TravelMode.BUS, provider="test_a")
        self.refund_calls = 0
        self.seat_map_calls = 0

    async def search(self, request: SearchRequest):
        offers = await super().search(request)
        return tuple(
            offer.model_copy(
                update={
                    "capabilities": [
                        capability
                        for capability in offer.capabilities
                        if capability
                        not in {Capability.REFUND_RULES, Capability.SEAT_SELECTION}
                    ]
                }
            )
            for offer in offers
        )

    async def get_refund_rules(self, offer_id: str):
        self.refund_calls += 1
        return await super().get_refund_rules(offer_id)

    async def get_seat_map(self, offer_id: str):
        self.seat_map_calls += 1
        return await super().get_seat_map(offer_id)


class UnsafeRedirectAdapter(FakeTravelAdapter):
    def __init__(self, redirect_url: str) -> None:
        super().__init__(mode=TravelMode.FLIGHT, provider="test_a")
        self._redirect_url = redirect_url

    def build_redirect_url(self, source_offer_id: str) -> str:
        return self._redirect_url


class SameSellerFareVariantsAdapter(FakeTravelAdapter):
    async def search(self, request: SearchRequest):
        base = (await super().search(request))[0]
        cheapest = base.model_copy(update={"capabilities": []})
        protected = base.model_copy(
            update={
                "source_offer_id": f"{base.source_offer_id}-protected",
                "price": base.price.model_copy(
                    update={"amount": base.price.amount + 200_000}
                ),
                "capabilities": [Capability.TOROB_GUARANTEE],
            }
        )
        return cheapest, protected


class MissingMetricsAdapter(UnknownSellerRatingAdapter):
    async def search(self, request: SearchRequest):
        base = (await super().search(request))[0]
        return (base.model_copy(update={"arrival_at": None}),)


class BlockingSearchAdapter(FakeTravelAdapter):
    def __init__(self) -> None:
        super().__init__(mode=TravelMode.FLIGHT, provider="test_a")
        self.search_calls = 0
        self.started = asyncio.Event()
        self.release = asyncio.Event()

    async def search(self, request: SearchRequest):
        self.search_calls += 1
        self.started.set()
        await self.release.wait()
        return await super().search(request)


class CountingSearchAdapter(FakeTravelAdapter):
    def __init__(
        self,
        *,
        mode: TravelMode = TravelMode.FLIGHT,
        provider: str = "test_a",
    ) -> None:
        super().__init__(mode=mode, provider=provider)
        self.search_calls = 0

    async def search(self, request: SearchRequest):
        self.search_calls += 1
        return await super().search(request)


class FailingFirstSearchAdapter(CountingSearchAdapter):
    async def search(self, request: SearchRequest):
        self.search_calls += 1
        if self.search_calls == 1:
            raise AdapterUnavailableError("temporary provider failure")
        return await FakeTravelAdapter.search(self, request)


class CancelledFirstSearchAdapter(CountingSearchAdapter):
    async def search(self, request: SearchRequest):
        self.search_calls += 1
        if self.search_calls == 1:
            raise asyncio.CancelledError
        return await FakeTravelAdapter.search(self, request)


class RoundTripTrackingAdapter(CountingSearchAdapter):
    def __init__(
        self,
        *,
        provider: str,
        fail_return_leg: bool = False,
    ) -> None:
        super().__init__(provider=provider)
        self.fail_return_leg = fail_return_leg
        self.requests: list[SearchRequest] = []

    async def search(self, request: SearchRequest):
        self.search_calls += 1
        self.requests.append(request)
        if self.fail_return_leg and request.origin == "MHD":
            raise AdapterUnavailableError("return leg is temporarily unavailable")
        return await FakeTravelAdapter.search(self, request)


def _orchestrator_for(adapter: FakeTravelAdapter) -> SearchOrchestrator:
    factory = AdapterFactory()
    factory.register(adapter)
    return SearchOrchestrator(
        adapter_factory=factory,
        repository=InMemoryOfferRepository(),
        normalizer=OfferNormalizer(),
        grouping_service=OfferGroupingService(),
        ranking_service=OfferRankingService(),
        redirect_hosts_by_provider={"test_a": ("www.alibaba.ir",)},
    )


@pytest.mark.asyncio
async def test_round_trip_splits_one_way_requests_and_persists_both_legs() -> None:
    healthy = RoundTripTrackingAdapter(provider="test_a")
    partially_available = RoundTripTrackingAdapter(
        provider="test_b",
        fail_return_leg=True,
    )
    factory = AdapterFactory()
    factory.register(healthy)
    factory.register(partially_available)
    repository = InMemoryOfferRepository()
    orchestrator = SearchOrchestrator(
        adapter_factory=factory,
        repository=repository,
        normalizer=OfferNormalizer(),
        grouping_service=OfferGroupingService(),
        ranking_service=OfferRankingService(),
        redirect_hosts_by_provider={
            "test_a": ("www.alibaba.ir",),
            "test_b": ("www.alibaba.ir",),
        },
    )
    request = SearchRequest(
        mode=TravelMode.FLIGHT,
        origin="THR",
        destination="MHD",
        departure_date=date(2030, 1, 15),
        return_date=date(2030, 1, 20),
        intent=SearchIntent.CHEAPEST,
    )

    result = await orchestrator.search(
        request,
        search_id="src_round_trip_contract",
    )

    assert result.return_leg is not None
    assert result.providers_queried == 2
    assert result.providers_succeeded == 2
    assert result.provider_failures == []
    assert result.return_leg.providers_queried == 2
    assert result.return_leg.providers_succeeded == 1
    assert [failure.provider for failure in result.return_leg.provider_failures] == [
        "test_b"
    ]
    assert [offer.rank for offer in result.offers] == [1, 2, 3]
    assert [offer.rank for offer in result.return_leg.offers] == [1, 2, 3]

    all_requests = healthy.requests + partially_available.requests
    assert all(item.return_date is None for item in all_requests)
    assert {
        (item.origin, item.destination, item.departure_date)
        for item in all_requests
    } == {
        ("THR", "MHD", date(2030, 1, 15)),
        ("MHD", "THR", date(2030, 1, 20)),
    }

    outbound_group_ids = {offer.id for offer in result.offers}
    return_group_ids = {offer.id for offer in result.return_leg.offers}
    assert outbound_group_ids.isdisjoint(return_group_ids)
    outbound_seller_ids = {
        seller_offer.id
        for offer in result.offers
        for seller_offer in offer.seller_offers
    }
    return_seller_ids = {
        seller_offer.id
        for offer in result.return_leg.offers
        for seller_offer in offer.seller_offers
    }
    assert outbound_seller_ids.isdisjoint(return_seller_ids)
    for offer_id in outbound_group_ids | return_group_ids:
        assert await repository.get(offer_id) is not None


@pytest.mark.asyncio
async def test_orchestrator_never_publishes_insufficient_capacity_rows() -> None:
    factory = AdapterFactory()
    factory.register(
        MixedAvailabilityAdapter(mode=TravelMode.FLIGHT, provider="test_a")
    )
    orchestrator = SearchOrchestrator(
        adapter_factory=factory,
        repository=InMemoryOfferRepository(),
        normalizer=OfferNormalizer(),
        grouping_service=OfferGroupingService(),
        ranking_service=OfferRankingService(),
        redirect_hosts_by_provider={"test_a": ("www.alibaba.ir",)},
    )

    result = await orchestrator.search(
        SearchRequest(
            mode=TravelMode.FLIGHT,
            origin="THR",
            destination="MHD",
            departure_date=date(2030, 1, 15),
            passengers=PassengerCounts(adults=2),
        )
    )

    assert result.total == 1
    assert result.offers[0].seller_offers[0].remaining_seats is None


@pytest.mark.asyncio
async def test_unknown_seller_rating_never_claims_high_seller_trust() -> None:
    orchestrator = _orchestrator_for(UnknownSellerRatingAdapter())

    result = await orchestrator.search(
        SearchRequest(
            mode=TravelMode.FLIGHT,
            origin="THR",
            destination="MHD",
            departure_date=date(2030, 1, 15),
        )
    )

    assert all(
        "high_seller_trust" not in group.recommendation_reasons
        for group in result.offers
    )


@pytest.mark.asyncio
async def test_same_provider_fare_variants_are_preserved_without_mixing_capabilities() -> None:
    orchestrator = _orchestrator_for(
        SameSellerFareVariantsAdapter(mode=TravelMode.FLIGHT, provider="test_a")
    )

    result = await orchestrator.search(
        SearchRequest(
            mode=TravelMode.FLIGHT,
            origin="THR",
            destination="MHD",
            departure_date=date(2030, 1, 15),
            intent="cheapest",
        )
    )

    assert result.total == 1
    group = result.offers[0]
    assert group.seller_count == 1
    assert len(group.seller_offers) == 2
    assert group.available_capabilities == [Capability.TOROB_GUARANTEE]
    assert group.recommended_seller_offer_id == group.seller_offers[0].id
    assert group.recommended_price == group.lowest_price
    assert group.recommended_capabilities == []


@pytest.mark.asyncio
async def test_best_choice_renormalizes_weights_when_duration_and_rating_are_unknown() -> None:
    orchestrator = _orchestrator_for(MissingMetricsAdapter())

    result = await orchestrator.search(
        SearchRequest(
            mode=TravelMode.FLIGHT,
            origin="THR",
            destination="MHD",
            departure_date=date(2030, 1, 15),
        )
    )

    assert result.offers[0].duration_minutes is None
    assert result.offers[0].seller_offers[0].seller.rating is None
    assert result.offers[0].score == 100


@pytest.mark.asyncio
async def test_search_admission_rejects_excess_work_without_unbounded_queueing() -> None:
    adapter = BlockingSearchAdapter()
    factory = AdapterFactory()
    factory.register(adapter)
    orchestrator = SearchOrchestrator(
        adapter_factory=factory,
        repository=InMemoryOfferRepository(),
        normalizer=OfferNormalizer(),
        grouping_service=OfferGroupingService(),
        ranking_service=OfferRankingService(),
        max_concurrent_searches=1,
        search_admission_timeout_seconds=0.01,
        redirect_hosts_by_provider={"test_a": ("www.alibaba.ir",)},
    )
    request = SearchRequest(
        mode=TravelMode.FLIGHT,
        origin="THR",
        destination="MHD",
        departure_date=date(2030, 1, 15),
    )

    first_search = asyncio.create_task(orchestrator.search(request))
    await adapter.started.wait()

    with pytest.raises(AdapterUnavailableError, match="ظرفیت جست‌وجوی زنده"):
        await orchestrator.search(request)

    adapter.release.set()
    assert (await first_search).total > 0


@pytest.mark.asyncio
async def test_concurrent_identical_searches_share_one_raw_adapter_call() -> None:
    adapter = BlockingSearchAdapter()
    orchestrator = _orchestrator_for(adapter)
    request = SearchRequest(
        mode=TravelMode.FLIGHT,
        origin="THR",
        destination="MHD",
        departure_date=date(2030, 1, 15),
    )

    first_search = asyncio.create_task(orchestrator.search(request))
    await adapter.started.wait()
    second_search = asyncio.create_task(orchestrator.search(request))
    for _ in range(3):
        await asyncio.sleep(0)

    assert adapter.search_calls == 1

    adapter.release.set()
    first_result, second_result = await asyncio.gather(first_search, second_search)

    assert adapter.search_calls == 1
    assert first_result.search_id != second_result.search_id
    assert {offer.id for offer in first_result.offers}.isdisjoint(
        offer.id for offer in second_result.offers
    )


@pytest.mark.asyncio
async def test_raw_adapter_cache_expires_using_monotonic_time() -> None:
    now = [100.0]
    adapter = CountingSearchAdapter()
    factory = AdapterFactory()
    factory.register(adapter)
    orchestrator = SearchOrchestrator(
        adapter_factory=factory,
        repository=InMemoryOfferRepository(),
        normalizer=OfferNormalizer(),
        grouping_service=OfferGroupingService(),
        ranking_service=OfferRankingService(),
        adapter_search_cache_ttl_seconds=5,
        monotonic_clock=lambda: now[0],
        redirect_hosts_by_provider={"test_a": ("www.alibaba.ir",)},
    )
    request = SearchRequest(
        mode=TravelMode.FLIGHT,
        origin="THR",
        destination="MHD",
        departure_date=date(2030, 1, 15),
    )

    await orchestrator.search(request)
    now[0] = 104.999
    await orchestrator.search(request)
    assert adapter.search_calls == 1

    now[0] = 105.0
    await orchestrator.search(request)
    assert adapter.search_calls == 2


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "changed_request",
    (
        SearchRequest(
            mode=TravelMode.FLIGHT,
            origin="THR",
            destination="MHD",
            departure_date=date(2030, 1, 16),
        ),
        SearchRequest(
            mode=TravelMode.FLIGHT,
            origin="IKA",
            destination="MHD",
            departure_date=date(2030, 1, 15),
        ),
        SearchRequest(
            mode=TravelMode.FLIGHT,
            origin="THR",
            destination="MHD",
            departure_date=date(2030, 1, 15),
            passengers=PassengerCounts(adults=2),
        ),
        SearchRequest(
            mode=TravelMode.FLIGHT,
            origin="THR",
            destination="MHD",
            departure_date=date(2030, 1, 15),
            preferences=FlightSearchPreferences(
                mode=TravelMode.FLIGHT,
                nonstop_only=True,
            ),
        ),
    ),
    ids=("date", "route", "passengers", "preferences"),
)
async def test_raw_adapter_cache_separates_adapter_effective_request_fields(
    changed_request: SearchRequest,
) -> None:
    adapter = CountingSearchAdapter()
    orchestrator = _orchestrator_for(adapter)
    baseline = SearchRequest(
        mode=TravelMode.FLIGHT,
        origin="THR",
        destination="MHD",
        departure_date=date(2030, 1, 15),
    )

    await orchestrator.search(baseline)
    await orchestrator.search(changed_request)

    assert adapter.search_calls == 2


@pytest.mark.asyncio
async def test_raw_adapter_cache_separates_providers_and_travel_modes() -> None:
    first_provider = CountingSearchAdapter(provider="test_a")
    second_provider = CountingSearchAdapter(provider="test_b")
    train_adapter = CountingSearchAdapter(
        mode=TravelMode.TRAIN,
        provider="test_a",
    )
    factory = AdapterFactory()
    factory.register(first_provider)
    factory.register(second_provider)
    factory.register(train_adapter)
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
    flight_request = SearchRequest(
        mode=TravelMode.FLIGHT,
        origin="THR",
        destination="MHD",
        departure_date=date(2030, 1, 15),
    )
    train_request = SearchRequest(
        mode=TravelMode.TRAIN,
        origin="THR",
        destination="MHD",
        departure_date=date(2030, 1, 15),
    )

    flight_result = await orchestrator.search(flight_request)
    train_result = await orchestrator.search(train_request)

    assert first_provider.search_calls == 1
    assert second_provider.search_calls == 1
    assert train_adapter.search_calls == 1
    assert flight_result.providers_succeeded == 2
    assert train_result.providers_succeeded == 1


@pytest.mark.asyncio
async def test_intent_reuses_raw_results_but_keeps_response_ids_and_persistence() -> None:
    adapter = CountingSearchAdapter()
    factory = AdapterFactory()
    factory.register(adapter)
    repository = InMemoryOfferRepository()
    orchestrator = SearchOrchestrator(
        adapter_factory=factory,
        repository=repository,
        normalizer=OfferNormalizer(),
        grouping_service=OfferGroupingService(),
        ranking_service=OfferRankingService(),
        redirect_hosts_by_provider={"test_a": ("www.alibaba.ir",)},
    )
    request = SearchRequest(
        mode=TravelMode.FLIGHT,
        origin="THR",
        destination="MHD",
        departure_date=date(2030, 1, 15),
        intent=SearchIntent.BEST,
    )

    best = await orchestrator.search(request, persist_offers=False)
    assert await repository.get(best.offers[0].id) is None

    cheapest = await orchestrator.search(
        request.model_copy(update={"intent": SearchIntent.CHEAPEST})
    )

    assert adapter.search_calls == 1
    assert best.intent is SearchIntent.BEST
    assert cheapest.intent is SearchIntent.CHEAPEST
    assert best.search_id != cheapest.search_id
    assert best.offers[0].id != cheapest.offers[0].id
    assert await repository.get(cheapest.offers[0].id) is not None


@pytest.mark.asyncio
async def test_default_raw_cache_keeps_intent_reranking_stable_for_30_seconds() -> None:
    now = [100.0]
    adapter = CountingSearchAdapter()
    factory = AdapterFactory()
    factory.register(adapter)
    orchestrator = SearchOrchestrator(
        adapter_factory=factory,
        repository=InMemoryOfferRepository(),
        normalizer=OfferNormalizer(),
        grouping_service=OfferGroupingService(),
        ranking_service=OfferRankingService(),
        monotonic_clock=lambda: now[0],
        redirect_hosts_by_provider={"test_a": ("www.alibaba.ir",)},
    )
    request = SearchRequest(
        mode=TravelMode.FLIGHT,
        origin="THR",
        destination="MHD",
        departure_date=date(2030, 1, 15),
        intent=SearchIntent.BEST,
    )

    best = await orchestrator.search(request)
    now[0] = 129.999
    cheapest = await orchestrator.search(
        request.model_copy(update={"intent": SearchIntent.CHEAPEST})
    )

    assert adapter.search_calls == 1
    assert best.search_id != cheapest.search_id
    assert best.offers[0].id != cheapest.offers[0].id

    now[0] = 130.0
    await orchestrator.search(
        request.model_copy(update={"intent": SearchIntent.FASTEST})
    )
    assert adapter.search_calls == 2


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "adapter_type, expected_error",
    (
        (FailingFirstSearchAdapter, AdapterUnavailableError),
        (CancelledFirstSearchAdapter, asyncio.CancelledError),
    ),
    ids=("exception", "cancellation"),
)
async def test_failed_or_cancelled_adapter_search_is_not_cached(
    adapter_type: type[CountingSearchAdapter],
    expected_error: type[BaseException],
) -> None:
    adapter = adapter_type()
    orchestrator = _orchestrator_for(adapter)
    request = SearchRequest(
        mode=TravelMode.FLIGHT,
        origin="THR",
        destination="MHD",
        departure_date=date(2030, 1, 15),
    )

    with pytest.raises(expected_error):
        await orchestrator.search(request)

    result = await orchestrator.search(request)

    assert result.total > 0
    assert adapter.search_calls == 2


@pytest.mark.asyncio
async def test_cancelling_the_only_waiter_cancels_and_does_not_cache_raw_work() -> None:
    adapter = BlockingSearchAdapter()
    orchestrator = _orchestrator_for(adapter)
    request = SearchRequest(
        mode=TravelMode.FLIGHT,
        origin="THR",
        destination="MHD",
        departure_date=date(2030, 1, 15),
    )
    cancelled_search = asyncio.create_task(orchestrator.search(request))
    await adapter.started.wait()

    cancelled_search.cancel()
    with pytest.raises(asyncio.CancelledError):
        await cancelled_search

    adapter.release.set()
    result = await orchestrator.search(request)

    assert result.total > 0
    assert adapter.search_calls == 2


@pytest.mark.asyncio
async def test_raw_adapter_cache_evicts_least_recently_used_entries() -> None:
    adapter = CountingSearchAdapter()
    factory = AdapterFactory()
    factory.register(adapter)
    orchestrator = SearchOrchestrator(
        adapter_factory=factory,
        repository=InMemoryOfferRepository(),
        normalizer=OfferNormalizer(),
        grouping_service=OfferGroupingService(),
        ranking_service=OfferRankingService(),
        adapter_search_cache_max_entries=2,
        redirect_hosts_by_provider={"test_a": ("www.alibaba.ir",)},
    )

    def request_for(day: int) -> SearchRequest:
        return SearchRequest(
            mode=TravelMode.FLIGHT,
            origin="THR",
            destination="MHD",
            departure_date=date(2030, 1, day),
        )

    await orchestrator.search(request_for(15))
    await orchestrator.search(request_for(16))
    await orchestrator.search(request_for(17))
    await orchestrator.search(request_for(15))

    assert adapter.search_calls == 4


@pytest.mark.asyncio
async def test_capability_calls_are_rejected_before_adapter_dispatch() -> None:
    adapter = UnadvertisedCapabilityAdapter()
    orchestrator = _orchestrator_for(adapter)
    result = await orchestrator.search(
        SearchRequest(
            mode=TravelMode.BUS,
            origin="THR",
            destination="MHD",
            departure_date=date(2030, 1, 15),
        )
    )
    group = result.offers[0]
    seller_offer = group.seller_offers[0]

    with pytest.raises(AdapterUnavailableError):
        await orchestrator.get_refund_rules(
            offer_id=group.id,
            seller_offer_id=seller_offer.id,
        )
    with pytest.raises(AdapterUnavailableError):
        await orchestrator.get_seat_map(
            offer_id=group.id,
            seller_offer_id=seller_offer.id,
        )

    assert adapter.refund_calls == 0
    assert adapter.seat_map_calls == 0


def test_orchestrator_requires_a_non_empty_per_provider_redirect_allow_list() -> None:
    with pytest.raises(ValueError, match="trusted redirect hostname"):
        SearchOrchestrator(
            adapter_factory=AdapterFactory(),
            repository=InMemoryOfferRepository(),
            normalizer=OfferNormalizer(),
            grouping_service=OfferGroupingService(),
            ranking_service=OfferRankingService(),
            redirect_hosts_by_provider={},
        )


def test_orchestrator_requires_redirect_allowlist_registry_parity() -> None:
    factory = AdapterFactory()
    factory.register(FakeTravelAdapter(mode=TravelMode.FLIGHT, provider="test_a"))

    with pytest.raises(ValueError, match="include every registered provider"):
        SearchOrchestrator(
            adapter_factory=factory,
            repository=InMemoryOfferRepository(),
            normalizer=OfferNormalizer(),
            grouping_service=OfferGroupingService(),
            ranking_service=OfferRankingService(),
            redirect_hosts_by_provider={"unused": ("www.alibaba.ir",)},
        )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "redirect_url",
    (
        "https://www.alibaba.ir.evil.example/checkout",
        "https://www.snapptrip.com/checkout",
        "http://www.alibaba.ir/checkout",
    ),
)
async def test_redirect_preview_requires_https_and_an_exact_allowed_hostname(
    redirect_url: str,
) -> None:
    orchestrator = _orchestrator_for(UnsafeRedirectAdapter(redirect_url))
    result = await orchestrator.search(
        SearchRequest(
            mode=TravelMode.FLIGHT,
            origin="THR",
            destination="MHD",
            departure_date=date(2030, 1, 15),
        )
    )
    group = result.offers[0]

    with pytest.raises(AdapterUnavailableError):
        await orchestrator.preview_redirect(
            offer_id=group.id,
            seller_offer_id=group.seller_offers[0].id,
        )


@pytest.mark.asyncio
async def test_redirect_preview_marks_seller_search_for_price_recheck() -> None:
    orchestrator = _orchestrator_for(
        FakeTravelAdapter(mode=TravelMode.FLIGHT, provider="test_a")
    )
    result = await orchestrator.search(
        SearchRequest(
            mode=TravelMode.FLIGHT,
            origin="THR",
            destination="MHD",
            departure_date=date(2030, 1, 15),
        )
    )
    group = result.offers[0]

    preview = await orchestrator.preview_redirect(
        offer_id=group.id,
        seller_offer_id=group.recommended_seller_offer_id,
    )

    assert preview.target_kind == "seller_search"
    assert preview.price_recheck_required is True
    assert preview.notice_code == "external_checkout"
