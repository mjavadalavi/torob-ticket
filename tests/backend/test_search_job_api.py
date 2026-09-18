from __future__ import annotations

import asyncio

import pytest
from httpx import AsyncClient
from test_search_api import search_payload


@pytest.mark.asyncio
async def test_search_job_api_accepts_immediately_and_returns_provider_neutral_result(
    client: AsyncClient,
) -> None:
    accepted = await client.post("/api/v1/search-jobs", json=search_payload(mode="bus"))

    assert accepted.status_code == 202
    accepted_body = accepted.json()
    assert accepted_body["status"] == "queued"
    assert accepted_body["search_id"].startswith("src_")
    assert accepted.headers["location"].endswith(
        f"/api/v1/search-jobs/{accepted_body['search_id']}"
    )
    assert accepted.headers["retry-after"] == "1"

    status_body = None
    for _ in range(100):
        status_response = await client.get(
            f"/api/v1/search-jobs/{accepted_body['search_id']}"
        )
        assert status_response.status_code == 200
        status_body = status_response.json()
        if status_body["status"] in {"completed", "failed"}:
            break
        await asyncio.sleep(0)

    assert status_body is not None
    assert status_body["status"] == "completed"
    assert status_body["error"] is None
    result = status_body["result"]
    assert result["search_id"] == accepted_body["search_id"]
    assert result["mode"] == "bus"
    assert result["providers_queried"] == 2
    assert result["providers_succeeded"] == 2
    assert result["offers"]
    assert all(offer["mode"] == "bus" for offer in result["offers"])


@pytest.mark.asyncio
async def test_round_trip_job_keeps_both_legs_under_one_search_id(
    client: AsyncClient,
) -> None:
    payload = search_payload(mode="flight")
    payload["return_date"] = "2030-01-20"
    accepted = await client.post("/api/v1/search-jobs", json=payload)
    search_id = accepted.json()["search_id"]

    result = None
    for _ in range(100):
        status_response = await client.get(f"/api/v1/search-jobs/{search_id}")
        status_body = status_response.json()
        if status_body["status"] == "completed":
            result = status_body["result"]
            break
        assert status_body["status"] != "failed"
        await asyncio.sleep(0)

    assert result is not None
    assert result["search_id"] == search_id
    assert result["return_leg"] is not None
    assert all(offer["id"].startswith(search_id) for offer in result["offers"])
    assert all(
        offer["id"].startswith(f"{search_id}_return_")
        for offer in result["return_leg"]["offers"]
    )


@pytest.mark.asyncio
async def test_completed_search_job_keeps_offer_available_for_redirect(
    client: AsyncClient,
) -> None:
    accepted = await client.post("/api/v1/search-jobs", json=search_payload(mode="bus"))
    search_id = accepted.json()["search_id"]

    result = None
    for _ in range(100):
        status_response = await client.get(f"/api/v1/search-jobs/{search_id}")
        status_body = status_response.json()
        if status_body["status"] == "completed":
            result = status_body["result"]
            break
        assert status_body["status"] != "failed"
        await asyncio.sleep(0)

    assert result is not None
    offer = result["offers"][0]
    seller_offer = offer["seller_offers"][0]
    response = await client.get(
        f"/api/v1/offers/{offer['id']}/redirect",
        params={"seller_offer_id": seller_offer["id"]},
    )

    assert response.status_code == 200
    assert response.json()["offer_id"] == offer["id"]
    assert response.json()["seller_offer_id"] == seller_offer["id"]


@pytest.mark.asyncio
async def test_search_job_api_returns_existing_not_found_envelope(
    client: AsyncClient,
) -> None:
    response = await client.get(
        "/api/v1/search-jobs/src_00000000000000000000000000000000"
    )

    assert response.status_code == 404
    assert response.json() == {
        "error": {
            "code": "resource_not_found",
            "message": "This search job was not found or has expired.",
        }
    }


@pytest.mark.asyncio
async def test_search_job_api_reuses_search_request_validation(
    client: AsyncClient,
) -> None:
    invalid = search_payload()
    invalid["destination"] = "thr"

    response = await client.post("/api/v1/search-jobs", json=invalid)

    assert response.status_code == 422
