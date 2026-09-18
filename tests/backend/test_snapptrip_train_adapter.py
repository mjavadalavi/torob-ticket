from __future__ import annotations

import json
from copy import deepcopy
from datetime import date
from pathlib import Path

import pytest
from app.adapters.snapptrip import SnappTripTrainAdapter
from app.core.errors import AdapterUnavailableError
from app.domain.travel import PassengerCounts, SearchRequest

FIXTURES = Path(__file__).parent / "fixtures"


def station_rows() -> list[dict[str, object]]:
    return json.loads(
        (FIXTURES / "snapptrip_train_stations.json").read_text(encoding="utf-8")
    )


def available_row() -> dict[str, object]:
    response = json.loads(
        (FIXTURES / "snapptrip_train_available.json").read_text(encoding="utf-8")
    )
    return response["solutions"]["solutions"][0]


class StubHttp:
    def __init__(self, response: object | None = None) -> None:
        self.response = station_rows() if response is None else response
        self.calls = 0

    async def request_json(self, _url, **_kwargs):
        self.calls += 1
        return deepcopy(self.response)


class StubSnappTripTrainAdapter(SnappTripTrainAdapter):
    def __init__(self, rows: list[dict[str, object]] | None = None) -> None:
        super().__init__(http_client=StubHttp())
        self.rows = rows
        self.payload: dict[str, object] | None = None

    async def _fetch_rows(self, payload):
        self.payload = dict(payload)
        return self.rows if self.rows is not None else [available_row()]


def train_request(
    *,
    passengers: int = 2,
    preferences: dict[str, object] | None = None,
) -> SearchRequest:
    return SearchRequest(
        mode="train",
        origin="THR",
        destination="Karaj",
        departure_date=date(2026, 9, 18),
        passengers=PassengerCounts(adults=passengers),
        preferences=preferences,
    )


@pytest.mark.asyncio
async def test_train_maps_verified_snapptrip_response() -> None:
    adapter = StubSnappTripTrainAdapter()

    offers = await adapter.search(train_request())

    assert adapter.payload == {
        "ticketType": "NORMAL",
        "adultCount": 2,
        "childCount": 0,
        "infantCount": 0,
        "origin": "Tehran",
        "destination": "Karaj",
        "moveDate": "2026-09-18",
        "isExclusive": False,
    }
    assert len(offers) == 1
    offer = offers[0]
    assert offer.origin == "تهران"
    assert offer.destination == "کرج"
    assert offer.departure_at.isoformat() == "2026-09-18T06:20:00+03:30"
    assert offer.arrival_at is not None
    assert offer.arrival_at.isoformat() == "2026-09-18T07:17:00+03:30"
    assert offer.price.amount == 273_500
    assert offer.remaining_seats == 12
    assert offer.attributes.operator == "رجا"
    assert offer.attributes.operator_code == "raja"
    assert str(offer.attributes.operator_logo_url) == (
        "https://fs.snapptrip.com/images/train/uploads/raja.png"
    )
    assert offer.attributes.service_number == "460"
    assert offer.attributes.vehicle_class == "4ستاره سالنی پردیس"
    assert offer.attributes.ticket_type == "normal"
    assert offer.attributes.stops == 0
    assert offer.mode_details.compartment_capacity == 4
    assert offer.mode_details.private_compartment_available is None
    assert offer.capabilities == []
    assert offer.refundable is None

    details = await adapter.get_details(offer.source_offer_id)
    assert details.mode_details.train_number == "460"
    assert adapter.build_redirect_url(offer.source_offer_id) == (
        "https://www.snapptrip.com/train-ticket/Tehran/Karaj?"
        "adultCount=2&childCount=0&infantCount=0&departureDate=2026-09-18&"
        "isExclusive=false&ticketType=NORMAL&source=searchBox&saleType=one-way"
    )


@pytest.mark.asyncio
async def test_train_locations_use_active_verified_station_shape_and_cache() -> None:
    http = StubHttp()
    adapter = SnappTripTrainAdapter(http_client=http)

    first = await adapter.search_locations("کر")
    second = await adapter.search_locations("Kar")

    assert http.calls == 1
    assert first == second
    assert len(first) == 1
    assert first[0].code == "Karaj"
    assert first[0].name == "کرج"
    assert first[0].providers == ["snapptrip"]
    assert all(location.code != "Inactive" for location in first)


@pytest.mark.asyncio
async def test_train_station_cache_expires() -> None:
    clock = [0.0]
    http = StubHttp()
    adapter = SnappTripTrainAdapter(
        station_ttl_seconds=60,
        http_client=http,
    )
    adapter._station_rows._clock = lambda: clock[0]

    await adapter.search_locations("")
    await adapter.search_locations("")
    assert http.calls == 1

    clock[0] = 61.0
    await adapter.search_locations("")
    assert http.calls == 2


@pytest.mark.asyncio
async def test_train_does_not_cache_wholly_invalid_station_document() -> None:
    http = StubHttp(response=[{"isActive": True, "nameFa": "تهران"}, {}])
    adapter = SnappTripTrainAdapter(http_client=http)

    for _ in range(2):
        with pytest.raises(AdapterUnavailableError, match="فهرست ایستگاه"):
            await adapter.search_locations("")

    assert http.calls == 2


@pytest.mark.asyncio
async def test_train_resolves_persian_english_numeric_and_canonical_station_ids() -> None:
    adapter = StubSnappTripTrainAdapter()
    rows = await adapter._fetch_station_rows()

    expected = ("Tehran", "تهران", "1")
    assert adapter._resolve_station("THR", rows) == expected
    assert adapter._resolve_station("تهران", rows) == expected
    assert adapter._resolve_station("Tehran", rows) == expected
    assert adapter._resolve_station("1", rows) == expected


@pytest.mark.asyncio
async def test_train_rejects_unknown_station_without_calling_listing() -> None:
    adapter = StubSnappTripTrainAdapter()

    with pytest.raises(AdapterUnavailableError, match="فهرست تأییدشده"):
        await adapter.search(
            SearchRequest(
                mode="train",
                origin="ایستگاه ساختگی",
                destination="کرج",
                departure_date=date(2026, 9, 18),
            )
        )

    assert adapter.payload is None


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("status", "seats", "passengers"),
    [
        ("UNAVAILABLE", 12, 2),
        ("AVAILABLE", 1, 2),
    ],
)
async def test_train_returns_only_truly_bookable_rows(
    status: str,
    seats: int,
    passengers: int,
) -> None:
    row = available_row()
    row["capacityStatus"] = status
    row["seatsRemaining"] = seats
    adapter = StubSnappTripTrainAdapter(rows=[row])

    assert await adapter.search(train_request(passengers=passengers)) == ()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("origin", "191"),
        ("destination", "1"),
        ("originName", "مشهد"),
        ("departureDateTime", "2026-09-19T06:20:00"),
        ("exclusible", True),
    ],
)
async def test_train_discards_rows_outside_requested_journey(
    field: str,
    value: object,
) -> None:
    row = available_row()
    row[field] = value

    offers = await StubSnappTripTrainAdapter(rows=[row]).search(train_request())

    assert offers == ()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("arrivalTime", "07:18"),
        ("duration", 0),
        ("ticketType", "FOREIGN"),
        ("capacityStatus", "UNKNOWN"),
        ("pricing", {}),
    ],
)
async def test_train_reports_contract_drift_for_malformed_bookable_rows(
    field: str,
    value: object,
) -> None:
    row = available_row()
    row[field] = value

    with pytest.raises(AdapterUnavailableError, match="ساختار همه"):
        await StubSnappTripTrainAdapter(rows=[row]).search(train_request())


@pytest.mark.asyncio
async def test_train_uses_only_safe_allowlisted_logo_names() -> None:
    row = available_row()
    row["logoName"] = "../seller.svg"

    offer = (
        await StubSnappTripTrainAdapter(rows=[row]).search(train_request())
    )[0]

    assert str(offer.attributes.operator_logo_url) == (
        "https://fs.snapptrip.com/images/train/uploads/raja.png"
    )
    assert offer.attributes.operator_logo_fallback == "رج"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "preferences",
    [
        {"mode": "train", "vehicle_transport": True},
        {"mode": "train", "passenger_type": "female"},
        {"mode": "train", "passenger_type": "male"},
    ],
)
async def test_train_rejects_unverified_search_capabilities(
    preferences: dict[str, object],
) -> None:
    adapter = StubSnappTripTrainAdapter()

    with pytest.raises(AdapterUnavailableError, match="تأیید نشده"):
        await adapter.search(train_request(preferences=preferences))

    assert adapter.payload is None


@pytest.mark.asyncio
async def test_train_exclusive_search_maps_request_and_confirmed_result() -> None:
    row = available_row()
    row["exclusible"] = True
    adapter = StubSnappTripTrainAdapter(rows=[row])

    offer = (
        await adapter.search(
            train_request(
                preferences={"mode": "train", "exclusive_compartment": True}
            )
        )
    )[0]

    assert adapter.payload is not None
    assert adapter.payload["isExclusive"] is True
    assert offer.mode_details.private_compartment_available is True


@pytest.mark.asyncio
async def test_train_fetch_requires_verified_nested_response_shape() -> None:
    adapter = SnappTripTrainAdapter(http_client=StubHttp(response={"solutions": []}))

    with pytest.raises(AdapterUnavailableError, match="پاسخ جست‌وجو"):
        await adapter._fetch_rows({})


@pytest.mark.asyncio
async def test_train_fetch_accepts_captured_nested_response_contract() -> None:
    response = json.loads(
        (FIXTURES / "snapptrip_train_available.json").read_text(encoding="utf-8")
    )
    adapter = SnappTripTrainAdapter(http_client=StubHttp(response=response))

    rows = await adapter._fetch_rows({"ticketType": "NORMAL"})

    assert len(rows) == 1
    assert rows[0]["capacityStatus"] == "AVAILABLE"
