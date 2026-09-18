from __future__ import annotations

import pytest
from app.domain.travel import TravelMode
from app.ports.travel_adapter import AdapterFactory
from fakes import FakeTravelAdapter


def make_adapter() -> FakeTravelAdapter:
    return FakeTravelAdapter(mode=TravelMode.FLIGHT, provider="test_ota")


def test_factory_resolves_adapter_by_mode_and_provider() -> None:
    factory = AdapterFactory()
    adapter = make_adapter()
    factory.register(adapter)

    assert factory.adapters_for(TravelMode.FLIGHT) == (adapter,)
    assert factory.get(TravelMode.FLIGHT, "test_ota") is adapter
    assert factory.adapters_for(TravelMode.BUS) == ()


def test_factory_rejects_duplicate_registration() -> None:
    factory = AdapterFactory()
    factory.register(make_adapter())

    with pytest.raises(ValueError, match="already registered"):
        factory.register(make_adapter())


def test_new_provider_registration_does_not_require_factory_changes() -> None:
    factory = AdapterFactory()
    adapter = FakeTravelAdapter(mode=TravelMode.BUS, provider="new_ota")

    factory.register(adapter)

    assert factory.get(TravelMode.BUS, "new_ota") is adapter
