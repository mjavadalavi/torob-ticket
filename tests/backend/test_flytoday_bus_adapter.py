from __future__ import annotations

from datetime import date

import pytest
from app.adapters.flytoday.bus_adapter import FlyTodayBusAdapter
from app.adapters.flytoday.spec import (
    FLYTODAY_BUS_LOCATION_URL,
    FLYTODAY_BUS_SEARCH_URL,
)
from app.core.errors import AdapterUnavailableError
from app.domain.travel import SearchRequest


def location(city_id: str, english: str, persian: str) -> dict[str, object]:
    return {
        "id": city_id,
        "name": english,
        "nameFa": persian,
        "locationType": 1,
        "cityId": city_id,
        "cityName": english,
        "cityNameFa": persian,
        "terminalCount": 4,
        "isDomestic": True,
        "popularity": 10_500,
    }


def endpoint(city_id: str, english: str, persian: str) -> dict[str, str]:
    return {
        "id": city_id,
        "name": english,
        "nameFa": persian,
        "cityId": city_id,
        "cityName": english,
        "cityNameFa": persian,
        "terminalNameFa": persian,
    }


def bus_response() -> dict[str, object]:
    origin = endpoint("0001", "Tehran", "تهران")
    destination = endpoint("0006", "Mashhad", "مشهد")
    itinerary_origin = {
        **origin,
        "id": "10002",
        "name": "SouthTehran",
        "nameFa": "پایانه جنوب ( تهران )",
        "terminalNameFa": "پایانه جنوب ( تهران )",
    }
    return {
        "searchId": 5_029_992,
        "originDestinationItineraries": [
            {
                "origin": origin,
                "destination": destination,
                "departureDate": "2026-09-23T06:00:00",
                "firstAvailableDate": None,
                "isFull": False,
                "noResult": False,
                "itineraries": [
                    {
                        "fareSourceCode": "verified-bus-fare-source",
                        "name": "گیتی نورد تعاونى شماره 12 - پایانه جنوب",
                        "busCompanyNameFa": (
                            "شرکت گیتی نورد تعاونى شماره 12 - پایانه جنوب"
                        ),
                        "busCompanyId": "1782",
                        "busGroupCompanyCode": "T12",
                        "busGroupCompanyNameFa": "گیتی نورد",
                        "departureDate": "2026-09-23T06:00:00",
                        "busType": "وی آی پی ۲۹ نفره صندلی تخت شو",
                        "origin": itinerary_origin,
                        "destination": destination,
                        "finalDestination": destination,
                        "remainingSeat": 15,
                        "price": 13_155_000,
                        "fullPrice": 13_155_000,
                        "hasDiscount": False,
                        "isFull": False,
                        "facilities": ["شارژر", "تخت خواب شو"],
                    }
                ],
            }
        ],
    }


class StubHttp:
    def __init__(self, *, malformed: bool = False) -> None:
        self.calls: list[tuple[str, dict[str, object]]] = []
        self.malformed = malformed

    async def request_json(self, url: str, **kwargs):
        self.calls.append((url, kwargs))
        if url == FLYTODAY_BUS_LOCATION_URL:
            term = kwargs["payload"]["searchTerm"]
            if term in {"تهران", "0001"}:
                rows = [location("0001", "Tehran", "تهران")]
            else:
                rows = [location("0006", "Mashhad", "مشهد")]
            return {"typeSearch": "match", "total": len(rows), "locations": rows}
        if url == FLYTODAY_BUS_SEARCH_URL:
            response = bus_response()
            if self.malformed:
                response["originDestinationItineraries"][0]["itineraries"] = [{}]
            return response
        raise AssertionError(url)


def request(*, passengers: int = 1) -> SearchRequest:
    return SearchRequest(
        mode="bus",
        origin="تهران",
        destination="مشهد",
        departure_date=date(2026, 9, 23),
        passengers={"adults": passengers},
    )


@pytest.mark.asyncio
async def test_maps_verified_flytoday_bus_contract() -> None:
    http = StubHttp()
    adapter = FlyTodayBusAdapter(http_client=http)

    offers = await adapter.search(request(passengers=2))

    assert len(offers) == 1
    offer = offers[0]
    assert offer.origin == "تهران"
    assert offer.destination == "مشهد"
    assert offer.price.amount == 2_631_000
    assert offer.remaining_seats == 15
    assert offer.attributes.operator == "گیتی نورد"
    assert offer.attributes.operator_code == "T12"
    assert offer.mode_details.origin_terminal == "پایانه جنوب ( تهران )"
    assert offer.mode_details.destination_terminal == "مشهد"
    assert offer.arrival_at is None
    search_call = next(call for call in http.calls if call[0] == FLYTODAY_BUS_SEARCH_URL)
    assert search_call[1]["payload"] == {
        "originDestinations": [
            {
                "originId": "0001",
                "destinationId": "0006",
                "departureDate": "2026-09-23",
            }
        ]
    }
    assert search_call[1]["path"] == (
        "https://www.flytodayir.com/bus/tehran-mashhad?"
        "origin=0001&destination=0006&departureDate=2026-09-23"
    )
    redirect = adapter.build_redirect_url(offer.source_offer_id)
    assert redirect == search_call[1]["path"]


@pytest.mark.asyncio
async def test_bus_locations_use_verified_place_search_contract() -> None:
    http = StubHttp()
    adapter = FlyTodayBusAdapter(http_client=http)

    locations = await adapter.search_locations("تهران")

    assert len(locations) == 1
    assert locations[0].code == "0001"
    assert locations[0].name == "تهران"
    assert locations[0].providers == ["flytoday"]
    assert http.calls[0][1]["payload"] == {
        "searchTerm": "تهران",
        "pageSize": 100,
        "pageNumber": 0,
    }


@pytest.mark.asyncio
async def test_reports_wholly_malformed_bus_contract() -> None:
    adapter = FlyTodayBusAdapter(http_client=StubHttp(malformed=True))

    with pytest.raises(AdapterUnavailableError, match="ساختار همه"):
        await adapter.search(request())


@pytest.mark.asyncio
async def test_does_not_claim_unverified_seat_selection() -> None:
    adapter = FlyTodayBusAdapter(http_client=StubHttp())
    requested = SearchRequest(
        mode="bus",
        origin="تهران",
        destination="مشهد",
        departure_date=date(2026, 9, 23),
        preferences={"mode": "bus", "seat_selection_required": True},
    )

    assert await adapter.search(requested) == ()
