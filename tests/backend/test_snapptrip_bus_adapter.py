from __future__ import annotations

import json
from copy import deepcopy
from datetime import date
from pathlib import Path

import pytest
from app.adapters.snapptrip import SnappTripBusAdapter
from app.core.errors import AdapterUnavailableError
from app.domain.travel import PassengerCounts, SearchRequest

FIXTURES = Path(__file__).parent / "fixtures"


class StubSnappTripBusAdapter(SnappTripBusAdapter):
    def __init__(self) -> None:
        super().__init__()
        self.fetch_args: tuple[str, str, str] | None = None
        self.location_rows_override = None
        self.rows_override = None

    async def _fetch_location_rows(self, query):
        if self.location_rows_override is not None:
            return self.location_rows_override
        if query in {"تهران", "THR", "TEHRAN"}:
            return [{"code": "Tehran", "name": "تهران", "city": "تهران", "cityEn": "Tehran"}]
        if query in {"مشهد", "MHD", "MASHHAD"}:
            return [{"code": "Mashhad", "name": "مشهد", "city": "مشهد", "cityEn": "Mashhad"}]
        if query == "اصفهان":
            return [
                {
                    "code": "Esfahan",
                    "name": "اصفهان",
                    "city": "اصفهان",
                    "cityEn": "Esfahan",
                }
            ]
        response = json.loads(
            (FIXTURES / "snapptrip_bus_locations.json").read_text(encoding="utf-8")
        )
        return response["endpoints"]

    async def _fetch_rows(self, origin_code, destination_code, departure_date):
        self.fetch_args = (origin_code, destination_code, departure_date)
        if self.rows_override is not None:
            return self.rows_override
        response = json.loads(
            (FIXTURES / "snapptrip_bus_available.json").read_text(encoding="utf-8")
        )
        return response["solutions"]


@pytest.mark.asyncio
async def test_bus_maps_verified_snapptrip_response() -> None:
    adapter = StubSnappTripBusAdapter()
    request = SearchRequest(
        mode="bus",
        origin="THR",
        destination="MHD",
        departure_date=date(2026, 9, 23),
        passengers=PassengerCounts(adults=2),
    )

    offers = await adapter.search(request)

    assert adapter.fetch_args == ("Tehran", "Mashhad", "2026-09-23")
    offer = offers[0]
    assert offer.origin == "تهران"
    assert offer.destination == "مشهد"
    assert offer.price.amount == 2_626_000
    assert offer.attributes.operator == "پیک صبا تهران پایانه جنوب"
    assert offer.attributes.operator_code == "1045"
    assert str(offer.attributes.operator_logo_url) == (
        "https://www.payaneha.com/cloob/Images/"
        "454c5f8c40701efdb26497-peyksabalogo.png"
    )
    assert offer.attributes.operator_logo_alt == (
        "نشان شرکت پیک صبا تهران پایانه جنوب"
    )
    assert offer.attributes.operator_logo_fallback == "پی"
    assert offer.attributes.service_number is None
    assert offer.attributes.stops is None
    assert offer.remaining_seats == 20
    assert offer.capabilities == []
    assert offer.refundable is None
    assert offer.mode_details.origin_terminal == "پایانه جنوب"
    assert offer.mode_details.destination_terminal == "مشهد"
    assert offer.mode_details.seat_selection_available is None
    assert offer.mode_details.capacity is None

    details = await adapter.get_details(offer.source_offer_id)
    assert details.mode_details.bus_class == "اتوبوس VIP-تخت شو-شارژر دار"
    assert adapter.build_redirect_url(offer.source_offer_id) == (
        "https://www.snapptrip.com/bus/Tehran/Mashhad?"
        "source=searchBox&departureDate=2026-09-23"
    )


@pytest.mark.asyncio
async def test_bus_required_seats_filter_uses_verified_remaining_capacity() -> None:
    adapter = StubSnappTripBusAdapter()
    request = SearchRequest(
        mode="bus",
        origin="THR",
        destination="MHD",
        departure_date=date(2026, 9, 23),
        passengers=PassengerCounts(adults=9),
        preferences={"mode": "bus", "seat_selection_required": True},
    )
    with pytest.raises(AdapterUnavailableError):
        await adapter.search(request)

    assert adapter.fetch_args is None


@pytest.mark.asyncio
async def test_bus_locations_use_verified_endpoint_shape() -> None:
    adapter = StubSnappTripBusAdapter()

    locations = await adapter.search_locations("تهران")

    assert len(locations) == 1
    assert locations[0].code == "Tehran"
    assert locations[0].name == "تهران"
    assert locations[0].providers == ["snapptrip"]


@pytest.mark.asyncio
async def test_bus_location_resolution_requires_an_exact_provider_match() -> None:
    adapter = StubSnappTripBusAdapter()
    adapter.location_rows_override = [
        {"code": "Qom", "name": "قم", "city": "قم", "cityEn": "Qom"}
    ]

    with pytest.raises(AdapterUnavailableError, match="تأییدشده"):
        await adapter._resolve_endpoint("کاشان")


@pytest.mark.asyncio
async def test_bus_resolves_shared_canonical_code_to_provider_endpoint() -> None:
    adapter = StubSnappTripBusAdapter()

    assert await adapter._resolve_endpoint("IFN") == ("Esfahan", "اصفهان")


@pytest.mark.asyncio
async def test_bus_enforces_provider_per_order_limit() -> None:
    adapter = StubSnappTripBusAdapter()

    offers = await adapter.search(
        SearchRequest(
            mode="bus",
            origin="THR",
            destination="MHD",
            departure_date=date(2026, 9, 23),
            passengers=PassengerCounts(adults=7),
        )
    )

    assert offers == ()


@pytest.mark.asyncio
async def test_bus_keeps_offer_when_provider_omits_unverified_arrival_time() -> None:
    adapter = StubSnappTripBusAdapter()
    response = json.loads(
        (FIXTURES / "snapptrip_bus_available.json").read_text(encoding="utf-8")
    )
    row = response["solutions"][0]
    row["arrivalDatetime"] = ""
    row["journeyDuration"] = 0
    adapter.rows_override = [row]

    offers = await adapter.search(
        SearchRequest(
            mode="bus",
            origin="THR",
            destination="MHD",
            departure_date=date(2026, 9, 23),
        )
    )

    assert len(offers) == 1
    assert offers[0].arrival_at is None


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("originCity", "قم"),
        ("destinationCity", "شیراز"),
        ("departureDate", "2026-09-24"),
        ("departureDatetime", "2026-09-24T21:00:00"),
        ("multiStop", True),
    ],
)
async def test_bus_discards_rows_outside_requested_journey(
    field: str,
    value: object,
) -> None:
    adapter = StubSnappTripBusAdapter()
    response = json.loads(
        (FIXTURES / "snapptrip_bus_available.json").read_text(encoding="utf-8")
    )
    valid_row = response["solutions"][0]
    invalid_row = deepcopy(valid_row)
    invalid_row[field] = value
    adapter.rows_override = [invalid_row, valid_row]

    offers = await adapter.search(
        SearchRequest(
            mode="bus",
            origin="THR",
            destination="MHD",
            departure_date=date(2026, 9, 23),
        )
    )

    assert len(offers) == 1


@pytest.mark.asyncio
async def test_snapptrip_bus_reports_parse_drift_for_all_malformed_rows() -> None:
    adapter = StubSnappTripBusAdapter()
    adapter.rows_override = [{}]

    with pytest.raises(AdapterUnavailableError, match="ساختار همه"):
        await adapter.search(
            SearchRequest(
                mode="bus",
                origin="THR",
                destination="MHD",
                departure_date=date(2026, 9, 23),
            )
        )
