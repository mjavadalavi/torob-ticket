from __future__ import annotations

from urllib.parse import urlparse

import pytest
from httpx import AsyncClient


async def create_offer(client: AsyncClient) -> dict[str, object]:
    response = await client.post(
        "/api/v1/search",
        json={
            "mode": "flight",
            "origin": "THR",
            "destination": "MHD",
            "departure_date": "2030-01-15",
            "intent": "best",
        },
    )
    assert response.status_code == 200
    return response.json()["offers"][0]


@pytest.mark.asyncio
async def test_get_offer_returns_all_sellers(client: AsyncClient) -> None:
    offer = await create_offer(client)

    response = await client.get(f"/api/v1/offers/{offer['id']}")

    assert response.status_code == 200
    assert response.json()["id"] == offer["id"]
    assert response.json()["seller_count"] == 2


@pytest.mark.asyncio
async def test_redirect_preview_selects_exact_seller_offer(client: AsyncClient) -> None:
    offer = await create_offer(client)
    seller_offer = offer["seller_offers"][1]

    response = await client.get(
        f"/api/v1/offers/{offer['id']}/redirect",
        params={"seller_offer_id": seller_offer["id"]},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["offer_id"] == offer["id"]
    assert body["seller_offer_id"] == seller_offer["id"]
    assert body["provider"] == seller_offer["provider"]
    assert body["seller_id"] == seller_offer["seller"]["id"]
    assert body["is_external"] is True
    assert body["notice_code"] == "external_checkout"
    assert urlparse(body["url"]).hostname == "www.alibaba.ir"


@pytest.mark.asyncio
async def test_redirect_preview_rejects_unrelated_seller_offer(client: AsyncClient) -> None:
    offer = await create_offer(client)

    response = await client.get(
        f"/api/v1/offers/{offer['id']}/redirect",
        params={"seller_offer_id": "sel_does_not_exist"},
    )

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "resource_not_found"


@pytest.mark.asyncio
async def test_unknown_offer_returns_structured_not_found(client: AsyncClient) -> None:
    response = await client.get("/api/v1/offers/off_missing")

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "resource_not_found"
