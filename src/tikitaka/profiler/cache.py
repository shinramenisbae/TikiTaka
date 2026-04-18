from __future__ import annotations

import time
from collections import OrderedDict


class TTLCache[K, V]:
    def __init__(self, max_size: int = 10_000, ttl_seconds: float = 24 * 3600) -> None:
        self.max_size = max_size
        self.ttl = ttl_seconds
        self._store: OrderedDict[K, tuple[float, V]] = OrderedDict()

    def get(self, key: K) -> V | None:
        now = time.monotonic()
        item = self._store.get(key)
        if item is None:
            return None
        expires_at, value = item
        if expires_at < now:
            self._store.pop(key, None)
            return None
        self._store.move_to_end(key)
        return value

    def set(self, key: K, value: V) -> None:
        expires_at = time.monotonic() + self.ttl
        self._store[key] = (expires_at, value)
        self._store.move_to_end(key)
        while len(self._store) > self.max_size:
            self._store.popitem(last=False)
