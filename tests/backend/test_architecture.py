from __future__ import annotations

from pathlib import Path

import yaml
from app.adapters import Safar724BusAdapter as PublicSafar724BusAdapter
from app.adapters import SnappTripTrainAdapter as PublicSnappTripTrainAdapter
from app.adapters.alibaba import (
    AlibabaBusAdapter,
    AlibabaFlightAdapter,
    AlibabaTrainAdapter,
)
from app.adapters.booking import BookingFlightAdapter
from app.adapters.flytoday import FlyTodayBusAdapter, FlyTodayFlightAdapter
from app.adapters.mrbilit import (
    MrBilitBusAdapter,
    MrBilitFlightAdapter,
    MrBilitTrainAdapter,
)
from app.adapters.payaneha import PayanehaBusAdapter
from app.adapters.registry import register_live_adapters
from app.adapters.safar724 import Safar724BusAdapter
from app.adapters.snapptrip import (
    SnappTripBusAdapter,
    SnappTripFlightAdapter,
    SnappTripTrainAdapter,
)
from app.domain.capabilities import Capability
from app.domain.travel import TravelMode
from app.main import create_app
from app.ports.capabilities import SupportsRefundRules, SupportsSeatSelection
from app.ports.travel_adapter import AdapterFactory

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]


def _allows_null(schema: dict[str, object]) -> bool:
    schema_type = schema.get("type")
    if schema_type == "null":
        return True
    if isinstance(schema_type, list) and "null" in schema_type:
        return True
    return any(
        isinstance(option, dict) and _allows_null(option)
        for keyword in ("anyOf", "oneOf")
        for option in schema.get(keyword, [])
    )


def test_runtime_registers_only_verified_provider_mode_pairs() -> None:
    factory = AdapterFactory()

    register_live_adapters(factory)

    expected = {
        TravelMode.FLIGHT: AlibabaFlightAdapter,
        TravelMode.TRAIN: AlibabaTrainAdapter,
        TravelMode.BUS: AlibabaBusAdapter,
    }
    for mode, adapter_type in expected.items():
        adapter = factory.get(mode, "alibaba")
        assert isinstance(adapter, adapter_type)
        assert adapter.mode is mode
        assert adapter.provider == "alibaba"
        assert adapter in factory.adapters_for(mode)
    snapptrip_expected = {
        TravelMode.FLIGHT: SnappTripFlightAdapter,
        TravelMode.TRAIN: SnappTripTrainAdapter,
        TravelMode.BUS: SnappTripBusAdapter,
    }
    for mode, adapter_type in snapptrip_expected.items():
        adapter = factory.get(mode, "snapptrip")
        assert isinstance(adapter, adapter_type)
        assert adapter.mode is mode
        assert adapter.provider == "snapptrip"
        assert adapter in factory.adapters_for(mode)
    mrbilit_expected = {
        TravelMode.FLIGHT: MrBilitFlightAdapter,
        TravelMode.TRAIN: MrBilitTrainAdapter,
        TravelMode.BUS: MrBilitBusAdapter,
    }
    for mode, adapter_type in mrbilit_expected.items():
        adapter = factory.get(mode, "mrbilit")
        assert isinstance(adapter, adapter_type)
        assert adapter.mode is mode
        assert adapter.provider == "mrbilit"
        assert adapter in factory.adapters_for(mode)
    flytoday_flight = factory.get(TravelMode.FLIGHT, "flytoday")
    assert isinstance(flytoday_flight, FlyTodayFlightAdapter)
    assert flytoday_flight in factory.adapters_for(TravelMode.FLIGHT)
    flytoday_bus = factory.get(TravelMode.BUS, "flytoday")
    assert isinstance(flytoday_bus, FlyTodayBusAdapter)
    assert flytoday_bus in factory.adapters_for(TravelMode.BUS)
    safar724_bus = factory.get(TravelMode.BUS, "safar724")
    assert isinstance(safar724_bus, Safar724BusAdapter)
    assert safar724_bus in factory.adapters_for(TravelMode.BUS)
    booking_flight = factory.get(TravelMode.FLIGHT, "booking")
    assert isinstance(booking_flight, BookingFlightAdapter)
    assert booking_flight in factory.adapters_for(TravelMode.FLIGHT)
    payaneha_bus = factory.get(TravelMode.BUS, "payaneha")
    assert isinstance(payaneha_bus, PayanehaBusAdapter)
    assert payaneha_bus in factory.adapters_for(TravelMode.BUS)

    registered_sellers = {
        adapter.seller.id: adapter.seller
        for mode in TravelMode
        for adapter in factory.adapters_for(mode)
    }
    assert set(registered_sellers) == {
        "alibaba",
        "booking",
        "flytoday",
        "mrbilit",
        "payaneha",
        "safar724",
        "snapptrip",
    }
    for seller in registered_sellers.values():
        assert seller.logo_url is not None
        assert str(seller.logo_url).startswith("https://")
        assert seller.logo_alt == f"نشان فروشنده {seller.name}"
        assert seller.logo_fallback


def test_root_adapter_package_exports_snapptrip_train_adapter() -> None:
    assert PublicSnappTripTrainAdapter is SnappTripTrainAdapter
    assert PublicSafar724BusAdapter is Safar724BusAdapter


def test_capabilities_are_small_optional_protocols() -> None:
    flight = AlibabaFlightAdapter()
    train = AlibabaTrainAdapter()
    bus = AlibabaBusAdapter()
    snapptrip_flight = SnappTripFlightAdapter()
    snapptrip_bus = SnappTripBusAdapter()
    snapptrip_train = SnappTripTrainAdapter()
    mrbilit_flight = MrBilitFlightAdapter()
    mrbilit_train = MrBilitTrainAdapter()
    mrbilit_bus = MrBilitBusAdapter()
    flytoday_flight = FlyTodayFlightAdapter()
    flytoday_bus = FlyTodayBusAdapter()
    safar724_bus = Safar724BusAdapter()
    booking_flight = BookingFlightAdapter()
    payaneha_bus = PayanehaBusAdapter()

    assert isinstance(flight, SupportsRefundRules)
    assert not isinstance(flight, SupportsSeatSelection)
    assert not isinstance(train, SupportsRefundRules)
    assert not isinstance(train, SupportsSeatSelection)
    assert isinstance(bus, SupportsRefundRules)
    assert isinstance(bus, SupportsSeatSelection)
    assert isinstance(snapptrip_flight, SupportsRefundRules)
    assert not isinstance(snapptrip_flight, SupportsSeatSelection)
    assert not isinstance(snapptrip_bus, SupportsRefundRules)
    assert not isinstance(snapptrip_bus, SupportsSeatSelection)
    assert not isinstance(snapptrip_train, SupportsRefundRules)
    assert not isinstance(snapptrip_train, SupportsSeatSelection)
    assert isinstance(mrbilit_flight, SupportsRefundRules)
    assert isinstance(mrbilit_train, SupportsRefundRules)
    assert isinstance(mrbilit_bus, SupportsRefundRules)
    assert not isinstance(mrbilit_flight, SupportsSeatSelection)
    assert not isinstance(mrbilit_train, SupportsSeatSelection)
    assert not isinstance(mrbilit_bus, SupportsSeatSelection)
    assert not isinstance(flytoday_flight, SupportsRefundRules)
    assert not isinstance(flytoday_flight, SupportsSeatSelection)
    assert not isinstance(flytoday_bus, SupportsRefundRules)
    assert not isinstance(flytoday_bus, SupportsSeatSelection)
    assert isinstance(safar724_bus, SupportsRefundRules)
    assert not isinstance(safar724_bus, SupportsSeatSelection)
    assert not isinstance(booking_flight, SupportsRefundRules)
    assert not isinstance(booking_flight, SupportsSeatSelection)
    assert not isinstance(payaneha_bus, SupportsRefundRules)
    assert not isinstance(payaneha_bus, SupportsSeatSelection)


def test_product_runtime_contains_no_demo_or_fixture_fallback() -> None:
    forbidden = ("ENABLE_DEMO_FALLBACK", "getOffers", "example.com/ota")
    product_files = [
        *REPOSITORY_ROOT.glob("backend/app/**/*.py"),
        *REPOSITORY_ROOT.glob("frontend/app/**/*.tsx"),
        *REPOSITORY_ROOT.glob("frontend/components/**/*.tsx"),
        *REPOSITORY_ROOT.glob("frontend/lib/**/*.ts"),
    ]

    for path in product_files:
        contents = path.read_text(encoding="utf-8")
        assert all(token not in contents for token in forbidden), path


def test_static_openapi_matches_runtime_capability_and_redirect_contract() -> None:
    static_schema = yaml.safe_load(
        (REPOSITORY_ROOT / "contracts/openapi.yaml").read_text(encoding="utf-8")
    )
    runtime_schema = create_app().openapi()
    static_components = static_schema["components"]["schemas"]
    runtime_components = runtime_schema["components"]["schemas"]

    assert static_components["Capability"]["enum"] == [item.value for item in Capability]
    assert static_components["NormalizedOffer"]["required"] == runtime_components[
        "NormalizedOffer"
    ]["required"]
    assert static_components["OfferGroup"]["required"] == runtime_components["OfferGroup"][
        "required"
    ]
    assert "RedirectTarget" not in static_components
    assert "RedirectTarget" not in runtime_components
    assert "redirect" not in static_components["NormalizedOffer"]["properties"]
    assert "redirect" not in runtime_components["NormalizedOffer"]["properties"]
    assert "provider" in static_components["RedirectPreview"]["required"]


def test_provider_source_offer_ids_are_internal_only() -> None:
    static_schema = yaml.safe_load(
        (REPOSITORY_ROOT / "contracts/openapi.yaml").read_text(encoding="utf-8")
    )
    runtime_schema = create_app().openapi()

    for schema in (static_schema, runtime_schema):
        components = schema["components"]["schemas"]
        assert "source_offer_id" not in components["NormalizedOffer"]["properties"]
        assert "source_offer_id" not in components["OfferDetails"]["properties"]
        assert "source_offer_id" not in components["NormalizedOffer"]["required"]
        assert "source_offer_id" not in components["OfferDetails"]["required"]
        assert "seller_offer_id" in components["OfferDetails"]["required"]

    typescript_contract = (REPOSITORY_ROOT / "contracts/travel.ts").read_text(
        encoding="utf-8"
    )
    assert "source_offer_id" not in typescript_contract
    assert "seller_offer_id" in typescript_contract


def test_redirect_targets_are_internal_only() -> None:
    static_schema = yaml.safe_load(
        (REPOSITORY_ROOT / "contracts/openapi.yaml").read_text(encoding="utf-8")
    )
    runtime_schema = create_app().openapi()

    for schema in (static_schema, runtime_schema):
        components = schema["components"]["schemas"]
        assert "RedirectTarget" not in components
        assert "redirect" not in components["NormalizedOffer"]["properties"]
        assert "url" in components["RedirectPreview"]["properties"]

    typescript_contract = (REPOSITORY_ROOT / "contracts/travel.ts").read_text(
        encoding="utf-8"
    )
    assert "interface RedirectTarget" not in typescript_contract
    normalized_offer = typescript_contract.split("export interface NormalizedOffer", 1)[1]
    normalized_offer = normalized_offer.split("\n}", 1)[0]
    assert "redirect:" not in normalized_offer


def test_static_public_response_properties_match_runtime_openapi() -> None:
    static_schema = yaml.safe_load(
        (REPOSITORY_ROOT / "contracts/openapi.yaml").read_text(encoding="utf-8")
    )
    runtime_schema = create_app().openapi()
    static_components = static_schema["components"]["schemas"]
    runtime_components = runtime_schema["components"]["schemas"]

    response_models = (
        "NormalizedOffer",
        "OfferDetails",
        "OfferGroup",
        "RefundRules",
        "Seat",
        "SeatMap",
        "TravelLocation",
        "LocationSearchResponse",
        "RedirectPreview",
        "SearchLegResponse",
        "SearchResponse",
    )
    for component_name in response_models:
        assert set(static_components[component_name]["properties"]) == set(
            runtime_components[component_name]["properties"]
        )
        assert static_components[component_name].get("required", []) == (
            runtime_components[component_name].get("required", [])
        )


def test_static_contract_required_fields_match_runtime_for_shared_components() -> None:
    static_schema = yaml.safe_load(
        (REPOSITORY_ROOT / "contracts/openapi.yaml").read_text(encoding="utf-8")
    )
    runtime_schema = create_app().openapi()
    static_components = static_schema["components"]["schemas"]
    runtime_components = runtime_schema["components"]["schemas"]

    for component_name in static_components.keys() & runtime_components.keys():
        assert static_components[component_name].get("required", []) == (
            runtime_components[component_name].get("required", [])
        ), component_name


def test_background_search_contract_matches_runtime_surface() -> None:
    static_schema = yaml.safe_load(
        (REPOSITORY_ROOT / "contracts/openapi.yaml").read_text(encoding="utf-8")
    )
    runtime_schema = create_app().openapi()

    static_create = static_schema["paths"]["/api/v1/search-jobs"]["post"]
    runtime_create = runtime_schema["paths"]["/api/v1/search-jobs"]["post"]
    assert static_create["operationId"] == runtime_create["operationId"]
    assert static_create["requestBody"]["content"]["application/json"]["schema"] == (
        runtime_create["requestBody"]["content"]["application/json"]["schema"]
    )
    assert static_create["responses"]["202"]["content"]["application/json"][
        "schema"
    ] == runtime_create["responses"]["202"]["content"]["application/json"][
        "schema"
    ]
    assert set(static_create["responses"]["202"]["headers"]) == {
        "Location",
        "Retry-After",
    }
    assert set(runtime_create["responses"]["202"]["headers"]) == {
        "Location",
        "Retry-After",
    }
    assert static_create["responses"]["503"]["content"]["application/json"][
        "schema"
    ]["$ref"] == "#/components/schemas/ErrorResponse"

    static_status = static_schema["paths"]["/api/v1/search-jobs/{search_id}"]["get"]
    runtime_status = runtime_schema["paths"]["/api/v1/search-jobs/{search_id}"]["get"]
    assert static_status["operationId"] == runtime_status["operationId"]
    assert static_status["responses"]["200"]["content"]["application/json"][
        "schema"
    ] == runtime_status["responses"]["200"]["content"]["application/json"][
        "schema"
    ]
    assert static_status["responses"]["404"]["content"]["application/json"][
        "schema"
    ]["$ref"] == "#/components/schemas/ErrorResponse"

    static_components = static_schema["components"]["schemas"]
    runtime_components = runtime_schema["components"]["schemas"]
    for component_name in (
        "SearchJobAccepted",
        "SearchJobError",
        "SearchJobStatus",
        "SearchJobStatusResponse",
    ):
        assert set(static_components[component_name].get("properties", {})) == set(
            runtime_components[component_name].get("properties", {})
        )
        assert static_components[component_name].get("required", []) == (
            runtime_components[component_name].get("required", [])
        )

    assert static_components["SearchJobAccepted"]["properties"]["status"][
        "const"
    ] == "queued"
    assert static_components["SearchJobStatus"]["enum"] == [
        "queued",
        "running",
        "completed",
        "failed",
    ]


def test_static_openapi_matches_runtime_optional_journey_fields() -> None:
    static_schema = yaml.safe_load(
        (REPOSITORY_ROOT / "contracts/openapi.yaml").read_text(encoding="utf-8")
    )
    runtime_schema = create_app().openapi()
    static_components = static_schema["components"]["schemas"]
    runtime_components = runtime_schema["components"]["schemas"]

    optional_fields = {
        "OfferAttributes": ("stops",),
        "BusDetails": (
            "service_number",
            "seat_selection_available",
            "capacity",
            "cancellation_policy",
        ),
        "NormalizedOffer": ("arrival_at", "duration_minutes"),
        "OfferGroup": ("arrival_at", "duration_minutes"),
    }
    for component_name, fields in optional_fields.items():
        static_component = static_components[component_name]
        runtime_component = runtime_components[component_name]
        for field in fields:
            assert field not in static_component.get("required", [])
            assert field not in runtime_component.get("required", [])
            assert _allows_null(static_component["properties"][field])
            assert _allows_null(runtime_component["properties"][field])

    assert static_components["BusDetails"]["properties"]["service_number"][
        "maxLength"
    ] == runtime_components["BusDetails"]["properties"]["service_number"][
        "anyOf"
    ][0]["maxLength"]


def test_seller_reputation_is_explicitly_unknown_when_not_verified() -> None:
    static_schema = yaml.safe_load(
        (REPOSITORY_ROOT / "contracts/openapi.yaml").read_text(encoding="utf-8")
    )
    runtime_schema = create_app().openapi()

    for schema in (static_schema, runtime_schema):
        seller = schema["components"]["schemas"]["Seller"]
        for field in ("rating", "review_count"):
            assert field not in seller.get("required", [])
            assert _allows_null(seller["properties"][field])


def test_static_openapi_does_not_require_defaulted_redirect_fields() -> None:
    static_schema = yaml.safe_load(
        (REPOSITORY_ROOT / "contracts/openapi.yaml").read_text(encoding="utf-8")
    )
    runtime_schema = create_app().openapi()

    static_required = static_schema["components"]["schemas"]["RedirectPreview"][
        "required"
    ]
    runtime_required = runtime_schema["components"]["schemas"]["RedirectPreview"][
        "required"
    ]
    assert static_required == runtime_required


def test_static_openapi_documents_every_runtime_operation() -> None:
    static_schema = yaml.safe_load(
        (REPOSITORY_ROOT / "contracts/openapi.yaml").read_text(encoding="utf-8")
    )
    runtime_schema = create_app().openapi()

    for path, runtime_path_item in runtime_schema["paths"].items():
        assert path in static_schema["paths"]
        for method in runtime_path_item:
            assert method in static_schema["paths"][path]


def test_static_openapi_operation_ids_match_runtime_exactly() -> None:
    static_schema = yaml.safe_load(
        (REPOSITORY_ROOT / "contracts/openapi.yaml").read_text(encoding="utf-8")
    )
    runtime_schema = create_app().openapi()

    static_operations = {
        (path, method): operation["operationId"]
        for path, path_item in static_schema["paths"].items()
        for method, operation in path_item.items()
        if method in {"get", "post", "put", "patch", "delete"}
    }
    runtime_operations = {
        (path, method): operation["operationId"]
        for path, path_item in runtime_schema["paths"].items()
        for method, operation in path_item.items()
        if method in {"get", "post", "put", "patch", "delete"}
    }

    assert static_operations == runtime_operations


def test_static_openapi_matches_runtime_capability_response_models() -> None:
    static_schema = yaml.safe_load(
        (REPOSITORY_ROOT / "contracts/openapi.yaml").read_text(encoding="utf-8")
    )
    runtime_schema = create_app().openapi()
    static_components = static_schema["components"]["schemas"]
    runtime_components = runtime_schema["components"]["schemas"]

    for component_name in ("OfferDetails", "RefundRules", "Seat", "SeatMap"):
        assert static_components[component_name]["required"] == runtime_components[
            component_name
        ]["required"]

    for coordinate in ("row", "column"):
        assert _allows_null(static_components["Seat"]["properties"][coordinate])
        assert _allows_null(runtime_components["Seat"]["properties"][coordinate])

    capability_responses = {
        "/api/v1/offers/{offer_id}/details": "OfferDetails",
        "/api/v1/offers/{offer_id}/refund-rules": "RefundRules",
        "/api/v1/offers/{offer_id}/seat-map": "SeatMap",
    }
    for path, component_name in capability_responses.items():
        expected_ref = f"#/components/schemas/{component_name}"
        assert static_schema["paths"][path]["get"]["responses"]["200"]["content"][
            "application/json"
        ]["schema"]["$ref"] == expected_ref
        assert runtime_schema["paths"][path]["get"]["responses"]["200"]["content"][
            "application/json"
        ]["schema"]["$ref"] == expected_ref


def test_static_search_contract_matches_runtime_validation_rules() -> None:
    static_schema = yaml.safe_load(
        (REPOSITORY_ROOT / "contracts/openapi.yaml").read_text(encoding="utf-8")
    )
    search_request = static_schema["components"]["schemas"]["SearchRequest"]

    assert search_request["properties"]["return_date"] == {
        "type": ["string", "null"],
        "format": "date",
        "description": "Optional return date; must be later than departure_date.",
    }

    mode_rules = {
        rule["properties"]["mode"]["const"]: rule["properties"]
        for rule in search_request["oneOf"]
    }
    expected_preferences = {
        "flight": "FlightSearchPreferences",
        "train": "TrainSearchPreferences",
        "bus": "BusSearchPreferences",
    }
    for mode, component_name in expected_preferences.items():
        assert mode_rules[mode]["preferences"]["anyOf"][0]["$ref"] == (
            f"#/components/schemas/{component_name}"
        )

    assert mode_rules["flight"]["passengers"]["$ref"].endswith("/PassengerCounts")
    for mode in ("train", "bus"):
        assert mode_rules[mode]["passengers"]["$ref"].endswith(
            "/GroundPassengerCounts"
        )


def test_typescript_search_contract_matches_runtime_validation_rules() -> None:
    typescript_contract = (REPOSITORY_ROOT / "contracts/travel.ts").read_text(
        encoding="utf-8"
    )
    search_request = typescript_contract.split("export type SearchRequest =", 1)[1]
    search_request = search_request.split("export type LocationKind", 1)[0]

    assert "return_date?: string | null;" in typescript_contract
    assert search_request.count("passengers?: GroundPassengerCounts;") == 2
    assert "preferences?: FlightSearchPreferences | null;" in search_request
    assert "preferences?: TrainSearchPreferences | null;" in search_request
    assert "preferences?: BusSearchPreferences | null;" in search_request


def test_static_openapi_documents_adapter_unavailable_responses() -> None:
    static_schema = yaml.safe_load(
        (REPOSITORY_ROOT / "contracts/openapi.yaml").read_text(encoding="utf-8")
    )
    paths = (
        "/api/v1/offers/{offer_id}/redirect",
        "/api/v1/offers/{offer_id}/details",
        "/api/v1/offers/{offer_id}/refund-rules",
        "/api/v1/offers/{offer_id}/seat-map",
    )

    for path in paths:
        response = static_schema["paths"][path]["get"]["responses"]["503"]
        assert response["content"]["application/json"]["schema"]["$ref"] == (
            "#/components/schemas/ErrorResponse"
        )


def test_response_fixtures_are_not_shipped() -> None:
    assert not list((REPOSITORY_ROOT / "contracts/fixtures").glob("*.response.json"))
