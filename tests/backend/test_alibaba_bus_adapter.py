from __future__ import annotations

import json
from copy import deepcopy
from datetime import date
from pathlib import Path

import pytest
from app.adapters.alibaba import AlibabaBusAdapter
from app.adapters.alibaba.spec import (
    ALIBABA_BUS_CANCELLATION_URL,
    ALIBABA_BUS_SEATS_URL,
)
from app.core.errors import AdapterUnavailableError
from app.domain.capabilities import Capability
from app.domain.travel import PassengerCounts, SearchRequest

FIXTURES = Path(__file__).parent / "fixtures"


def load_fixture(name: str):
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


class StubHttpClient:
    async def request_json(self, url, **kwargs):
        if url == ALIBABA_BUS_SEATS_URL:
            return load_fixture("alibaba_bus_seats.json")
        if url == ALIBABA_BUS_CANCELLATION_URL:
            return load_fixture("alibaba_bus_refund.json")
        raise AssertionError(f"Unexpected URL: {url}")


class StubAlibabaBusAdapter(AlibabaBusAdapter):
    def __init__(self) -> None:
        super().__init__()
        self.query: dict[str, object] | None = None
        self.rows_override = None

    async def _fetch_rows(self, query):
        self.query = dict(query)
        if self.rows_override is not None:
            return self.rows_override
        return load_fixture("alibaba_bus_available.json")["result"]["availableList"]

    async def _fetch_station_rows(self, query):
        if query in {"", "شیراز"}:
            return [
                {
                    "domainCode": "41310000",
                    "name": "شیراز",
                    "isPopular": True,
                    "country": {"domainCode": "IRN"},
                    "displayNames": [
                        {"language": "fa-IR", "value": "شیراز"},
                        {"language": "en-US", "value": "SYZ"},
                    ],
                }
            ]
        return []


class UnavailableStationAlibabaBusAdapter(AlibabaBusAdapter):
    async def _fetch_station_rows(self, query):
        raise AdapterUnavailableError("station endpoint unavailable")


@pytest.mark.asyncio
async def test_bus_maps_verified_response_and_capabilities() -> None:
    adapter = StubAlibabaBusAdapter()
    request = SearchRequest(
        mode="bus",
        origin="THR",
        destination="MHD",
        departure_date=date(2026, 9, 19),
        passengers=PassengerCounts(adults=2),
    )

    offers = await adapter.search(request)

    assert adapter.query == {
        "orginCityCode": "11320000",
        "destinationCityCode": "31310000",
        "requestDate": "2026-09-19",
        "passengerCount": 2,
        "serviceType": "Bus",
    }
    offer = offers[0]
    assert offer.origin == "تهران"
    assert offer.destination == "مشهد"
    assert offer.price.amount == 2_360_000
    assert offer.attributes.operator == "آرو (پایانه جنوب)"
    assert offer.attributes.operator_code == "1100761_24"
    assert offer.attributes.operator_logo_url is None
    assert offer.attributes.operator_logo_fallback == "آر"
    assert offer.mode_details.origin_terminal == "تهران پایانه جنوب"
    assert offer.mode_details.destination_terminal == "پایانه امام رضا"
    assert offer.remaining_seats == 13
    assert offer.refundable is True
    assert offer.capabilities == [
        Capability.SEAT_SELECTION,
        Capability.REFUND_RULES,
    ]
    assert adapter.build_redirect_url(offer.source_offer_id) == (
        "https://www.alibaba.ir/bus/THR-MHD?departing=1405-06-28"
    )

    adapter._http = StubHttpClient()
    seat_map = await adapter.get_seat_map(offer.source_offer_id)
    assert [seat.number for seat in seat_map.seats] == ["1", "2", "3"]
    assert [(seat.row, seat.column) for seat in seat_map.seats] == [
        (1, 1),
        (1, 2),
        (1, 4),
    ]
    assert [seat.available for seat in seat_map.seats] == [False, True, False]
    rules = await adapter.get_refund_rules(offer.source_offer_id)
    assert rules.refundable is True
    assert "10% جریمه" in rules.summary


@pytest.mark.asyncio
async def test_bus_rejects_unverified_station() -> None:
    adapter = StubAlibabaBusAdapter()
    request = SearchRequest(
        mode="bus",
        origin="شهر ناشناخته",
        destination="MHD",
        departure_date=date(2026, 9, 19),
    )

    with pytest.raises(AdapterUnavailableError, match="پایانه"):
        await adapter.search(request)


@pytest.mark.asyncio
async def test_bus_locations_and_dynamic_station_are_provider_backed() -> None:
    adapter = StubAlibabaBusAdapter()
    row = load_fixture("alibaba_bus_available.json")["result"]["availableList"][0]
    row["originCityCode"] = "41310000"
    adapter.rows_override = [row]

    locations = await adapter.search_locations("")
    assert [(item.code, item.name) for item in locations] == [("SYZ", "شیراز")]

    offers = await adapter.search(
        SearchRequest(
            mode="bus",
            origin="شیراز",
            destination="مشهد",
            departure_date=date(2026, 9, 19),
        )
    )
    assert offers[0].origin == "شیراز"
    assert adapter.query is not None
    assert adapter.query["orginCityCode"] == "41310000"
    assert adapter.build_redirect_url(offers[0].source_offer_id).startswith(
        "https://www.alibaba.ir/bus/SYZ-MHD?"
    )


@pytest.mark.asyncio
async def test_bus_locations_fall_back_to_verified_warm_catalogue() -> None:
    adapter = UnavailableStationAlibabaBusAdapter()

    locations = await adapter.search_locations("اصفهان")

    assert [(item.code, item.name) for item in locations] == [("IFN", "اصفهان")]
    assert locations[0].providers == ["alibaba"]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("originCityCode", "31310000"),
        ("destinationCityCode", "11320000"),
        ("departureDateTime", "2026-09-20T20:30:00"),
        ("type", "Train"),
    ],
)
async def test_alibaba_bus_discards_rows_outside_requested_journey(
    field: str,
    value: str,
) -> None:
    adapter = StubAlibabaBusAdapter()
    valid_row = load_fixture("alibaba_bus_available.json")["result"]["availableList"][0]
    invalid_row = deepcopy(valid_row)
    invalid_row[field] = value
    adapter.rows_override = [invalid_row, valid_row]

    offers = await adapter.search(
        SearchRequest(
            mode="bus",
            origin="THR",
            destination="MHD",
            departure_date=date(2026, 9, 19),
        )
    )

    assert len(offers) == 1


@pytest.mark.asyncio
async def test_alibaba_bus_reports_parse_drift_for_all_malformed_rows() -> None:
    adapter = StubAlibabaBusAdapter()
    adapter.rows_override = [{}]

    with pytest.raises(AdapterUnavailableError, match="ساختار همه"):
        await adapter.search(
            SearchRequest(
                mode="bus",
                origin="THR",
                destination="MHD",
                departure_date=date(2026, 9, 19),
            )
        )
