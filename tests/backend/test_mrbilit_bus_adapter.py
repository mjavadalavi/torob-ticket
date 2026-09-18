from __future__ import annotations

from datetime import date

import pytest
from app.adapters.mrbilit import MrBilitBusAdapter
from app.adapters.mrbilit.spec import (
    MRBILIT_BUS_LOCATIONS_URL,
    MRBILIT_BUS_SEARCH_URL,
)
from app.domain.capabilities import Capability
from app.domain.travel import PassengerCounts, SearchRequest

CITY_RESPONSE = [
    {
        "cities": [
            {
                "id": 11320000,
                "title": "تهران - همه پایانه‌ها",
                "persianTitle": "تهران",
                "englishTitle": "Tehran",
                "code": "tehran",
            },
            {
                "id": 21310000,
                "title": "اصفهان - همه پایانه‌ها",
                "persianTitle": "اصفهان",
                "englishTitle": "Isfahan",
                "code": "esfahan",
            },
            {
                "id": 11321007,
                "title": "تهران (بیهقی)",
                "code": "tehran_beyhaqi",
            },
        ]
    }
]

BUS_ROW = {
    "id": 56115201,
    "from": 11321007,
    "to": 21310000,
    "fromName": "تهران (بیهقی)",
    "toName": "اصفهان",
    "departureTime": "2026-09-24T00:30:00",
    "arrivalTime": "2026-09-24T06:00:00",
    "price": 7_120_000,
    "capacity": 19,
    "busType": "درسا VIP + مانیتور + شارژر",
    "superCorporationID": 9,
    "superCorporation": "رویال سفر",
    "fromTerminal": "تهران (بیهقی)",
    "fromCity": "تهران (بیهقی)",
    "toCity": "اصفهان",
    "toTerminal": "اصفهان (کاوه)",
    "penaltyText": "تا یک ساعت قبل از حرکت با ۱۰٪ جریمه قابل کنسل است.",
    "reservable": True,
    "isCar": False,
    "shortTitle": "درسا",
    "needsSelectSeat": True,
    "serviceNo": "RO6661THBIFK24SEP2026",
}


class StubHttp:
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict[str, object]]] = []

    async def request_json(self, url: str, **kwargs):
        self.calls.append((url, kwargs))
        if url == MRBILIT_BUS_LOCATIONS_URL:
            return CITY_RESPONSE
        if url == MRBILIT_BUS_SEARCH_URL:
            return {"buses": [BUS_ROW]}
        raise AssertionError(url)


def request(*, passengers: int = 1) -> SearchRequest:
    return SearchRequest(
        mode="bus",
        origin="تهران",
        destination="اصفهان",
        departure_date=date(2026, 9, 24),
        passengers=PassengerCounts(adults=passengers),
    )


@pytest.mark.asyncio
async def test_maps_verified_mrbilit_bus_contract_and_party_total() -> None:
    http = StubHttp()
    adapter = MrBilitBusAdapter(http_client=http)

    offers = await adapter.search(request(passengers=2))

    assert len(offers) == 1
    offer = offers[0]
    assert offer.origin == "تهران"
    assert offer.destination == "اصفهان"
    assert offer.price.amount == 1_424_000
    assert offer.remaining_seats == 19
    assert offer.attributes.operator == "رویال سفر"
    assert offer.attributes.service_number == "RO6661THBIFK24SEP2026"
    assert offer.mode_details.origin_terminal == "تهران (بیهقی)"
    assert offer.mode_details.destination_terminal == "اصفهان (کاوه)"
    assert offer.mode_details.seat_selection_available is True
    assert offer.capabilities == [Capability.REFUND_RULES]
    assert http.calls[-1][1]["payload"]["from"] == 11320000
    assert http.calls[-1][1]["payload"]["to"] == 21310000
    assert adapter.build_redirect_url(offer.source_offer_id).startswith(
        "https://mrbilit.com/buses/tehran-esfahan?"
    )


@pytest.mark.asyncio
async def test_bus_location_catalog_keeps_cities_and_excludes_terminals() -> None:
    http = StubHttp()
    adapter = MrBilitBusAdapter(http_client=http)

    first = await adapter.search_locations("تهران")
    second = await adapter.search_locations("اصفهان")

    assert [(item.code, item.name) for item in first] == [("tehran", "تهران")]
    assert [(item.code, item.name) for item in second] == [("esfahan", "اصفهان")]
    assert [call[0] for call in http.calls].count(MRBILIT_BUS_LOCATIONS_URL) == 1


@pytest.mark.asyncio
async def test_bus_seat_selection_requirement_uses_verified_flag() -> None:
    adapter = MrBilitBusAdapter(http_client=StubHttp())
    requested = SearchRequest(
        **request().model_dump(exclude={"preferences"}),
        preferences={"mode": "bus", "seat_selection_required": True},
    )

    offers = await adapter.search(requested)

    assert len(offers) == 1
