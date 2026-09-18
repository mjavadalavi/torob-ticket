from __future__ import annotations

from copy import deepcopy
from datetime import date

import pytest
from app.adapters.alibaba import AlibabaTrainAdapter
from app.core.errors import AdapterUnavailableError
from app.domain.travel import (
    PassengerCounts,
    SearchRequest,
    TrainSearchPreferences,
    TravelMode,
)


class StubAlibabaTrainAdapter(AlibabaTrainAdapter):
    def __init__(self) -> None:
        super().__init__()
        self.payload: dict[str, object] | None = None
        self.rows = [
            {
                "proposalId": 22_816_659_672,
                "trainNumber": 384,
                "wagonName": "۴ ستاره غزال",
                "departureDateTime": "2026-09-19T16:50:00",
                "arrivalDateTime": "2026-09-20T03:10:00",
                "seat": 0,
                "cost": 13_000_000,
                "isCompartment": True,
                "compartmentCapacity": 4,
                "companyName": "پارس لاریم",
                "nonRefundable": False,
                "isCharter": False,
                "originCode": "THR",
                "destinationCode": "MHD",
            }
        ]

    async def _fetch_rows(self, payload):
        self.payload = dict(payload)
        return self.rows


@pytest.mark.asyncio
async def test_alibaba_train_maps_live_contract_and_real_redirect() -> None:
    adapter = StubAlibabaTrainAdapter()
    request = SearchRequest(
        mode="train",
        origin="THR",
        destination="MHD",
        departure_date=date(2026, 9, 19),
    )

    offers = await adapter.search(request)

    assert adapter.payload is not None
    assert adapter.payload["origin"] == "THR"
    assert adapter.payload["destination"] == "MHD"
    assert adapter.payload["passengerCount"] == 1
    assert offers[0].price.amount == 1_300_000
    assert offers[0].attributes.operator == "پارس لاریم"
    assert offers[0].mode_details.compartment_capacity == 4
    assert offers[0].remaining_seats == 0
    assert offers[0].mode_details.private_compartment_available is None
    details = await adapter.get_details(offers[0].source_offer_id)
    assert details.mode == "train"
    assert details.capabilities == []
    assert details.refundable is True
    assert details.cancellation_summary is None
    assert adapter.build_redirect_url(offers[0].source_offer_id) == (
        "https://www.alibaba.ir/train/THR-MHD?adult=1&child=0&infant=0&"
        "departing=1405-06-28&ticketType=Family&isExclusive=false"
    )


@pytest.mark.asyncio
async def test_alibaba_train_price_is_total_for_the_requested_party() -> None:
    adapter = StubAlibabaTrainAdapter()
    request = SearchRequest(
        mode="train",
        origin="THR",
        destination="MHD",
        departure_date=date(2026, 9, 19),
        passengers=PassengerCounts(adults=2),
    )

    offers = await adapter.search(request)

    assert adapter.payload is not None
    assert adapter.payload["passengerCount"] == 2
    assert offers[0].price.amount == 2_600_000


@pytest.mark.asyncio
async def test_alibaba_train_rejects_unverified_station_ids() -> None:
    adapter = StubAlibabaTrainAdapter()
    request = SearchRequest(
        mode="train",
        origin="XXX",
        destination="MHD",
        departure_date=date(2026, 9, 19),
    )

    with pytest.raises(AdapterUnavailableError):
        await adapter.search(request)


@pytest.mark.asyncio
async def test_alibaba_train_forwards_verified_search_preferences() -> None:
    adapter = StubAlibabaTrainAdapter()
    adapter.rows[0]["originCode"] = "IFN"
    request = SearchRequest(
        mode="train",
        origin="اصفهان",
        destination="مشهد",
        departure_date=date(2026, 9, 19),
        preferences=TrainSearchPreferences(
            mode=TravelMode.TRAIN,
            exclusive_compartment=True,
            passenger_type="female",
        ),
    )

    offers = await adapter.search(request)

    assert adapter.payload is not None
    assert adapter.payload["origin"] == "IFN"
    assert adapter.payload["isExclusiveCompartment"] is True
    assert adapter.payload["ticketType"] == "Female"
    assert "ticketType=Female" in adapter.build_redirect_url(offers[0].source_offer_id)
    assert "isExclusive=true" in adapter.build_redirect_url(offers[0].source_offer_id)


@pytest.mark.asyncio
async def test_alibaba_train_rejects_unverified_vehicle_transport() -> None:
    adapter = StubAlibabaTrainAdapter()
    request = SearchRequest(
        mode="train",
        origin="THR",
        destination="MHD",
        departure_date=date(2026, 9, 19),
        preferences=TrainSearchPreferences(
            mode=TravelMode.TRAIN,
            vehicle_transport=True,
        ),
    )

    with pytest.raises(AdapterUnavailableError):
        await adapter.search(request)

    assert adapter.payload is None


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("originCode", "IFN"),
        ("destinationCode", "SYZ"),
        ("departureDateTime", "2026-09-20T16:50:00"),
    ],
)
async def test_alibaba_train_discards_rows_outside_requested_journey(
    field: str,
    value: str,
) -> None:
    adapter = StubAlibabaTrainAdapter()
    valid_row = deepcopy(adapter.rows[0])
    invalid_row = deepcopy(valid_row)
    invalid_row[field] = value
    adapter.rows = [invalid_row, valid_row]

    offers = await adapter.search(
        SearchRequest(
            mode="train",
            origin="THR",
            destination="MHD",
            departure_date=date(2026, 9, 19),
        )
    )

    assert len(offers) == 1


@pytest.mark.asyncio
async def test_alibaba_train_reports_parse_drift_for_all_malformed_rows() -> None:
    adapter = StubAlibabaTrainAdapter()
    adapter.rows = [{}]

    with pytest.raises(AdapterUnavailableError, match="ساختار همه"):
        await adapter.search(
            SearchRequest(
                mode="train",
                origin="THR",
                destination="MHD",
                departure_date=date(2026, 9, 19),
            )
        )
