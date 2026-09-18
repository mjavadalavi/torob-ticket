from __future__ import annotations

from collections import Counter
from pathlib import Path
from urllib.parse import urlparse

import pytest
import yaml

from app.core.config import Settings
from app.domain.travel import TravelMode
from app.main import create_app
from app.services.provider_support import (
    PROVIDER_SUPPORT_CATALOG,
    ProviderSupportStatus,
)


EXPECTED_PROVIDER_MODE_PAIRS = {
    # Train.
    (TravelMode.TRAIN, "flytoday"),
    (TravelMode.TRAIN, "mrbilit"),
    (TravelMode.TRAIN, "alibaba"),
    (TravelMode.TRAIN, "raja"),
    (TravelMode.TRAIN, "snapptrip"),
    (TravelMode.TRAIN, "booking"),
    (TravelMode.TRAIN, "ghasedak24"),
    (TravelMode.TRAIN, "fadak"),
    # Flight.
    (TravelMode.FLIGHT, "flytoday"),
    (TravelMode.FLIGHT, "mrbilit"),
    (TravelMode.FLIGHT, "alibaba"),
    (TravelMode.FLIGHT, "safarmarket"),
    (TravelMode.FLIGHT, "booking"),
    (TravelMode.FLIGHT, "snapptrip"),
    (TravelMode.FLIGHT, "eligasht"),
    (TravelMode.FLIGHT, "snapp_flights"),
    (TravelMode.FLIGHT, "trip"),
    # Bus.
    (TravelMode.BUS, "mrbilit"),
    (TravelMode.BUS, "alibaba"),
    (TravelMode.BUS, "safar724"),
    (TravelMode.BUS, "snapptrip"),
    (TravelMode.BUS, "flytoday"),
    (TravelMode.BUS, "payaneh_ir"),
    (TravelMode.BUS, "ghasedak24"),
    (TravelMode.BUS, "safarmarket"),
    (TravelMode.BUS, "bazargah"),
    (TravelMode.BUS, "payaneha"),
}
REPOSITORY_ROOT = Path(__file__).resolve().parents[2]


def test_catalog_represents_every_user_supplied_provider_mode_pair_once() -> None:
    actual_pairs = [
        (record.mode, record.provider_id) for record in PROVIDER_SUPPORT_CATALOG
    ]

    assert len(actual_pairs) == 27
    assert set(actual_pairs) == EXPECTED_PROVIDER_MODE_PAIRS
    assert Counter(actual_pairs).most_common(1)[0][1] == 1
    assert Counter(record.mode for record in PROVIDER_SUPPORT_CATALOG) == {
        TravelMode.TRAIN: 8,
        TravelMode.FLIGHT: 9,
        TravelMode.BUS: 10,
    }


def test_catalog_registration_exactly_matches_runtime_factory() -> None:
    application = create_app()
    factory = application.state.adapter_factory
    actual_pairs = {
        (mode, adapter.provider)
        for mode in TravelMode
        for adapter in factory.adapters_for(mode)
    }
    catalog_registered_pairs = {
        (record.mode, record.provider_id)
        for record in PROVIDER_SUPPORT_CATALOG
        if record.status is ProviderSupportStatus.REGISTERED
    }

    assert len(actual_pairs) == 14
    assert catalog_registered_pairs == actual_pairs
    assert all(
        record.adapter_registered
        is (record.status is ProviderSupportStatus.REGISTERED)
        for record in PROVIDER_SUPPORT_CATALOG
    )
    assert all(
        (record.mode, record.provider_id) not in actual_pairs
        for record in PROVIDER_SUPPORT_CATALOG
        if record.status is not ProviderSupportStatus.REGISTERED
    )


def test_default_redirect_allowlist_exactly_matches_registered_providers() -> None:
    application = create_app()
    registered_providers = {
        adapter.provider
        for mode in TravelMode
        for adapter in application.state.adapter_factory.adapters_for(mode)
    }

    assert set(Settings().redirect_hosts_by_provider) == registered_providers


def test_every_provider_status_has_a_persian_reason_and_official_https_url() -> None:
    for record in PROVIDER_SUPPORT_CATALOG:
        assert record.reason_fa
        assert any("\u0600" <= character <= "\u06ff" for character in record.reason_fa)
        parsed_url = urlparse(str(record.official_url))
        assert parsed_url.scheme == "https"
        assert parsed_url.hostname


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("mode", "expected_count"),
    [("flight", 9), ("train", 8), ("bus", 10)],
)
async def test_provider_support_endpoint_lists_audited_mode_catalog(
    client,
    mode: str,
    expected_count: int,
) -> None:
    response = await client.get("/api/v1/providers", params={"mode": mode})

    assert response.status_code == 200
    body = response.json()
    assert body["mode"] == mode
    assert len(body["providers"]) == expected_count
    assert all(record["mode"] == mode for record in body["providers"])
    assert all("adapter_registered" in record for record in body["providers"])


@pytest.mark.asyncio
async def test_provider_support_endpoint_rejects_unknown_mode(client) -> None:
    response = await client.get("/api/v1/providers", params={"mode": "hotel"})

    assert response.status_code == 422


def test_provider_support_static_contract_matches_runtime() -> None:
    static_schema = yaml.safe_load(
        (REPOSITORY_ROOT / "contracts/openapi.yaml").read_text(encoding="utf-8")
    )
    runtime_schema = create_app().openapi()

    static_operation = static_schema["paths"]["/api/v1/providers"]["get"]
    runtime_operation = runtime_schema["paths"]["/api/v1/providers"]["get"]
    assert static_operation["operationId"] == runtime_operation["operationId"]
    assert static_operation["responses"]["200"]["content"]["application/json"][
        "schema"
    ] == runtime_operation["responses"]["200"]["content"]["application/json"][
        "schema"
    ]

    for component_name in (
        "ProviderSupportStatus",
        "ProviderSupportRecord",
        "ProviderSupportResponse",
    ):
        static_component = static_schema["components"]["schemas"][component_name]
        runtime_component = runtime_schema["components"]["schemas"][component_name]
        assert set(static_component.get("properties", {})) == set(
            runtime_component.get("properties", {})
        )
        assert static_component.get("required", []) == runtime_component.get(
            "required", []
        )
