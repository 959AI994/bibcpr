"""Named conflict classes (§8).

Each rule receives the full list of `EvidenceRecord`s and returns one of:
  (None, None)                        — no conflict of this class detected.
  (ConflictClass.X, chosen_value)     — conflict detected and resolved.
  (ConflictClass.X, None)             — conflict detected but not resolvable.
"""
from __future__ import annotations

from typing import Any

from ..schemas import ConflictClass, EvidenceRecord


def detect_online_vs_issue_year(records: list[EvidenceRecord]) -> tuple[ConflictClass | None, int | None]:
    """When Crossref exposes both published-online and published-print with
    different years, we prefer the printed/issue year. In Phase 1 we do not
    have separate fields for these — the year in each EvidenceRecord is the
    provider's primary year. We detect conflicts across providers by
    checking whether two tier A/B providers disagree on year by ≥ 1.
    """
    ab = [r for r in records if r.authority_tier in ("A", "B") and r.year is not None]
    if len(ab) < 2:
        return None, None
    years = {r.year for r in ab}
    if len(years) <= 1:
        return None, None
    # Prefer the smaller (issue/print) year over the larger (online) year.
    resolved = min(years)
    return ConflictClass.ONLINE_VS_ISSUE_YEAR, resolved


def detect_arxiv_vs_formal(records: list[EvidenceRecord]) -> tuple[ConflictClass | None, str | None]:
    """If we have an arXiv record AND a Crossref/DBLP record, the formal
    publication wins.  Returns the venue chosen (or None to defer)."""
    has_arxiv = any(r.source == "arXiv" for r in records)
    formal = [r for r in records if r.source in ("Crossref", "DBLP", "OpenReview")]
    if has_arxiv and formal:
        # Prefer whichever formal record has a venue set.
        for r in formal:
            if r.venue:
                return ConflictClass.ARXIV_VS_FORMAL_PUBLICATION, r.venue
        return ConflictClass.ARXIV_VS_FORMAL_PUBLICATION, None
    return None, None


def detect_pages_conflict(records: list[EvidenceRecord]) -> tuple[ConflictClass | None, str | None]:
    """If Crossref/DBLP report pages of the form `N:1--N:M` (ACM article
    numbering) we prefer that; else no conflict.  This is the *permissive*
    side of §9 — a suggestion, not automatic.
    """
    for r in records:
        if r.pages and ":" in r.pages and r.authority_tier in ("A", "B"):
            return ConflictClass.IEEE_PAGES_VS_ACM_ARTICLE_NUMBER, r.pages
    return None, None


def detect_conflicts(records: list[EvidenceRecord]) -> dict[str, tuple[ConflictClass | None, Any]]:
    """Run all detectors, returning field → (class, chosen_value)."""
    out: dict[str, tuple[ConflictClass | None, Any]] = {}
    cy, y = detect_online_vs_issue_year(records)
    if cy is not None:
        out["year"] = (cy, y)
    cv, v = detect_arxiv_vs_formal(records)
    if cv is not None:
        out["venue"] = (cv, v)
    cp, p = detect_pages_conflict(records)
    if cp is not None:
        out["pages"] = (cp, p)
    return out


def resolve_conflict(cls: ConflictClass, records: list[EvidenceRecord], field: str) -> Any:
    """Legacy single-shot resolver for a given field. Kept for symmetry."""
    conflicts = detect_conflicts(records)
    entry = conflicts.get(field)
    if entry is None:
        return None
    return entry[1]
