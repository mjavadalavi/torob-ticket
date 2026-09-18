from __future__ import annotations

from datetime import date

import pytest
from app.adapters.safar724.bus_adapter import Safar724BusAdapter
from app.adapters.safar724.spec import SAFAR724_LOCATIONS_URL, SAFAR724_SEARCH_URL
from app.core.errors import AdapterUnavailableError
from app.domain.capabilities import Capability
from app.domain.travel import SearchRequest


def city(code: str, english: str, persian: str) -> dict[str, object]:
    return {
        "ID": 1,
        "Code": code,
        "Name": english,
        "PersianName": persian,
        "ProvinceName": english,
        "ProvincePersianName": persian,
        "SearchExpressions": [english, persian],
        "IsCapital": True,
        "Order": 1,
    }


def response() -> dict[str, object]:
    return {
        "date": "1405-07-01",
        "originPersianName": "تهران",
        "originEnglishName": "tehran",
        "originCode": "11320000",
        "destinationPersianName": "اصفهان",
        "destinationEnglishName": "isfahan",
        "destinationCode": "21310000",
        "today": "1405-06-27",
        "logo": "",
        "items": [
            {
                "id": 39_882_852,
                "isVip": False,
                "busType": "درسا VIP + مانیتور + شارژر",
                "price": 7_120_000,
                "companyCode": "RO11321007",
                "companyName": "royal-safar",
                "companyPersianName": "رویال سفر ایرانیان",
                "departureTime": "00:30",
                "departureDate": "1405/07/01",
                "originTerminalPersianName": "بیهقی (آرژانتین)",
                "destinationTerminalPersianName": "کاوه",
                "availableSeatCount": 25,
                "companyLogo": (
                    "https://cdn.safar724.com/Content/Images/Companies/"
                    "CompanyLogo/PNG/royal-safar-iranian.png"
                ),
                "vehicleType": "Bus",
                "status": "Available",
                "facilities": [],
                "refundRules": [
                    {
                        "from": None,
                        "to": "-01:00:00",
                        "percent": 10.0,
                        "message": "تا ۱ ساعت قبل حرکت",
                    },
                    {
                        "from": "-01:00:00",
                        "to": None,
                        "percent": 50.0,
                        "message": "کمتر از ۱ ساعت به حرکت",
                    },
                ],
                "capacity": 25,
            }
        ],
    }


class StubHttp:
    def __init__(self, *, malformed: bool = False) -> None:
        self.calls: list[tuple[str, dict[str, object]]] = []
        self.malformed = malformed

    async def request_json(self, url: str, **kwargs):
        self.calls.append((url, kwargs))
        if url == SAFAR724_LOCATIONS_URL:
            return [
                city("11320000", "tehran", "تهران"),
                city("21310000", "isfahan", "اصفهان"),
            ]
        if url == SAFAR724_SEARCH_URL:
            result = response()
            if self.malformed:
                result["items"] = [{}]
            return result
        raise AssertionError(url)


def request(*, passengers: int = 1) -> SearchRequest:
    return SearchRequest(
        mode="bus",
        origin="تهران",
        destination="اصفهان",
        departure_date=date(2026, 9, 23),
        passengers={"adults": passengers},
    )


@pytest.mark.asyncio
async def test_maps_verified_safar724_bus_contract() -> None:
    http = StubHttp()
    adapter = Safar724BusAdapter(http_client=http)

    offers = await adapter.search(request(passengers=2))

    assert len(offers) == 1
    offer = offers[0]
    assert offer.origin == "تهران"
    assert offer.destination == "اصفهان"
    assert offer.price.amount == 1_424_000
    assert offer.remaining_seats == 25
    assert offer.attributes.operator == "رویال سفر ایرانیان"
    assert offer.attributes.operator_code == "RO11321007"
    assert offer.mode_details.origin_terminal == "بیهقی (آرژانتین)"
    assert offer.mode_details.destination_terminal == "کاوه"
    assert offer.mode_details.capacity == 25
    assert offer.capabilities == [Capability.REFUND_RULES]
    assert offer.refundable is True
    assert str(offer.attributes.operator_logo_url) == (
        "https://www.payaneha.com/images/payanehlogo/ROYAL.png"
    )
    search_call = next(call for call in http.calls if call[0] == SAFAR724_SEARCH_URL)
    assert search_call[1]["query"] == {
        "Date": "1405-07-01",
        "Destination": "21310000",
        "Origin": "11320000",
    }
    assert adapter.build_redirect_url(offer.source_offer_id) == (
        "https://safar724.com/bus/tehran-isfahan?date=1405-07-01"
    )
    rules = await adapter.get_refund_rules(offer.source_offer_id)
    assert rules.refundable is True
    assert "10٪" in rules.summary
    assert "50٪" in rules.summary


@pytest.mark.asyncio
async def test_bus_locations_use_verified_city_catalogue() -> None:
    http = StubHttp()
    adapter = Safar724BusAdapter(http_client=http)

    locations = await adapter.search_locations("تهران")
    repeated = await adapter.search_locations("تهران")

    assert locations == repeated
    assert len(locations) == 1
    assert locations[0].code == "11320000"
    assert locations[0].name == "تهران"
    assert locations[0].providers == ["safar724"]
    assert [call[0] for call in http.calls] == [SAFAR724_LOCATIONS_URL]


@pytest.mark.asyncio
async def test_reports_wholly_malformed_bus_contract() -> None:
    adapter = Safar724BusAdapter(http_client=StubHttp(malformed=True))

    with pytest.raises(AdapterUnavailableError, match="ساختار همه"):
        await adapter.search(request())


@pytest.mark.asyncio
async def test_filters_non_bus_and_unavailable_inventory() -> None:
    http = StubHttp()
    original = http.request_json

    async def custom_response(url: str, **kwargs):
        result = await original(url, **kwargs)
        if url == SAFAR724_SEARCH_URL:
            result["items"][0]["vehicleType"] = "AutoMobile"
        return result

    http.request_json = custom_response
    adapter = Safar724BusAdapter(http_client=http)

    assert await adapter.search(request()) == ()
