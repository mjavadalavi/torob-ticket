from __future__ import annotations

from importlib import import_module

from app.adapters.shared.context import ExpiringLruStore
from app.core.config import Settings


class FakeClock:
    def __init__(self) -> None:
        self.now = 0.0

    def __call__(self) -> float:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += seconds


def test_context_store_expires_entries_without_sliding_on_read() -> None:
    clock = FakeClock()
    store = ExpiringLruStore[str, int](
        ttl_seconds=10,
        max_entries=5,
        clock=clock,
    )
    store.set("offer-1", 1)

    clock.advance(9)
    assert store.get("offer-1") == 1

    clock.advance(1)
    assert store.get("offer-1") is None
    assert len(store) == 0


def test_context_store_evicts_the_least_recently_used_entry() -> None:
    clock = FakeClock()
    store = ExpiringLruStore[str, int](
        ttl_seconds=10,
        max_entries=2,
        clock=clock,
    )
    store.set("offer-1", 1)
    store.set("offer-2", 2)
    assert store.get("offer-1") == 1

    store.set("offer-3", 3)

    assert store.get("offer-1") == 1
    assert store.get("offer-2") is None
    assert store.get("offer-3") == 3


def test_context_store_purges_expired_entries_before_capacity_eviction() -> None:
    clock = FakeClock()
    store = ExpiringLruStore[str, int](
        ttl_seconds=5,
        max_entries=2,
        clock=clock,
    )
    store.set("expired-1", 1)
    store.set("expired-2", 2)
    clock.advance(5)

    store.set("fresh", 3)

    assert len(store) == 1
    assert store.get("fresh") == 3


def test_application_passes_repository_lifetime_to_adapter_context(monkeypatch) -> None:
    main_module = import_module("app.main")
    captured: dict[str, int | float] = {}
    resources = object()

    def register_live_adapters(_factory, **options):
        captured.update(options)
        return resources

    monkeypatch.setattr(main_module, "register_live_adapters", register_live_adapters)

    application = main_module.create_app(
        Settings(
            adapter_timeout_seconds=4.5,
            offer_ttl_seconds=321,
            offer_repository_max_entries=123,
        )
    )

    assert application.state.adapter_resources is resources
    assert captured == {
        "timeout_seconds": 4.5,
        "offer_ttl_seconds": 321,
        "max_entries": 123,
    }
