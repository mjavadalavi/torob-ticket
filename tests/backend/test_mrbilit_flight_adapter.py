from __future__ import annotations

from copy import deepcopy
from datetime import date

import pytest
from app.adapters.mrbilit import MrBilitFlightAdapter
from app.adapters.mrbilit.spec import (
    MRBILIT_FLIGHT_AIRPORTS_URL,
    MRBILIT_FLIGHT_SEARCH_URL,
)
from app.core.errors import AdapterUnavailableError
from app.domain.capabilities import Capability
from app.domain.travel import SearchRequest


def airport(city: str, code: str, english: str) -> dict[str, object]:
    return {
        "Airports": [
            {
                "CityPersianTitle": city,
                "Code": code,
                "CityEnglishTitle": english,
            }
        ],
        "Code": f"{code}ALL",
        "PersianTitle": city,
        "Title": english,
        "CityIataCode": code,
    }


def flight_row() -> dict[str, object]:
    return {
        "Id": "21910773",
        "Prices": [
            {
                "ProposalId": "verified-proposal-token",
                "Capacity": 8,
                "BookingClass": "YE",
                "PassengerFares": [
                    {"TotalFare": 99_322_000, "PaxType": "ADL"},
                    {"TotalFare": 79_777_000, "PaxType": "CHD"},
                    {"TotalFare": 15_707_000, "PaxType": "INF"},
                ],
                "Baggage": 20,
                "BaggageType": "KG",
                "CabinClass": "Economy",
                "CabinClassDisplayName": "اکونومی",
                "FareRules": "تا ۷ روز قبل از پرواز با ۳۰٪ جریمه قابل کنسل است.",
                "IsCharter": False,
            }
        ],
        "Segments": [
            {
                "Legs": [
                    {
                        "FlightNumber": "5840",
                        "Origin": "تهران",
                        "OriginCode": "THR",
                        "Destination": "مشهد",
                        "DestinationCode": "MHD",
                        "AirlineCode": "V1",
                        "Airline": {
                            "IataCode": "V1",
                            "PersianTitle": "وارش",
                            "Logo": (
                                "https://static.mrbilit.com/"
                                "img/AirlineLogos/svg/V1.svg"
                            ),
                        },
                        "DepartureTime": "2026-09-24T19:00:00+03:30",
                        "ArrivalTime": "2026-09-24T20:30:00+03:30",
                        "Stops": 0,
                    }
                ]
            }
        ],
    }


class StubHttp:
    def __init__(self, *, malformed: bool = False) -> None:
        self.calls: list[tuple[str, dict[str, object]]] = []
        self.malformed = malformed

    async def request_json(self, url: str, **kwargs):
        self.calls.append((url, kwargs))
        if url == MRBILIT_FLIGHT_AIRPORTS_URL:
            term = kwargs["query"]["term"]
            return [
                airport("تهران", "THR", "Tehran")
                if term in {"تهران", "THR"}
                else airport("مشهد", "MHD", "Mashhad")
            ]
        if url == MRBILIT_FLIGHT_SEARCH_URL:
            return {"Flights": [{}] if self.malformed else [flight_row()]}
        raise AssertionError(url)


def request() -> SearchRequest:
    return SearchRequest(
        mode="flight",
        origin="تهران",
        destination="مشهد",
        departure_date=date(2026, 9, 24),
    )


@pytest.mark.asyncio
async def test_maps_verified_mrbilit_flight_contract() -> None:
    http = StubHttp()
    adapter = MrBilitFlightAdapter(http_client=http)

    offers = await adapter.search(request())

    assert len(offers) == 1
    offer = offers[0]
    assert offer.origin == "تهران"
    assert offer.destination == "مشهد"
    assert offer.price.amount == 9_932_200
    assert offer.remaining_seats == 8
    assert offer.attributes.operator == "وارش"
    assert offer.attributes.operator_code == "V1"
    assert offer.attributes.service_number == "5840"
    assert offer.attributes.baggage_allowance_kg == 20
    assert offer.capabilities == [Capability.REFUND_RULES]
    assert offer.refundable is True
    assert http.calls[-1][1]["payload"] == {
        "AdultCount": 1,
        "ChildCount": 0,
        "InfantCount": 0,
        "CabinClass": "All",
        "Routes": [
            {
                "OriginCode": "THR",
                "DestinationCode": "MHD",
                "DepartureDate": "2026-09-24",
            }
        ],
        "Baggage": True,
        "IncludeFlightsWithHigherCapacity": False,
    }
    assert adapter.build_redirect_url(offer.source_offer_id).startswith(
        "https://mrbilit.com/flights/THR-MHD?"
    )
    rules = await adapter.get_refund_rules(offer.source_offer_id)
    assert rules.refundable is True


@pytest.mark.asyncio
async def test_flight_locations_use_provider_city_contract() -> None:
    adapter = MrBilitFlightAdapter(http_client=StubHttp())

    locations = await adapter.search_locations("تهران")

    assert len(locations) == 1
    assert locations[0].code == "THR"
    assert locations[0].name == "تهران"
    assert locations[0].providers == ["mrbilit"]


@pytest.mark.asyncio
async def test_reports_wholly_malformed_flight_contract() -> None:
    adapter = MrBilitFlightAdapter(http_client=StubHttp(malformed=True))

    with pytest.raises(AdapterUnavailableError, match="ساختار همه"):
        await adapter.search(request())


@pytest.mark.asyncio
async def test_filters_unrequested_fare_type() -> None:
    row = flight_row()
    row["Prices"][0]["IsCharter"] = True
    http = StubHttp()
    original = http.request_json

    async def response(url: str, **kwargs):
        if url == MRBILIT_FLIGHT_SEARCH_URL:
            return {"Flights": [deepcopy(row)]}
        return await original(url, **kwargs)

    http.request_json = response
    adapter = MrBilitFlightAdapter(http_client=http)
    requested = SearchRequest(
        mode="flight",
        origin="تهران",
        destination="مشهد",
        departure_date=date(2026, 9, 24),
        preferences={"mode": "flight", "fare_type": "system"},
    )

    assert await adapter.search(requested) == ()
