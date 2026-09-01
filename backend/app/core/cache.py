"""Multi-tier in-memory & Redis cache manager for high-speed metadata lookups."""

from __future__ import annotations

import logging
import os
import threading
import time
from typing import Any, Callable

logger = logging.getLogger(__name__)


class MemoryCache:
    """Thread-safe in-memory cache with per-key TTL expiration."""

    def __init__(self) -> None:
        self._store: dict[str, tuple[float, Any]] = {}
        self._lock = threading.Lock()

    def get(self, key: str) -> Any | None:
        with self._lock:
            entry = self._store.get(key)
            if entry is None:
                return None
            expires_at, value = entry
            if time.time() > expires_at:
                del self._store[key]
                return None
            return value

    def set(self, key: str, value: Any, ttl_seconds: float = 300.0) -> None:
        with self._lock:
            self._store[key] = (time.time() + ttl_seconds, value)

    def delete(self, key: str) -> None:
        with self._lock:
            self._store.pop(key, None)

    def clear(self, prefix: str | None = None) -> None:
        with self._lock:
            if prefix is None:
                self._store.clear()
            else:
                keys_to_del = [k for k in self._store if k.startswith(prefix)]
                for k in keys_to_del:
                    del self._store[k]


_memory_cache = MemoryCache()


def get_or_set(key: str, factory: Callable[[], Any], ttl_seconds: float = 300.0) -> Any:
    """Retrieve value from cache or execute factory and store result."""
    cached = _memory_cache.get(key)
    if cached is not None:
        return cached
    value = factory()
    if value is not None:
        _memory_cache.set(key, value, ttl_seconds=ttl_seconds)
    return value


def invalidate_cache(prefix: str | None = None) -> None:
    """Clear cached entries matching prefix or all entries if None."""
    _memory_cache.clear(prefix)
