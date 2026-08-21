"""In-memory session store for the web UI.

One session = one uploaded .bib. Sessions live only for the lifetime
of the server process; nothing is persisted to disk. When the user
closes the browser, the session eventually expires (default 1 hour
of inactivity).
"""
from __future__ import annotations

import secrets
import time
from dataclasses import dataclass, field
from threading import Lock
from typing import Any

from ..schemas import AuditReport, BibEntry, CanonicalPublication


@dataclass
class SessionState:
    id: str
    bib_text: str
    filename: str
    entries: list[BibEntry] = field(default_factory=list)
    canonicals: dict[str, CanonicalPublication] = field(default_factory=dict)
    report: AuditReport | None = None
    corrected_bib_text: str | None = None
    markdown_report: str | None = None
    json_report: str | None = None
    created_at: float = field(default_factory=time.time)
    last_seen: float = field(default_factory=time.time)


class SessionStore:
    """Thread-safe in-memory session dict with TTL cleanup."""

    def __init__(self, ttl_seconds: int = 3600):
        self._sessions: dict[str, SessionState] = {}
        self._lock = Lock()
        self._ttl = ttl_seconds

    def create(self, bib_text: str, filename: str) -> SessionState:
        sid = secrets.token_urlsafe(12)
        state = SessionState(id=sid, bib_text=bib_text, filename=filename)
        with self._lock:
            self._sessions[sid] = state
            self._gc_locked()
        return state

    def get(self, sid: str) -> SessionState | None:
        with self._lock:
            state = self._sessions.get(sid)
            if state is not None:
                state.last_seen = time.time()
            return state

    def _gc_locked(self) -> None:
        now = time.time()
        dead = [sid for sid, s in self._sessions.items() if now - s.last_seen > self._ttl]
        for sid in dead:
            self._sessions.pop(sid, None)


# Module-level singleton
_store = SessionStore()


def get_store() -> SessionStore:
    return _store
