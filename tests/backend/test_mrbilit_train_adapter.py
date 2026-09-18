from __future__ import annotations

from datetime import date

import pytest
from app.adapters.mrbilit import MrBilitTrainAdapter
from app.adapters.mrbilit.spec import MRBILIT_TRAIN_SEARCH_URL
from app.core.errors import AdapterUnavailableError
from app.domain.capabilities import Capability
from app.domain.travel import PassengerCounts, SearchRequest

TRAIN_ROW = {
    "id": 3347256,
    "from": 1,
    "to": 165,
    "fromName": "تهران",
    "toName": "کرج",
    "trainNumber": 460,
    "departureTime": "2026-09-24T06:20:00",
    "arrivalTime": "2026-09-24T07:17:00",
    "provider": 1,
    "providerName": "رجا",
    "corporationID": 1,
    "corporationName": "رجا",
    "cancellable": True,
    "prices": [
        {
            "sellType": 3,
            "classes": [
                {
                    "id": 9815513,
                    "price": 1_367_500,
                    "capacity": 12,
                    "wagonName": "4ستاره سالنی پردیس",
                    "compartmentCapacity": 4,
                    "discount": 0,
                    "isAvailable": True,
                    "reservationAvailable": True,
                    "svgLogoPath": "Logos/svg/default.svg",
                    "minPersons": 1,
                    "owner": 1,
                    "ownerName": "رجا",
                    "cancellationTerms": (
                        "قوانین کنسلی توسط راه‌آهن جمهوری اسلامی ایران "
                        "تعیین می‌شود."
                    ),
                }
            ],
        }
    ],
}


class StubHttp:
    def __init__(self, response: object | None = None) -> None:
        self.response = (
            {
                "trains": [TRAIN_ROW],
                "contentPath": "https://train.mrbilit.com/Content/",
            }
            if response is None
            else response
        )
        self.calls: list[tuple[str, dict[str, object]]] = []

    async def request_json(self, url: str, **kwargs):
        self.calls.append((url, kwargs))
        assert url == MRBILIT_TRAIN_SEARCH_URL
        return self.response


def request(
    *,
    passengers: int = 1,
    preferences: dict[str, object] | None = None,
) -> SearchRequest:
    return SearchRequest(
        mode="train",
        origin="تهران",
        destination="کرج",
        departure_date=date(2026, 9, 24),
        passengers=PassengerCounts(adults=passengers),
        preferences=preferences,
    )


@pytest.mark.asyncio
async def test_maps_verified_mrbilit_train_contract_and_party_total() -> None:
    http = StubHttp()
    adapter = MrBilitTrainAdapter(http_client=http)

    offers = await adapter.search(request(passengers=2))

    assert len(offers) == 1
    offer = offers[0]
    assert offer.origin == "تهران"
    assert offer.destination == "کرج"
    assert offer.price.amount == 273_500
    assert offer.remaining_seats == 12
    assert offer.attributes.operator == "رجا"
    assert offer.attributes.service_number == "460"
    assert offer.attributes.vehicle_class == "4ستاره سالنی پردیس"
    assert str(offer.attributes.operator_logo_url) == (
        "https://fs.snapptrip.com/images/train/uploads/raja.png"
    )
    assert offer.mode_details.compartment_capacity == 4
    assert offer.capabilities == [Capability.REFUND_RULES]
    assert offer.refundable is True
    assert http.calls[0][1]["query"] == {
        "from": 1,
        "to": 165,
        "date": "2026-09-24T00:00:00.000Z",
        "genderCode": 3,
        "adultCount": 2,
        "childCount": 0,
        "infantCount": 0,
        "disableCache": False,
        "exclusive": False,
        "availableStatus": "Both",
    }
    assert adapter.build_redirect_url(offer.source_offer_id).startswith(
        "https://mrbilit.com/trains/tehran-karaj?"
    )


@pytest.mark.asyncio
async def test_train_locations_resolve_name_slug_id_and_alias() -> None:
    adapter = MrBilitTrainAdapter(http_client=StubHttp())

    assert adapter._resolve_station("تهران").id == 1
    assert adapter._resolve_station("tehran").id == 1
    assert adapter._resolve_station("1").id == 1
    assert adapter._resolve_station("THR").id == 1
    locations = await adapter.search_locations("کرج")
    assert [(item.code, item.name) for item in locations] == [("karaj", "کرج")]


@pytest.mark.asyncio
async def test_train_filters_sold_out_rows_without_fabricating_inventory() -> None:
    row = {**TRAIN_ROW, "prices": [{"sellType": 3, "classes": []}]}
    adapter = MrBilitTrainAdapter(
        http_client=StubHttp(
            response={
                "trains": [row],
                "contentPath": "https://train.mrbilit.com/Content/",
            }
        )
    )

    assert await adapter.search(request()) == ()


@pytest.mark.asyncio
async def test_train_rejects_unverified_vehicle_transport() -> None:
    adapter = MrBilitTrainAdapter(http_client=StubHttp())

    with pytest.raises(AdapterUnavailableError, match="حمل خودرو"):
        await adapter.search(
            request(preferences={"mode": "train", "vehicle_transport": True})
        )

    assert adapter._http.calls == []
