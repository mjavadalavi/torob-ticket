from __future__ import annotations

import json
from copy import deepcopy
from datetime import date
from pathlib import Path

import pytest
from app.adapters.snapptrip import SnappTripFlightAdapter
from app.core.errors import AdapterUnavailableError
from app.domain.capabilities import Capability
from app.domain.travel import PassengerCounts, SearchRequest

FIXTURES = Path(__file__).parent / "fixtures"


class StubHttp:
    def __init__(self, response: object | None = None) -> None:
        self.response = response
        self.calls = 0

    async def request_json(self, url, **kwargs):
        self.calls += 1
        if self.response is not None:
            return deepcopy(self.response)
        return verified_location_rows()


class StubSnappTripFlightAdapter(SnappTripFlightAdapter):
    def __init__(self, rows: list[dict[str, object]] | None = None) -> None:
        super().__init__(http_client=StubHttp())
        self.payload: dict[str, object] | None = None
        self.rows = rows

    async def _fetch_rows(self, payload):
        self.payload = dict(payload)
        return self.rows if self.rows is not None else [verified_flight_row()]


def verified_location_rows() -> list[dict[str, object]]:
    return json.loads(
        (FIXTURES / "snapptrip_flight_locations.json").read_text(encoding="utf-8")
    )


def verified_flight_row() -> dict[str, object]:
    response = json.loads(
        (FIXTURES / "snapptrip_flight_available.json").read_text(encoding="utf-8")
    )
    return response["airfares"][0]


def flight_request(*, origin: str = "THR", destination: str = "MHD") -> SearchRequest:
    return SearchRequest(
        mode="flight",
        origin=origin,
        destination=destination,
        departure_date=date(2026, 9, 23),
    )


@pytest.mark.asyncio
async def test_flight_maps_verified_snapptrip_response() -> None:
    adapter = StubSnappTripFlightAdapter()
    request = SearchRequest(
        mode="flight",
        origin="THR",
        destination="MHD",
        departure_date=date(2026, 9, 23),
        passengers=PassengerCounts(adults=2, children=1, infants=1),
    )

    offers = await adapter.search(request)

    assert adapter.payload == {
        "dateType": "jalali",
        "origin": "THR",
        "destination": "MHD",
        "destinationIsCity": True,
        "originIsCity": True,
        "adultCount": 2,
        "childCount": 1,
        "infantCount": 1,
        "departureDate": "2026-09-23",
        "returnDate": None,
        "cabinType": "ECONOMY",
    }
    offer = offers[0]
    assert offer.origin == "تهران"
    assert offer.destination == "مشهد"
    assert offer.price.amount == 10_167_300
    assert offer.attributes.operator == "کارون (نفت)"
    assert offer.attributes.operator_code == "NV"
    assert str(offer.attributes.operator_logo_url) == (
        "https://cdn.alibaba.ir/static/img/airlines/Domestic/NV.png"
    )
    assert offer.attributes.operator_logo_alt == "نشان شرکت کارون (نفت)"
    assert offer.attributes.service_number == "2638"
    assert offer.attributes.ticket_type == "system"
    assert offer.attributes.stops == 0
    assert offer.attributes.baggage_allowance_kg == 20
    assert offer.remaining_seats == 9
    assert offer.refundable is True
    assert offer.capabilities == [Capability.REFUND_RULES]

    details = await adapter.get_details(offer.source_offer_id)
    assert details.mode_details.origin_airport_code == "THR"
    rules = await adapter.get_refund_rules(offer.source_offer_id)
    assert rules.refundable is True
    assert "30٪ جریمه" in rules.summary
    assert adapter.build_redirect_url(offer.source_offer_id) == (
        "https://www.snapptrip.com/flights/THR_city/MHD_city?"
        "adultCount=2&childCount=1&infantCount=1&departureDate=2026-09-23&"
        "source=history_cards&dateType=jalali"
    )


@pytest.mark.asyncio
async def test_flight_filters_verified_fare_type() -> None:
    adapter = StubSnappTripFlightAdapter()
    request = SearchRequest(
        mode="flight",
        origin="THR",
        destination="MHD",
        departure_date=date(2026, 9, 23),
        preferences={"mode": "flight", "fare_type": "charter"},
    )

    assert await adapter.search(request) == ()


@pytest.mark.asyncio
async def test_flight_locations_use_verified_suggestion_shape() -> None:
    adapter = SnappTripFlightAdapter()
    adapter._http = StubHttp()

    locations = await adapter.search_locations("مش")

    assert len(locations) == 1
    assert locations[0].code == "MHD"
    assert locations[0].name == "مشهد"
    assert locations[0].providers == ["snapptrip"]


@pytest.mark.asyncio
async def test_flight_search_resolves_public_persian_city_names() -> None:
    adapter = StubSnappTripFlightAdapter()
    adapter._http = StubHttp()
    request = SearchRequest(
        mode="flight",
        origin="تهران",
        destination="مشهد",
        departure_date=date(2026, 9, 23),
    )

    offers = await adapter.search(request)

    assert offers
    assert adapter.payload is not None
    assert adapter.payload["origin"] == "THR"
    assert adapter.payload["destination"] == "MHD"


@pytest.mark.asyncio
async def test_flight_search_rejects_unknown_well_formed_iata_code() -> None:
    adapter = StubSnappTripFlightAdapter()

    with pytest.raises(AdapterUnavailableError, match="فهرست تأییدشده"):
        await adapter.search(flight_request(origin="ZZZ"))


@pytest.mark.asyncio
async def test_flight_location_cache_expires() -> None:
    clock = [0.0]
    http = StubHttp()
    adapter = SnappTripFlightAdapter(offer_ttl_seconds=60, http_client=http)
    adapter._location_rows._clock = lambda: clock[0]

    await adapter.search_locations("")
    await adapter.search_locations("")
    assert http.calls == 1

    clock[0] = 61.0
    await adapter.search_locations("")
    assert http.calls == 2


@pytest.mark.asyncio
async def test_flight_does_not_cache_wholly_malformed_locations() -> None:
    http = StubHttp(response=[{"iataCode": "INVALID", "cityFaName": "تهران"}, {}])
    adapter = SnappTripFlightAdapter(http_client=http)

    for _ in range(2):
        with pytest.raises(AdapterUnavailableError, match="فهرست فرودگاه"):
            await adapter.search_locations("")

    assert http.calls == 2


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("field", "value"),
    (
        ("originAirportCode", "MHD"),
        ("destinationAirportCode", "THR"),
    ),
)
async def test_flight_rejects_route_that_does_not_match_search(
    field: str,
    value: str,
) -> None:
    row = verified_flight_row()
    route = row["routes"][0]
    route[field] = value

    with pytest.raises(AdapterUnavailableError, match="ساختار همه"):
        await StubSnappTripFlightAdapter(rows=[row]).search(flight_request())


@pytest.mark.asyncio
async def test_flight_rejects_departure_date_that_does_not_match_search() -> None:
    row = verified_flight_row()
    row["routes"][0]["segments"][0]["departureDateTime"] = (
        "2026-09-24T21:30:00"
    )

    with pytest.raises(AdapterUnavailableError, match="ساختار همه"):
        await StubSnappTripFlightAdapter(rows=[row]).search(flight_request())


@pytest.mark.asyncio
async def test_flight_rejects_discontinuous_segments() -> None:
    row = verified_flight_row()
    route = row["routes"][0]
    first_segment = route["segments"][0]
    first_segment["arrivalAirportCode"] = "IFN"
    first_segment["arrivalDateTime"] = "2026-09-23T22:00:00"
    second_segment = deepcopy(first_segment)
    second_segment.update(
        {
            "departureAirportCode": "SYZ",
            "arrivalAirportCode": "MHD",
            "departureDateTime": "2026-09-23T22:30:00",
            "arrivalDateTime": "2026-09-23T23:30:00",
        }
    )
    route["segments"] = [first_segment, second_segment]

    with pytest.raises(AdapterUnavailableError, match="ساختار همه"):
        await StubSnappTripFlightAdapter(rows=[row]).search(flight_request())


@pytest.mark.asyncio
async def test_flight_rejects_non_irr_price_before_conversion() -> None:
    row = verified_flight_row()
    row["pricing"]["currency"] = "USD"

    with pytest.raises(AdapterUnavailableError, match="ساختار همه"):
        await StubSnappTripFlightAdapter(rows=[row]).search(flight_request())


@pytest.mark.asyncio
async def test_flight_does_not_advertise_generic_refund_rules() -> None:
    response = json.loads(
        (FIXTURES / "snapptrip_flight_available.json").read_text(encoding="utf-8")
    )
    row = response["airfares"][0]
    row.pop("policies", None)
    row["refundType"] = "REFUNDABLE"
    adapter = StubSnappTripFlightAdapter()

    async def fetch_rows(_payload):
        return [row]

    adapter._fetch_rows = fetch_rows

    offer = (
        await adapter.search(
            SearchRequest(
                mode="flight",
                origin="THR",
                destination="MHD",
                departure_date=date(2026, 9, 23),
            )
        )
    )[0]

    assert offer.refundable is True
    assert Capability.REFUND_RULES not in offer.capabilities
    assert offer.cancellation_summary is None
    with pytest.raises(AdapterUnavailableError):
        await adapter.get_refund_rules(offer.source_offer_id)


@pytest.mark.asyncio
async def test_flight_advertises_confirmed_non_refundable_status() -> None:
    response = json.loads(
        (FIXTURES / "snapptrip_flight_available.json").read_text(encoding="utf-8")
    )
    row = response["airfares"][0]
    row.pop("policies", None)
    row["refundType"] = "NON_REFUNDABLE"
    adapter = StubSnappTripFlightAdapter()

    async def fetch_rows(_payload):
        return [row]

    adapter._fetch_rows = fetch_rows

    offer = (
        await adapter.search(
            SearchRequest(
                mode="flight",
                origin="THR",
                destination="MHD",
                departure_date=date(2026, 9, 23),
            )
        )
    )[0]
    rules = await adapter.get_refund_rules(offer.source_offer_id)

    assert offer.capabilities == [Capability.REFUND_RULES]
    assert rules.refundable is False
    assert rules.summary == "این بلیت غیرقابل‌استرداد است."


@pytest.mark.asyncio
async def test_snapptrip_flight_reports_parse_drift_for_all_malformed_rows() -> None:
    adapter = StubSnappTripFlightAdapter()

    async def fetch_rows(_payload):
        return [{}]

    adapter._fetch_rows = fetch_rows

    with pytest.raises(AdapterUnavailableError, match="ساختار همه"):
        await adapter.search(
            SearchRequest(
                mode="flight",
                origin="THR",
                destination="MHD",
                departure_date=date(2026, 9, 23),
            )
        )
