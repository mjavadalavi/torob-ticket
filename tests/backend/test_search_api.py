from __future__ import annotations

import pytest
from httpx import AsyncClient


def search_payload(*, mode: str = "flight", intent: str = "best") -> dict[str, object]:
    return {
        "mode": mode,
        "origin": "THR",
        "destination": "MHD",
        "departure_date": "2030-01-15",
        "passengers": {"adults": 1, "children": 0, "infants": 0},
        "intent": intent,
    }


@pytest.mark.asyncio
async def test_search_groups_identical_journeys_by_seller(client: AsyncClient) -> None:
    response = await client.post("/api/v1/search", json=search_payload())

    assert response.status_code == 200
    body = response.json()
    assert body["mode"] == "flight"
    assert body["intent"] == "best"
    assert body["total"] == 3
    assert body["providers_queried"] == 2
    assert body["providers_succeeded"] == 2
    assert body["provider_failures"] == []
    assert all(offer["passenger_count"] == 1 for offer in body["offers"])
    assert [offer["rank"] for offer in body["offers"]] == [1, 2, 3]
    assert all(offer["seller_count"] == 2 for offer in body["offers"])
    assert all(len(offer["seller_offers"]) == 2 for offer in body["offers"])
    assert "journey_key" not in body["offers"][0]["seller_offers"][0]
    assert "source_offer_id" not in body["offers"][0]["seller_offers"][0]
    assert "redirect" not in body["offers"][0]["seller_offers"][0]


@pytest.mark.asyncio
async def test_search_exposes_accessible_operator_and_seller_branding(
    client: AsyncClient,
) -> None:
    response = await client.post("/api/v1/search", json=search_payload())

    seller_offer = response.json()["offers"][0]["seller_offers"][0]
    assert seller_offer["seller"]["logo_alt"].startswith("نشان فروشنده ")
    assert seller_offer["seller"]["logo_fallback"]
    assert seller_offer["attributes"]["operator_logo_alt"].startswith(
        "نشان شرکت "
    )
    assert seller_offer["attributes"]["operator_logo_fallback"]


@pytest.mark.asyncio
@pytest.mark.parametrize("mode", ["flight", "train", "bus"])
async def test_all_travel_modes_follow_the_same_contract(
    client: AsyncClient,
    mode: str,
) -> None:
    response = await client.post("/api/v1/search", json=search_payload(mode=mode))

    assert response.status_code == 200
    body = response.json()
    assert body["mode"] == mode
    assert body["offers"]
    assert {offer["mode"] for offer in body["offers"]} == {mode}
    assert "torob_guarantee" in body["offers"][0]["available_capabilities"]
    assert "torob_pay" in body["offers"][0]["available_capabilities"]


@pytest.mark.asyncio
async def test_flight_details_survive_normalization(client: AsyncClient) -> None:
    response = await client.post("/api/v1/search", json=search_payload(mode="flight"))

    details = response.json()["offers"][0]["mode_details"]
    seller_details = response.json()["offers"][0]["seller_offers"][0]["mode_details"]
    assert details == seller_details
    assert details["mode"] == "flight"
    assert details["origin_airport_code"] == "THR"
    assert details["destination_airport_code"] == "MHD"
    assert details["airline"]
    assert details["flight_number"]
    assert details["fare_type"] in {"system", "charter"}
    assert details["baggage_allowance_kg"] == 20


@pytest.mark.asyncio
async def test_train_details_survive_normalization(client: AsyncClient) -> None:
    response = await client.post("/api/v1/search", json=search_payload(mode="train"))

    details = response.json()["offers"][0]["mode_details"]
    seller_details = response.json()["offers"][0]["seller_offers"][0]["mode_details"]
    assert details == seller_details
    assert details["mode"] == "train"
    assert details["railway_company"]
    assert details["compartment_capacity"] in {4, 6}
    assert details["private_compartment_available"] is True
    assert details["women_only_available"] is True
    assert isinstance(details["vehicle_transport_available"], bool)


@pytest.mark.asyncio
async def test_bus_details_survive_normalization(client: AsyncClient) -> None:
    response = await client.post("/api/v1/search", json=search_payload(mode="bus"))

    details = response.json()["offers"][0]["mode_details"]
    seller_details = response.json()["offers"][0]["seller_offers"][0]["mode_details"]
    assert details == seller_details
    assert details["mode"] == "bus"
    assert details["origin_terminal"] == "پایانه مبدأ آزمون"
    assert details["destination_terminal"] == "پایانه مقصد آزمون"
    assert details["company"]
    assert details["seat_selection_available"] is True
    assert details["capacity"] in {25, 32}
    assert details["cancellation_policy"]


@pytest.mark.asyncio
async def test_cheapest_intent_orders_by_lowest_price(client: AsyncClient) -> None:
    response = await client.post(
        "/api/v1/search",
        json=search_payload(intent="cheapest"),
    )

    prices = [offer["lowest_price"]["amount"] for offer in response.json()["offers"]]
    assert prices == sorted(prices)
    assert response.json()["offers"][0]["recommendation_reasons"] == ["lowest_price"]


@pytest.mark.asyncio
async def test_grouped_offer_states_the_total_price_passenger_scope(
    client: AsyncClient,
) -> None:
    payload = search_payload()
    payload["passengers"] = {"adults": 2, "children": 1, "infants": 0}

    response = await client.post("/api/v1/search", json=payload)

    assert response.status_code == 200
    assert {
        offer["passenger_count"] for offer in response.json()["offers"]
    } == {3}


@pytest.mark.asyncio
async def test_fastest_intent_orders_by_duration(client: AsyncClient) -> None:
    response = await client.post(
        "/api/v1/search",
        json=search_payload(mode="bus", intent="fastest"),
    )

    durations = [offer["duration_minutes"] for offer in response.json()["offers"]]
    assert durations == sorted(durations)
    assert response.json()["offers"][0]["recommendation_reasons"] == [
        "shortest_travel_time"
    ]


@pytest.mark.asyncio
async def test_search_rejects_same_origin_and_destination(client: AsyncClient) -> None:
    payload = search_payload()
    payload["destination"] = "thr"

    response = await client.post("/api/v1/search", json=payload)

    assert response.status_code == 422


@pytest.mark.asyncio
async def test_search_rejects_preferences_for_another_mode(client: AsyncClient) -> None:
    payload = search_payload(mode="train")
    payload["preferences"] = {"mode": "bus", "seat_selection_required": True}

    response = await client.post("/api/v1/search", json=payload)

    assert response.status_code == 422


@pytest.mark.asyncio
async def test_search_returns_an_independently_ranked_reverse_leg(
    client: AsyncClient,
) -> None:
    payload = search_payload()
    payload["return_date"] = "2030-01-20"

    response = await client.post("/api/v1/search", json=payload)

    assert response.status_code == 200
    body = response.json()
    assert body["offers"]
    assert body["return_leg"]["offers"]
    assert body["return_leg"]["total"] == body["total"]
    assert body["return_leg"]["providers_queried"] == 2
    assert body["return_leg"]["providers_succeeded"] == 2
    assert body["return_leg"]["provider_failures"] == []
    assert {offer["origin"] for offer in body["offers"]} == {"THR"}
    assert {offer["destination"] for offer in body["offers"]} == {"MHD"}
    assert {offer["origin"] for offer in body["return_leg"]["offers"]} == {
        "MHD"
    }
    assert {offer["destination"] for offer in body["return_leg"]["offers"]} == {
        "THR"
    }
    assert [offer["rank"] for offer in body["return_leg"]["offers"]] == [1, 2, 3]


@pytest.mark.asyncio
@pytest.mark.parametrize("return_date", ("2030-01-14", "2030-01-15"))
async def test_search_rejects_return_date_not_after_departure(
    client: AsyncClient,
    return_date: str,
) -> None:
    payload = search_payload()
    payload["return_date"] = return_date

    response = await client.post("/api/v1/search", json=payload)

    assert response.status_code == 422


@pytest.mark.asyncio
@pytest.mark.parametrize("mode", ["train", "bus"])
@pytest.mark.parametrize(
    "passengers",
    [
        {"adults": 1, "children": 1, "infants": 0},
        {"adults": 1, "children": 0, "infants": 1},
    ],
)
async def test_ground_search_rejects_unverified_minor_passenger_pricing(
    client: AsyncClient,
    mode: str,
    passengers: dict[str, int],
) -> None:
    payload = search_payload(mode=mode)
    payload["passengers"] = passengers

    response = await client.post("/api/v1/search", json=payload)

    assert response.status_code == 422
