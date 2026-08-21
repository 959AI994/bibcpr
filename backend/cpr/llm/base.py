"""LLM client protocol (§36).

LLMs in bibcpr are strictly "routing decisions only, never evidence."
Every field that survives to `.verified.bib` must already be attested
by a Crossref/DBLP/arXiv/OpenReview record. The LLM is asked to:

- `sanity_check(entry_text)`  — does the serialized BibTeX look
                                well-formed for the venue it claims?
- `tie_break(candidates)`     — which of these evidence-backed
                                candidates matches the query?
- `resolve_conflict(...)`     — when two providers disagree on a
                                single field, choose the more likely
                                canonical value.
- `infer_id(entry)`           — given a raw entry with no DOI/arXiv
                                id, what plausible DOI or arXiv id
                                could this be? (The caller still
                                has to verify the guess against a
                                real provider before using it.)

Every method returns a structured result carrying its own confidence.
"""
from __future__ import annotations

from typing import Any, Literal, Protocol

from pydantic import BaseModel, Field


class SanityCheckResult(BaseModel):
    ok: bool
    issues: list[str] = Field(default_factory=list)
    confidence: Literal["low", "medium", "high"] = "medium"


class TieBreakResult(BaseModel):
    chosen_index: int | None
    reason: str = ""
    confidence: Literal["low", "medium", "high"] = "medium"


class ConflictResolution(BaseModel):
    chosen_value: Any = None
    reason: str = ""
    confidence: Literal["low", "medium", "high"] = "medium"


class IdInference(BaseModel):
    doi: str | None = None
    arxiv_id: str | None = None
    reason: str = ""
    confidence: Literal["low", "medium", "high"] = "low"


class LLMClient(Protocol):
    """The contract every LLM adapter must satisfy."""
    name: str

    async def sanity_check(self, entry_text: str) -> SanityCheckResult: ...
    async def tie_break(
        self, query: dict[str, Any], candidates: list[dict[str, Any]]
    ) -> TieBreakResult: ...
    async def resolve_conflict(
        self, field: str, values: list[dict[str, Any]]
    ) -> ConflictResolution: ...
    async def infer_id(self, entry: dict[str, Any]) -> IdInference: ...
    async def aclose(self) -> None: ...


class StubLLMClient:
    """A no-op client used when no API key is configured.

    Every method returns a low-confidence "unknown" result so that the
    caller can still ship — LLM checks degrade to a no-op instead of
    failing the pipeline.
    """
    name: str = "stub"

    async def sanity_check(self, entry_text: str) -> SanityCheckResult:
        return SanityCheckResult(ok=True, issues=[], confidence="low")

    async def tie_break(
        self, query: dict[str, Any], candidates: list[dict[str, Any]]
    ) -> TieBreakResult:
        return TieBreakResult(chosen_index=None, reason="stub client", confidence="low")

    async def resolve_conflict(
        self, field: str, values: list[dict[str, Any]]
    ) -> ConflictResolution:
        return ConflictResolution(chosen_value=None, reason="stub client", confidence="low")

    async def infer_id(self, entry: dict[str, Any]) -> IdInference:
        return IdInference(reason="stub client", confidence="low")

    async def aclose(self) -> None:
        return None


__all__ = [
    "LLMClient",
    "StubLLMClient",
    "SanityCheckResult",
    "TieBreakResult",
    "ConflictResolution",
    "IdInference",
]
