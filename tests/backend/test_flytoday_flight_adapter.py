from __future__ import annotations

from copy import deepcopy
from datetime import date

import pytest
from app.adapters.flytoday.flight_adapter import FlyTodayFlightAdapter
from app.adapters.flytoday.spec import (
    FLYTODAY_FLIGHT_LOCATION_URL,
    FLYTODAY_FLIGHT_SEARCH_URL,
)
from app.core.errors import AdapterUnavailableError
from app.domain.capabilities import Capability
from app.domain.travel import SearchRequest


def location(city: str, code: str, airport: str) -> dict[str, object]:
    return {
        "iata": code.lower(),
        "type": "Airport",
        "name": airport,
        "cityName": city,
        "countryCode": "IR",
        "countryName": "ایران",
        "children": [],
    }


def flight_response() -> dict[str, object]:
    return {
        "searchId": 42641764,
        "pricedItineraries": [
            {
                "fareSourceCode": "verified-fare-source",
                "key": "verified-offer-key",
                "isCharter": False,
                "isSystem": True,
                "airItineraryPricingInfo": {
                    "itinTotalFare": {"totalFare": 99_322_000}
                },
                "originDestinationOptions": [
                    {
                        "journeyDurationPerMinute": 90,
                        "flightSegments": [
                            {
                                "departureDateTime": "2026-09-24T19:00:00",
                                "arrivalDateTime": "2026-09-24T20:30:00",
                                "stopQuantity": 0,
                                "flightNumber": "VRH5840",
                                "departureAirportLocationCode": "thr",
                                "departureAirportCityId": "thr",
                                "arrivalAirportLocationCode": "mhd",
                                "arrivalAirportCityId": "mhd",
                                "marketingAirlineCode": "VRH",
                                "cabinClassName": "اکونومی",
                                "cabinClassNameLocal": "اکونومی",
                                "seatsRemaining": 8,
                                "baggage": "20 KG",
                            }
                        ],
                    }
                ],
                "payLater": {"hasPayLater": True},
            }
        ],
        "additionalData": {
            "airlines": [
                {"iata": "VRH", "name": "Varesh", "nameLocal": "وارش"}
            ],
            "airports": [
                {
                    "iata": "thr",
                    "cityId": "THR",
                    "cityLocal": "تهران",
                },
                {
                    "iata": "mhd",
                    "cityId": "MHD",
                    "cityLocal": "مشهد",
                },
            ],
        },
    }


class StubHttp:
    def __init__(self, *, malformed: bool = False) -> None:
        self.calls: list[tuple[str, dict[str, object]]] = []
        self.malformed = malformed

    async def request_json(self, url: str, **kwargs):
        self.calls.append((url, kwargs))
        if url == FLYTODAY_FLIGHT_LOCATION_URL:
            term = kwargs["payload"]["searchTerm"]
            if term in {"تهران", "THR"}:
                rows = [location("تهران", "THR", "فرودگاه مهرآباد")]
            else:
                rows = [location("مشهد", "MHD", "فرودگاه مشهد")]
            return {"typeSearch": "match", "total": len(rows), "locations": rows}
        if url == FLYTODAY_FLIGHT_SEARCH_URL:
            response = flight_response()
            if self.malformed:
                response["pricedItineraries"] = [{}]
            return response
        raise AssertionError(url)


def request() -> SearchRequest:
    return SearchRequest(
        mode="flight",
        origin="تهران",
        destination="مشهد",
        departure_date=date(2026, 9, 24),
    )


@pytest.mark.asyncio
async def test_maps_verified_flytoday_flight_contract() -> None:
    http = StubHttp()
    adapter = FlyTodayFlightAdapter(http_client=http)

    offers = await adapter.search(request())

    assert len(offers) == 1
    offer = offers[0]
    assert offer.origin == "تهران"
    assert offer.destination == "مشهد"
    assert offer.price.amount == 9_932_200
    assert offer.remaining_seats == 8
    assert offer.attributes.operator == "وارش"
    assert offer.attributes.operator_code == "VRH"
    assert offer.attributes.service_number == "VRH5840"
    assert offer.attributes.baggage_allowance_kg == 20
    assert offer.capabilities == [Capability.INSTALLMENT_PAYMENT]
    search_call = next(call for call in http.calls if call[0] == FLYTODAY_FLIGHT_SEARCH_URL)
    assert search_call[1]["payload"] == {
        "pricingSourceType": 0,
        "adultCount": 1,
        "childCount": 0,
        "infantCount": 0,
        "travelPreference": {
            "cabinType": "Y",
            "maxStopsQuantity": "All",
            "airTripType": "OneWay",
        },
        "originDestinationInformations": [
            {
                "departureDateTime": "2026-09-24",
                "destinationLocationCode": "MHD",
                "destinationType": "City",
                "originLocationCode": "THR",
                "originType": "City",
            }
        ],
        "isJalali": True,
    }
    redirect = adapter.build_redirect_url(offer.source_offer_id)
    assert redirect.startswith("https://www.flytodayir.com/flight/search?")
    assert "departure=thr%2C1" in redirect
    details = await adapter.get_details(offer.source_offer_id)
    assert details.capabilities == [Capability.INSTALLMENT_PAYMENT]


@pytest.mark.asyncio
async def test_flight_locations_use_verified_flytoday_contract() -> None:
    adapter = FlyTodayFlightAdapter(http_client=StubHttp())

    locations = await adapter.search_locations("تهران")

    assert len(locations) == 1
    assert locations[0].code == "THR"
    assert locations[0].name == "تهران"
    assert locations[0].providers == ["flytoday"]


@pytest.mark.asyncio
async def test_reports_wholly_malformed_flight_contract() -> None:
    adapter = FlyTodayFlightAdapter(http_client=StubHttp(malformed=True))

    with pytest.raises(AdapterUnavailableError, match="ساختار همه"):
        await adapter.search(request())


@pytest.mark.asyncio
async def test_filters_unrequested_fare_type() -> None:
    response = flight_response()
    response["pricedItineraries"][0]["isCharter"] = True
    http = StubHttp()
    original = http.request_json

    async def custom_response(url: str, **kwargs):
        if url == FLYTODAY_FLIGHT_SEARCH_URL:
            return deepcopy(response)
        return await original(url, **kwargs)

    http.request_json = custom_response
    adapter = FlyTodayFlightAdapter(http_client=http)
    requested = SearchRequest(
        mode="flight",
        origin="تهران",
        destination="مشهد",
        departure_date=date(2026, 9, 24),
        preferences={"mode": "flight", "fare_type": "system"},
    )

    assert await adapter.search(requested) == ()
