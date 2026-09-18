from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import pytest
from app.adapters.alibaba import AlibabaFlightAdapter
from app.core.errors import AdapterUnavailableError
from app.domain.capabilities import Capability
from app.domain.travel import PassengerCounts, SearchRequest

FIXTURE = Path(__file__).parent / "fixtures" / "alibaba_flight_available.json"


class StubAlibabaFlightAdapter(AlibabaFlightAdapter):
    def __init__(self, rows: list[dict[str, object]] | None = None) -> None:
        super().__init__()
        self.payload: dict[str, object] | None = None
        self.rows = rows

    async def _fetch_rows(self, payload):
        self.payload = dict(payload)
        if self.rows is not None:
            return self.rows
        response = json.loads(FIXTURE.read_text(encoding="utf-8"))
        return response["result"]["departing"]


def verified_flight_row() -> dict[str, object]:
    response = json.loads(FIXTURE.read_text(encoding="utf-8"))
    return response["result"]["departing"][0]


def flight_request() -> SearchRequest:
    return SearchRequest(
        mode="flight",
        origin="THR",
        destination="MHD",
        departure_date=date(2026, 9, 19),
    )


@pytest.mark.asyncio
async def test_flight_maps_verified_response_and_passenger_total() -> None:
    adapter = StubAlibabaFlightAdapter()
    request = SearchRequest(
        mode="flight",
        origin="THR",
        destination="MHD",
        departure_date=date(2026, 9, 19),
        passengers=PassengerCounts(adults=2, children=1, infants=1),
    )

    offers = await adapter.search(request)

    assert adapter.payload == {
        "origin": "THR",
        "destination": "MHD",
        "departureDate": "2026-09-19",
        "returnDate": None,
        "adult": 2,
        "child": 1,
        "infant": 1,
    }
    offer = offers[0]
    assert offer.origin == "تهران"
    assert offer.destination == "مشهد"
    assert offer.price.amount == 29_000_000
    assert offer.attributes.operator == "آتا"
    assert offer.attributes.operator_code == "I3"
    assert str(offer.attributes.operator_logo_url) == (
        "https://cdn.alibaba.ir/static/img/airlines/Domestic/I3.png"
    )
    assert offer.attributes.operator_logo_alt == "نشان شرکت آتا"
    assert offer.attributes.operator_logo_fallback == "آت"
    assert offer.attributes.ticket_type == "charter"
    assert offer.attributes.baggage_allowance_kg == 20
    assert offer.mode_details.origin_airport_code == "THR"
    assert offer.remaining_seats == 3
    assert offer.refundable is True
    assert offer.capabilities == [Capability.REFUND_RULES]

    details = await adapter.get_details(offer.source_offer_id)
    assert details.mode_details.flight_number == "5617"
    rules = await adapter.get_refund_rules(offer.source_offer_id)
    assert rules.refundable is True
    assert "50%" in rules.summary
    assert adapter.build_redirect_url(offer.source_offer_id) == (
        "https://www.alibaba.ir/flights/THR-MHD?adult=2&child=1&infant=1&"
        "departing=1405-06-28"
    )


@pytest.mark.asyncio
async def test_flight_filters_verified_fare_type() -> None:
    adapter = StubAlibabaFlightAdapter()
    request = SearchRequest(
        mode="flight",
        origin="THR",
        destination="MHD",
        departure_date=date(2026, 9, 19),
        preferences={"mode": "flight", "fare_type": "system"},
    )

    assert await adapter.search(request) == ()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "unavailable_signal",
    (
        {"seat": 0},
        {"seat": -1},
        {"status": "C"},
        {"status": "X"},
        {"isAllowedToBuy": False},
    ),
)
async def test_flight_filters_verified_unavailable_rows(
    unavailable_signal: dict[str, object],
) -> None:
    row = verified_flight_row()
    row.update(unavailable_signal)
    adapter = StubAlibabaFlightAdapter(rows=[row])

    assert await adapter.search(flight_request()) == ()


@pytest.mark.asyncio
async def test_flight_does_not_infer_availability_when_signals_are_absent() -> None:
    row = verified_flight_row()
    row.pop("seat", None)
    row.pop("status", None)
    row.pop("isAllowedToBuy", None)
    adapter = StubAlibabaFlightAdapter(rows=[row])

    offers = await adapter.search(flight_request())

    assert len(offers) == 1
    assert offers[0].remaining_seats is None


@pytest.mark.asyncio
async def test_flight_does_not_advertise_generic_refund_rules() -> None:
    row = verified_flight_row()
    row.pop("crcn", None)
    row["isRefundable"] = True
    adapter = StubAlibabaFlightAdapter(rows=[row])

    offer = (await adapter.search(flight_request()))[0]

    assert offer.refundable is True
    assert Capability.REFUND_RULES not in offer.capabilities
    assert offer.cancellation_summary is None
    with pytest.raises(AdapterUnavailableError):
        await adapter.get_refund_rules(offer.source_offer_id)


@pytest.mark.asyncio
async def test_flight_advertises_confirmed_non_refundable_status() -> None:
    row = verified_flight_row()
    row.pop("crcn", None)
    row["isRefundable"] = False
    adapter = StubAlibabaFlightAdapter(rows=[row])

    offer = (await adapter.search(flight_request()))[0]
    rules = await adapter.get_refund_rules(offer.source_offer_id)

    assert offer.capabilities == [Capability.REFUND_RULES]
    assert rules.refundable is False
    assert rules.summary == "این بلیت غیرقابل‌استرداد است."


@pytest.mark.asyncio
async def test_flight_locations_come_from_verified_airports() -> None:
    adapter = StubAlibabaFlightAdapter()

    locations = await adapter.search_locations("شی")

    assert [(item.code, item.name) for item in locations] == [("SYZ", "شیراز")]
    assert all(item.popular for item in locations)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("field", "value"),
    (
        ("origin", "MHD"),
        ("destination", "THR"),
        ("leaveDateTime", "2026-09-20T20:50:00"),
    ),
)
async def test_flight_rejects_rows_that_do_not_match_requested_route_or_date(
    field: str,
    value: str,
) -> None:
    row = verified_flight_row()
    row[field] = value
    adapter = StubAlibabaFlightAdapter(rows=[row])

    with pytest.raises(AdapterUnavailableError, match="ساختار همه"):
        await adapter.search(flight_request())


@pytest.mark.asyncio
async def test_flight_reports_parse_drift_without_logging_row_data(caplog) -> None:
    leaked_value = "secret-provider-token"
    adapter = StubAlibabaFlightAdapter(rows=[{"proposalId": leaked_value}])

    with pytest.raises(AdapterUnavailableError, match="ساختار همه"):
        await adapter.search(flight_request())

    assert leaked_value not in caplog.text
    malformed_records = [
        record
        for record in caplog.records
        if record.message == "Skipping malformed Alibaba flight row"
    ]
    assert len(malformed_records) == 1
    assert malformed_records[0].error_type == "ProviderRowError"
