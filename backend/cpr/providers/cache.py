"""SQLite-backed persistent disk cache for provider responses.

Cache key: (kind, url, sorted params tuple).
Value: JSON-encoded response payload (or `null` for 404).
"""
from __future__ import annotations

import json
import sqlite3
import time
from pathlib import Path
from typing import Any

from platformdirs import user_cache_dir


_DDL = """
CREATE TABLE IF NOT EXISTS cache (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL,
    is_null INTEGER NOT NULL DEFAULT 0,
    stored_at INTEGER NOT NULL
)
"""


class DiskCache:
    """A tiny SQLite cache. Not thread-safe across processes; fine for CLI."""

    def __init__(self, path: str | Path, ttl_seconds: int | None = None):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.ttl_seconds = ttl_seconds
        self._conn = sqlite3.connect(str(self.path))
        self._conn.execute(_DDL)
        self._conn.commit()

    @staticmethod
    def _serialize_key(key: Any) -> str:
        return json.dumps(key, sort_keys=True, default=str)

    def get(self, key: Any) -> Any:
        k = self._serialize_key(key)
        row = self._conn.execute(
            "SELECT value, is_null, stored_at FROM cache WHERE key = ?", (k,)
        ).fetchone()
        if row is None:
            return _MISSING
        value_text, is_null, stored_at = row
        if self.ttl_seconds is not None and (time.time() - stored_at) > self.ttl_seconds:
            self._conn.execute("DELETE FROM cache WHERE key = ?", (k,))
            self._conn.commit()
            return _MISSING
        if is_null:
            return None
        try:
            return json.loads(value_text)
        except Exception:
            return _MISSING

    def set(self, key: Any, value: Any) -> None:
        k = self._serialize_key(key)
        if value is None:
            self._conn.execute(
                "INSERT OR REPLACE INTO cache(key, value, is_null, stored_at) VALUES(?, ?, ?, ?)",
                (k, "", 1, int(time.time())),
            )
        else:
            self._conn.execute(
                "INSERT OR REPLACE INTO cache(key, value, is_null, stored_at) VALUES(?, ?, ?, ?)",
                (k, json.dumps(value, default=str), 0, int(time.time())),
            )
        self._conn.commit()

    def close(self) -> None:
        self._conn.close()


class NullCache:
    """A cache that never caches. Used by unit tests."""

    def get(self, key: Any) -> Any:
        return _MISSING

    def set(self, key: Any, value: Any) -> None:
        return None

    def close(self) -> None:
        return None


# Sentinel returned by `.get()` when there's no entry (so we can
# distinguish "cached miss / 404" (None) from "not in cache" (_MISSING)).
class _Missing:
    def __repr__(self) -> str:
        return "<cache MISS>"


_MISSING = _Missing()


def get_default_cache() -> DiskCache:
    root = Path(user_cache_dir("cpr", "cpr"))
    return DiskCache(root / "cache.sqlite")


# Provider mixin wants a uniform interface: return None for miss, `value` for hit.
# Wrap so that a cached-null (a real 404 we recorded) is distinguishable from a miss.
class _AdaptedGet:
    """Wraps a Cache so that `.get(key)` returns None on miss and the stored value on hit.

    But callers need to also know about the tri-state "cached-negative" case
    (a real 404 recorded as None). We handle that by encoding None-values as
    a sentinel and returning them as `False` (falsy) — providers explicitly
    check `is None`. See `BaseHttpProvider._get_json`.
    """


# Simplify: patch cache classes to return None on miss (providers already
# treat missing == not fetched). Since BaseHttpProvider's flow is:
#   cached = self._cache.get(key)
#   if cached is not None: return cached
# a cached 404 must not short-circuit. So providers-that-cache-null need to
# handle that themselves. For simplicity we drop cached-null differentiation
# in Phase 1 — a 404 is re-fetched each run.
def _patch_get(cls):
    orig = cls.get

    def get(self, key):
        v = orig(self, key)
        if isinstance(v, _Missing):
            return None
        return v

    cls.get = get
    return cls


_patch_get(DiskCache)
_patch_get(NullCache)
