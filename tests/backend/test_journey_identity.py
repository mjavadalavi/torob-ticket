from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from app.domain.capabilities import Capability
from app.domain.itinerary import BusDetails, FlightDetails, OfferAttributes, TrainDetails
from app.domain.offer import Money, ProviderOffer
from app.domain.travel import TravelMode
from app.services.normalization import OfferNormalizer
from app.services.offer_grouping import OfferGroupingService
from fakes import FakeTravelAdapter


def _bus_offer(
    *,
    source_offer_id: str,
    departure_at: datetime,
    company: str = "همسفر چابکسواران",
    bus_class: str = "VIP 2+1",
    service_number: str | None = None,
    arrival_at: datetime | None = None,
    price: int = 750_000,
    ticket_type: str = "system",
    capabilities: list[Capability] | None = None,
    operator_logo_url: str | None = None,
) -> ProviderOffer:
    return ProviderOffer(
        source_offer_id=source_offer_id,
        origin="تهران",
        destination="مشهد",
        departure_at=departure_at,
        arrival_at=arrival_at,
        price=Money(amount=price),
        attributes=OfferAttributes(
            operator=company,
            operator_logo_url=operator_logo_url,
            service_number=service_number,
            vehicle_class=bus_class,
            ticket_type=ticket_type,
        ),
        mode_details=BusDetails(
            mode=TravelMode.BUS,
            origin_terminal="پایانه جنوب",
            destination_terminal="پایانه امام رضا",
            company=company,
            service_number=service_number,
            bus_class=bus_class,
        ),
        capabilities=capabilities or [],
        last_updated_at=departure_at - timedelta(minutes=2),
    )


def _normalized_bus_offers(*offers: ProviderOffer):
    normalizer = OfferNormalizer()
    adapters = (
        FakeTravelAdapter(mode=TravelMode.BUS, provider="test_a"),
        FakeTravelAdapter(mode=TravelMode.BUS, provider="test_b"),
    )
    return [
        normalizer.normalize(adapter=adapter, provider_offer=offer)
        for adapter, offer in zip(adapters, offers, strict=True)
    ]


def _normalized_same_provider_bus_offers(*offers: ProviderOffer):
    normalizer = OfferNormalizer()
    adapter = FakeTravelAdapter(mode=TravelMode.BUS, provider="test_a")
    return [
        normalizer.normalize(adapter=adapter, provider_offer=offer)
        for offer in offers
    ]


def _flight_offer(
    *,
    source_offer_id: str,
    operator: str,
    cabin: str,
    fare_type: str = "system",
) -> ProviderOffer:
    departure_at = datetime(2030, 1, 15, 8, 0, tzinfo=timezone.utc)
    return ProviderOffer(
        source_offer_id=source_offer_id,
        origin="تهران",
        destination="مشهد",
        departure_at=departure_at,
        arrival_at=departure_at + timedelta(minutes=80),
        price=Money(amount=4_000_000),
        attributes=OfferAttributes(
            operator=operator,
            service_number="7730",
            vehicle_class=cabin,
            ticket_type=fare_type,
            stops=0,
        ),
        mode_details=FlightDetails(
            mode=TravelMode.FLIGHT,
            origin_airport_code="THR",
            destination_airport_code="MHD",
            airline=operator,
            flight_number="7730",
            fare_type=fare_type,
            cabin_class=cabin,
        ),
        last_updated_at=departure_at - timedelta(minutes=2),
    )


def _normalized_flight_offers(*offers: ProviderOffer):
    normalizer = OfferNormalizer()
    adapters = (
        FakeTravelAdapter(mode=TravelMode.FLIGHT, provider="test_a"),
        FakeTravelAdapter(mode=TravelMode.FLIGHT, provider="test_b"),
    )
    return [
        normalizer.normalize(adapter=adapter, provider_offer=offer)
        for adapter, offer in zip(adapters, offers, strict=True)
    ]


def _train_offer(*, source_offer_id: str, ticket_type: str) -> ProviderOffer:
    departure_at = datetime(2030, 1, 15, 7, 25, tzinfo=timezone.utc)
    return ProviderOffer(
        source_offer_id=source_offer_id,
        origin="تهران",
        destination="مشهد",
        departure_at=departure_at,
        arrival_at=departure_at + timedelta(minutes=525),
        price=Money(amount=1_520_000),
        attributes=OfferAttributes(
            operator="رجا",
            service_number="370",
            vehicle_class="چهار تخته",
            ticket_type=ticket_type,
        ),
        mode_details=TrainDetails(
            mode=TravelMode.TRAIN,
            railway_company="رجا",
            train_number="370",
            class_name="چهار تخته",
            compartment_capacity=4,
        ),
        last_updated_at=departure_at - timedelta(minutes=2),
    )


def _normalized_train_offers(*offers: ProviderOffer):
    normalizer = OfferNormalizer()
    adapters = (
        FakeTravelAdapter(mode=TravelMode.TRAIN, provider="test_a"),
        FakeTravelAdapter(mode=TravelMode.TRAIN, provider="test_b"),
    )
    return [
        normalizer.normalize(adapter=adapter, provider_offer=offer)
        for adapter, offer in zip(adapters, offers, strict=True)
    ]


def test_train_grouping_treats_system_and_normal_as_the_same_journey() -> None:
    groups = OfferGroupingService().group(
        _normalized_train_offers(
            _train_offer(source_offer_id="alibaba-370", ticket_type="system"),
            _train_offer(source_offer_id="snapptrip-370", ticket_type="normal"),
        ),
        passenger_count=1,
    )

    assert len(groups) == 1
    assert groups[0].seller_count == 2


def test_flight_grouping_normalizes_operator_suffix_and_cabin_language() -> None:
    groups = OfferGroupingService().group(
        _normalized_flight_offers(
            _flight_offer(
                source_offer_id="a-flight",
                operator="آوا ایر",
                cabin="اکونومی",
            ),
            _flight_offer(
                source_offer_id="b-flight",
                operator="آوا",
                cabin="ECONOMY",
            ),
        ),
        passenger_count=1,
    )

    assert len(groups) == 1
    assert groups[0].seller_count == 2


def test_flight_grouping_normalizes_parenthetical_airline_alias() -> None:
    groups = OfferGroupingService().group(
        _normalized_flight_offers(
            _flight_offer(
                source_offer_id="alibaba-karun",
                operator="کارون",
                cabin="اکونومی",
            ),
            _flight_offer(
                source_offer_id="snapptrip-karun",
                operator="کارون (نفت)",
                cabin="ECONOMY",
            ),
        ),
        passenger_count=1,
    )

    assert len(groups) == 1
    assert groups[0].seller_count == 2
    assert len(groups[0].seller_offers) == 2


def test_flight_grouping_keeps_different_cabin_fares_in_one_flight_card() -> None:
    groups = OfferGroupingService().group(
        _normalized_flight_offers(
            _flight_offer(
                source_offer_id="economy",
                operator="ایران ایر",
                cabin="اکونومی",
            ),
            _flight_offer(
                source_offer_id="business",
                operator="ایران ایر",
                cabin="BUSINESS",
            ),
        ),
        passenger_count=1,
    )

    assert len(groups) == 1
    assert groups[0].seller_count == 2
    assert len(groups[0].seller_offers) == 2


def test_direct_flight_grouping_tolerates_provider_arrival_disagreement() -> None:
    first = _flight_offer(
        source_offer_id="one-hour-duration",
        operator="آتا",
        cabin="اکونومی",
    )
    second = first.model_copy(
        update={
            "source_offer_id": "two-hour-duration",
            "arrival_at": first.arrival_at + timedelta(hours=1),
        }
    )

    groups = OfferGroupingService().group(
        _normalized_flight_offers(first, second),
        passenger_count=1,
    )

    assert len(groups) == 1
    assert groups[0].seller_count == 2
    assert len(groups[0].seller_offers) == 2


def test_flight_grouping_keeps_system_and_charter_as_seller_variants() -> None:
    groups = OfferGroupingService().group(
        _normalized_flight_offers(
            _flight_offer(
                source_offer_id="system",
                operator="آوا ایر",
                cabin="اکونومی",
                fare_type="system",
            ),
            _flight_offer(
                source_offer_id="charter",
                operator="آوا",
                cabin="ECONOMY",
                fare_type="charter",
            ),
        ),
        passenger_count=1,
    )

    assert len(groups) == 1
    assert groups[0].seller_count == 2
    assert len(groups[0].seller_offers) == 2


def test_bus_grouping_uses_shared_identity_not_provider_service_metadata() -> None:
    tehran_time = timezone(timedelta(hours=3, minutes=30))
    first = _bus_offer(
        source_offer_id="a-1",
        departure_at=datetime(2030, 1, 15, 8, 0, 20, tzinfo=tehran_time),
        company="شرکت همسفر چابکسواران",
        service_number="A-991",
        arrival_at=datetime(2030, 1, 15, 20, 0, tzinfo=tehran_time),
    )
    second = _bus_offer(
        source_offer_id="b-8",
        departure_at=datetime(2030, 1, 15, 4, 30, 50, tzinfo=timezone.utc),
        company="همسفر چابکسواران (تعاونی ۱۳)",
        service_number=None,
        arrival_at=None,
    )

    groups = OfferGroupingService().group(
        _normalized_bus_offers(first, second),
        passenger_count=1,
    )

    assert len(groups) == 1
    assert groups[0].seller_count == 2


def test_grouping_keeps_verified_operator_logo_from_non_cheapest_seller() -> None:
    departure = datetime(2030, 1, 15, 8, 0, tzinfo=timezone.utc)
    groups = OfferGroupingService().group(
        _normalized_bus_offers(
            _bus_offer(
                source_offer_id="cheapest-without-logo",
                departure_at=departure,
                price=700_000,
            ),
            _bus_offer(
                source_offer_id="verified-logo",
                departure_at=departure,
                price=750_000,
                operator_logo_url="https://cdn.alibaba.ir/operators/royal-safar.png",
            ),
        ),
        passenger_count=1,
    )

    assert len(groups) == 1
    assert groups[0].lowest_price.amount == 700_000
    assert str(groups[0].attributes.operator_logo_url) == (
        "https://cdn.alibaba.ir/operators/royal-safar.png"
    )


def test_bus_grouping_collapses_duplicate_source_ids_from_one_provider() -> None:
    departure = datetime(2030, 1, 15, 8, 0, tzinfo=timezone.utc)
    groups = OfferGroupingService().group(
        _normalized_same_provider_bus_offers(
            _bus_offer(
                source_offer_id="provider-service-a",
                departure_at=departure,
                service_number="A-100",
            ),
            _bus_offer(
                source_offer_id="provider-service-b",
                departure_at=departure + timedelta(seconds=30),
                service_number="B-200",
            ),
        ),
        passenger_count=1,
    )

    assert len(groups) == 1
    assert groups[0].seller_count == 1
    assert len(groups[0].seller_offers) == 1
    assert groups[0].seller_offers[0].source_offer_id == "provider-service-b"


def test_bus_grouping_keeps_same_provider_fare_variants_in_one_group() -> None:
    departure = datetime(2030, 1, 15, 8, 0, tzinfo=timezone.utc)
    groups = OfferGroupingService().group(
        _normalized_same_provider_bus_offers(
            _bus_offer(
                source_offer_id="system-fare",
                departure_at=departure,
                price=750_000,
                capabilities=[Capability.TOROB_PAY],
            ),
            _bus_offer(
                source_offer_id="refundable-fare",
                departure_at=departure + timedelta(seconds=30),
                price=800_000,
                ticket_type="refundable",
                capabilities=[Capability.TOROB_PAY, Capability.REFUND_RULES],
            ),
        ),
        passenger_count=1,
    )

    assert len(groups) == 1
    assert groups[0].seller_count == 1
    assert len(groups[0].seller_offers) == 2


def test_bus_grouping_keeps_different_company_class_or_minute_separate() -> None:
    departure = datetime(2030, 1, 15, 8, 0, tzinfo=timezone.utc)
    baseline = _bus_offer(source_offer_id="a", departure_at=departure)
    variants = (
        _bus_offer(
            source_offer_id="b-company",
            departure_at=departure,
            company="همسفر",
        ),
        _bus_offer(
            source_offer_id="b-class",
            departure_at=departure,
            bus_class="معمولی",
        ),
        _bus_offer(
            source_offer_id="b-time",
            departure_at=departure + timedelta(minutes=1),
        ),
    )

    for variant in variants:
        groups = OfferGroupingService().group(
            _normalized_bus_offers(baseline, variant),
            passenger_count=1,
        )
        assert len(groups) == 2
        assert {group.seller_count for group in groups} == {1}


def test_bus_grouping_uses_cooperative_number_across_company_display_names() -> None:
    departure = datetime(2030, 1, 15, 8, 0, tzinfo=timezone.utc)
    groups = OfferGroupingService().group(
        _normalized_bus_offers(
            _bus_offer(
                source_offer_id="a-coop",
                departure_at=departure,
                company="شرکت گیتی نورد تعاونی شماره ۱۲ - پایانه جنوب",
            ),
            _bus_offer(
                source_offer_id="b-coop",
                departure_at=departure,
                company="شرکت تعاونى 12 ترمينال جنوب",
            ),
        ),
        passenger_count=1,
    )

    assert len(groups) == 1
    assert groups[0].seller_count == 2


@pytest.mark.parametrize(
    ("first", "second"),
    (
        ("تعاونی ۱۵ ترابر بی تا", "ترابربی تا"),
        ("تعاونی ۸ لوان نور", "لوان نور"),
        ("رویال سفر ایرانیان", "رویال سفر"),
        ("ایمن سفر تعاونی ۶", "ایمن سفر"),
    ),
)
def test_bus_grouping_merges_known_company_name_variants(first: str, second: str) -> None:
    departure = datetime(2030, 1, 15, 8, 0, tzinfo=timezone.utc)
    groups = OfferGroupingService().group(
        _normalized_bus_offers(
            _bus_offer(source_offer_id="alias-a", departure_at=departure, company=first),
            _bus_offer(source_offer_id="alias-b", departure_at=departure, company=second),
        ),
        passenger_count=1,
    )

    assert len(groups) == 1
    assert groups[0].seller_count == 2
