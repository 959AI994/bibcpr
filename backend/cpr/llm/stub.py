"""LLM interface (§36).

Phase 1 ships the interface only. Concrete providers are wired in
Phase 2. Any call in MVP raises `NotImplementedError` — the audit
engine never invokes the LLM.
"""
from __future__ import annotations

from typing import Any, Protocol


class LLMResolver(Protocol):
    """Ambiguity resolver called by the audit engine when evidence is
    insufficient. The resolver returns structured suggestions with
    explicit uncertainty; the caller re-evaluates confidence."""

    name: str

    async def rerank(self, query: str, candidates: list[dict[str, Any]]) -> list[dict[str, Any]]: ...
    async def suggest_venue(self, title: str, year: int) -> str | None: ...


class StubLLMResolver:
    """A stub that refuses to do anything. Used in MVP."""

    name: str = "stub"

    async def rerank(self, query: str, candidates: list[dict[str, Any]]) -> list[dict[str, Any]]:
        raise NotImplementedError("LLM resolver not wired in Phase 1 — deterministic providers only.")

    async def suggest_venue(self, title: str, year: int) -> str | None:
        raise NotImplementedError("LLM resolver not wired in Phase 1 — deterministic providers only.")


__all__ = ["LLMResolver", "StubLLMResolver"]
