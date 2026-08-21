"""LLM adapters for bibcpr.

LLMs are used ONLY for routing decisions, never as an evidence source.
Field values that survive to `.verified.bib` must be attested by
Crossref/DBLP/arXiv/OpenReview.
"""
from .base import (
    ConflictResolution,
    IdInference,
    LLMClient,
    SanityCheckResult,
    StubLLMClient,
    TieBreakResult,
)
from .factory import build_client
from .stub import LLMResolver, StubLLMResolver

__all__ = [
    "LLMClient",
    "StubLLMClient",
    "SanityCheckResult",
    "TieBreakResult",
    "ConflictResolution",
    "IdInference",
    "build_client",
    # Kept for backwards-compat with Phase 1 audit engine imports:
    "LLMResolver",
    "StubLLMResolver",
]
