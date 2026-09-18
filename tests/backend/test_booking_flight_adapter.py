from __future__ import annotations

from datetime import date

import pytest
from app.adapters.booking import BookingFlightAdapter
from app.adapters.booking.spec import (
    BOOKING_FLIGHT_AIRPORTS_URL,
    BOOKING_FLIGHT_SEARCH_URL,
)
from app.core.errors import AdapterUnavailableError
from app.domain.travel import SearchRequest

LOCATIONS = {
    "httpStatusCode": 200,
    "statusCode": 200,
    "messages": [],
    "result": [
        {"label": "تهران، ایران", "code": "THRALL", "cityTitle": "تهران", "cityEnglishTitle": "Tehran", "isFeatured": True, "isInternational": False},
        {"label": "مشهد، ایران", "code": "MHDALL", "cityTitle": "مشهد", "cityEnglishTitle": "Mashhad", "isFeatured": True, "isInternational": False},
    ],
}


def flight_response() -> dict[str, object]:
    return {
        "httpStatusCode": 200,
        "statusCode": 200,
        "messages": [],
        "result": {
            "itineraries": [
                {
                    "id": "verified-booking-offer",
                    "totalPrice": 101_673_000,
                    "totalPriceIncludeCommission": 101_673_000,
                    "currency": "IRR",
                    "ticketType": 0,
                    "isFlightSaleable": True,
                    "flights": [
                        {
                            "remain": 5,
                            "stops": 0,
                            "cabinType": "Economy",
                            "flightsSegments": [
                                {
                                    "departureAirportLocationCode": "THR",
                                    "departureDateTime": "2026-09-23T21:30:00",
                                    "arrivalAirportLocationCode": "MHD",
                                    "arrivalDateTime": "2026-09-23T23:00:00",
                                    "flightNumber": "2638",
                                    "cabinType": "Economy",
                                    "airlineCode": "NV",
                                    "airlineTitle": "کارون (نفت) ایر",
                                    "baggageAllowance": {"adult": "20 کیلوگرم"},
                                }
                            ],
                        }
                    ],
                }
            ]
        },
    }


class StubHttp:
    def __init__(self, *, malformed: bool = False) -> None:
        self.calls: list[tuple[str, dict[str, object]]] = []
        self.malformed = malformed

    async def request_json(self, url: str, **kwargs):
        self.calls.append((url, kwargs))
        if url == BOOKING_FLIGHT_AIRPORTS_URL:
            return LOCATIONS
        if url == BOOKING_FLIGHT_SEARCH_URL:
            result = flight_response()
            if self.malformed:
                result["result"]["itineraries"] = [{}]
            return result
        raise AssertionError(url)


def request() -> SearchRequest:
    return SearchRequest(
        mode="flight",
        origin="تهران",
        destination="مشهد",
        departure_date=date(2026, 9, 23),
    )


@pytest.mark.asyncio
async def test_maps_verified_booking_flight_contract() -> None:
    http = StubHttp()
    adapter = BookingFlightAdapter(http_client=http)

    offers = await adapter.search(request())

    assert len(offers) == 1
    offer = offers[0]
    assert offer.origin == "تهران"
    assert offer.destination == "مشهد"
    assert offer.price.amount == 10_167_300
    assert offer.remaining_seats == 5
    assert offer.attributes.operator == "کارون (نفت) ایر"
    assert offer.attributes.operator_code == "NV"
    assert str(offer.attributes.operator_logo_url) == (
        "https://cdn.alibaba.ir/static/img/airlines/Domestic/NV.png"
    )
    assert offer.attributes.operator_logo_alt == "نشان شرکت کارون (نفت) ایر"
    assert offer.attributes.operator_logo_fallback == "کا"
    assert offer.attributes.service_number == "2638"
    assert offer.attributes.baggage_allowance_kg == 20
    assert offer.mode_details.fare_type == "system"
    search_call = next(call for call in http.calls if call[0] == BOOKING_FLIGHT_SEARCH_URL)
    assert search_call[1]["payload"]["itineraries"][0] == {
        "originLocation": "THRALL",
        "destinationLocation": "MHDALL",
        "departureDate": "2026-09-23",
        "returnDate": None,
    }
    assert search_call[1]["payload"]["searchType"] == 2
    redirect = adapter.build_redirect_url(offer.source_offer_id)
    assert redirect.startswith("https://www.booking.ir/flights/search/thrall-mhdall?")
    assert "departureDate=2026-09-23" in redirect


@pytest.mark.asyncio
async def test_booking_locations_use_verified_catalogue_and_cache() -> None:
    http = StubHttp()
    adapter = BookingFlightAdapter(http_client=http)

    locations = await adapter.search_locations("تهران")
    repeated = await adapter.search_locations("تهران")

    assert locations == repeated
    assert locations[0].code == "THRALL"
    assert locations[0].name == "تهران"
    assert locations[0].providers == ["booking"]
    assert [call[0] for call in http.calls] == [BOOKING_FLIGHT_AIRPORTS_URL]


@pytest.mark.asyncio
async def test_booking_filters_unsaleable_rows() -> None:
    http = StubHttp()
    original = http.request_json

    async def custom_response(url: str, **kwargs):
        result = await original(url, **kwargs)
        if url == BOOKING_FLIGHT_SEARCH_URL:
            result["result"]["itineraries"][0]["isFlightSaleable"] = False
        return result

    http.request_json = custom_response
    assert await BookingFlightAdapter(http_client=http).search(request()) == ()


@pytest.mark.asyncio
async def test_booking_reports_wholly_malformed_contract() -> None:
    with pytest.raises(AdapterUnavailableError, match="ساختار همه"):
        await BookingFlightAdapter(http_client=StubHttp(malformed=True)).search(request())


@pytest.mark.asyncio
async def test_booking_uses_international_search_type_for_foreign_cities() -> None:
    http = StubHttp()
    international_locations = {
        **LOCATIONS,
        "result": [
            {
                "label": "استانبول، ترکیه",
                "code": "ISTALL",
                "cityTitle": "استانبول",
                "cityEnglishTitle": "Istanbul",
                "isFeatured": True,
                "isInternational": True,
            },
            {
                "label": "آنتالیا، ترکیه",
                "code": "AYTALL",
                "cityTitle": "آنتالیا",
                "cityEnglishTitle": "Antalya",
                "isFeatured": True,
                "isInternational": True,
            },
        ],
    }
    original = http.request_json

    async def international_response(url: str, **kwargs):
        if url == BOOKING_FLIGHT_AIRPORTS_URL:
            http.calls.append((url, kwargs))
            return international_locations
        return await original(url, **kwargs)

    http.request_json = international_response
    adapter = BookingFlightAdapter(http_client=http)

    await adapter.search(
        SearchRequest(
            mode="flight",
            origin="استانبول",
            destination="آنتالیا",
            departure_date=date(2026, 9, 23),
        )
    )

    search_call = next(call for call in http.calls if call[0] == BOOKING_FLIGHT_SEARCH_URL)
    assert search_call[1]["payload"]["searchType"] == 1


@pytest.mark.asyncio
async def test_booking_treats_verified_no_flight_message_as_empty_inventory() -> None:
    http = StubHttp()
    original = http.request_json

    async def no_inventory(url: str, **kwargs):
        if url == BOOKING_FLIGHT_SEARCH_URL:
            http.calls.append((url, kwargs))
            return {
                "httpStatusCode": 200,
                "statusCode": 200,
                "messages": [
                    {
                        "type": 2,
                        "code": "0",
                        "message": "در تاریخ انتخاب شده پروازی یافت نشد",
                        "details": None,
                    }
                ],
                "result": None,
            }
        return await original(url, **kwargs)

    http.request_json = no_inventory

    assert await BookingFlightAdapter(http_client=http).search(request()) == ()
