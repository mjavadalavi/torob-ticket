from __future__ import annotations

import pytest
from httpx import AsyncClient


async def search_bus(client: AsyncClient) -> tuple[dict[str, object], dict[str, object]]:
    response = await client.post(
        "/api/v1/search",
        json={
            "mode": "bus",
            "origin": "THR",
            "destination": "MHD",
            "departure_date": "2030-01-15",
        },
    )
    assert response.status_code == 200
    offer = response.json()["offers"][0]
    return offer, offer["seller_offers"][0]


@pytest.mark.asyncio
async def test_offer_capability_routes_resolve_internal_source_offer(
    client: AsyncClient,
) -> None:
    offer, seller_offer = await search_bus(client)
    params = {"seller_offer_id": seller_offer["id"]}

    details = await client.get(
        f"/api/v1/offers/{offer['id']}/details",
        params=params,
    )
    refund = await client.get(
        f"/api/v1/offers/{offer['id']}/refund-rules",
        params=params,
    )
    seats = await client.get(
        f"/api/v1/offers/{offer['id']}/seat-map",
        params=params,
    )

    assert details.status_code == 200
    assert details.json()["seller_offer_id"] == seller_offer["id"]
    assert "source_offer_id" not in details.json()
    assert refund.status_code == 200
    assert refund.json()["offer_id"] == seller_offer["id"]
    assert refund.json()["refundable"] is True
    assert seats.status_code == 200
    assert seats.json()["offer_id"] == seller_offer["id"]
    assert seats.json()["seats"][0] == {
        "number": "1",
        "row": 1,
        "column": 1,
        "available": True,
        "price_delta": 0,
    }
