from __future__ import annotations

from collections import OrderedDict
from collections.abc import Callable, Hashable
from time import monotonic


class ExpiringLruStore[KeyT: Hashable, ValueT]:
    """Small synchronous TTL/LRU store for adapter-owned offer context.

    Adapter cache operations contain no await points, so keeping this store
    synchronous makes each mutation atomic within the application's event loop.
    """

    def __init__(
        self,
        *,
        ttl_seconds: float = 900,
        max_entries: int = 5_000,
        clock: Callable[[], float] = monotonic,
    ) -> None:
        self._items: OrderedDict[KeyT, tuple[ValueT, float]] = OrderedDict()
        self._ttl_seconds = max(1.0, float(ttl_seconds))
        self._max_entries = max(1, max_entries)
        self._clock = clock

    def set(self, key: KeyT, value: ValueT) -> None:
        now = self._clock()
        self._purge_expired(now)
        self._items[key] = (value, now + self._ttl_seconds)
        self._items.move_to_end(key)
        while len(self._items) > self._max_entries:
            self._items.popitem(last=False)

    def get(self, key: KeyT) -> ValueT | None:
        item = self._items.get(key)
        if item is None:
            return None
        value, expires_at = item
        if expires_at <= self._clock():
            self._items.pop(key, None)
            return None
        self._items.move_to_end(key)
        return value

    def clear(self) -> None:
        self._items.clear()

    def __len__(self) -> int:
        self._purge_expired(self._clock())
        return len(self._items)

    def _purge_expired(self, now: float) -> None:
        expired_keys = [
            key
            for key, (_, expires_at) in self._items.items()
            if expires_at <= now
        ]
        for key in expired_keys:
            self._items.pop(key, None)
