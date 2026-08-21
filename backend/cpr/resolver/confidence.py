"""Confidence classification per §24.

Verified: ≥ 2 sources at tier A/B agree.
High:     Exactly 1 tier-A source, no contradicting evidence.
Medium:   Exactly 1 tier-B source (or an A/B conflict that was resolved
          in favor of the tier-A source with a named ConflictClass rule).
Low:      Only tier-C source, or unresolved contradiction.
"""
from __future__ import annotations

from typing import Any, Sequence

from ..schemas import Confidence, EvidenceClaim


_TIER_ORDER = {"A": 3, "B": 2, "C": 1, "D": 0}


def _canonicalize_value(v: Any) -> Any:
    """For equality comparison across sources."""
    if isinstance(v, str):
        return v.strip().lower().rstrip(".")
    if isinstance(v, int):
        return v
    if isinstance(v, list):
        return tuple(_canonicalize_value(x) for x in v)
    if isinstance(v, dict):
        return tuple(sorted((k, _canonicalize_value(v)) for k, v in v.items()))
    return v


def classify_confidence(
    claims: Sequence[EvidenceClaim],
    conflict_resolved: bool = False,
) -> Confidence:
    """Return `verified | high | medium | low` for a set of same-field claims."""
    if not claims:
        return "low"

    by_tier: dict[str, list[EvidenceClaim]] = {}
    for c in claims:
        by_tier.setdefault(c.authority_tier, []).append(c)

    tier_a = by_tier.get("A", [])
    tier_b = by_tier.get("B", [])
    tier_c = by_tier.get("C", [])

    # Any contradiction anywhere in tier A/B disqualifies "verified"
    values_ab = [_canonicalize_value(c.value) for c in tier_a + tier_b]
    tier_ab_all_agree = len(set(values_ab)) <= 1 if values_ab else True

    if tier_ab_all_agree and (len(tier_a) + len(tier_b)) >= 2:
        return "verified"

    if len(tier_a) >= 1 and tier_ab_all_agree:
        return "high"

    if len(tier_a) >= 1 and not tier_ab_all_agree and conflict_resolved:
        # A vs B disagreement, but a named rule picked A → still trust it.
        return "medium"

    if len(tier_b) >= 1 and not tier_a and tier_ab_all_agree:
        return "medium"

    # Contradictions with no resolution, or only tier-C evidence, or empty:
    if not tier_a and not tier_b and tier_c:
        return "low"

    return "low"
