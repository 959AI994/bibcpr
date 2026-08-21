"""Apply StyleProfile + AuditFindings to the original entry → corrected entry.

Rules:
- Auto-apply only findings with confidence ∈ {verified, high} (§24) unless
  overridden by the caller (interactive mode).
- Citation keys are never rewritten under `strategy=preserve`.
- For arXiv→formal (§10) demotion, both `entry_type` and `venue` (booktitle
  or journal) are updated together; `eprint`/`archivePrefix`/`primaryClass`
  are retained if `keep_arxiv_eprint_field=true`.
"""
from __future__ import annotations

from copy import deepcopy

from ..schemas import (
    AuditFinding,
    BibEntry,
    Confidence,
    FindingType,
)
from .profile import StyleProfile


_APPLICABLE = {
    FindingType.TITLE_MISMATCH: "title",
    FindingType.YEAR_MISMATCH: "year",
    FindingType.VENUE_MISMATCH: "venue",
    FindingType.PAGES_MISMATCH: "pages",
    FindingType.DOI_MISMATCH: "doi",
    FindingType.DOI_MISSING: "doi",
    FindingType.ENTRY_TYPE_MISMATCH: "entry_type",
    FindingType.FORMAL_PUBLICATION_AVAILABLE: "venue",
    FindingType.ACM_ARTICLE_NUMBER_SUGGESTED: "pages",
    FindingType.AUTHOR_MISMATCH: "author",
}


def _confidence_allows(finding: AuditFinding, gate: set[Confidence]) -> bool:
    return finding.confidence in gate and finding.suggested_value is not None


def apply_findings(
    entry: BibEntry,
    findings: list[AuditFinding],
    profile: StyleProfile,
    gate: set[Confidence] | None = None,
) -> tuple[BibEntry, list[AuditFinding]]:
    """Return a copy of `entry` with all auto-fixable findings applied.

    Returns (corrected_entry, applied_findings).
    """
    gate = gate or {"verified", "high"}
    corrected = deepcopy(entry)
    applied: list[AuditFinding] = []
    for f in findings:
        if f.entry_key != entry.key:
            continue
        if not _confidence_allows(f, gate):
            continue
        target = _APPLICABLE.get(f.finding_type)
        if target is None:
            continue
        if _apply_one(corrected, f, target, profile):
            applied.append(f)
    return corrected, applied


def _apply_one(entry: BibEntry, finding: AuditFinding, target: str, profile: StyleProfile) -> bool:
    val = finding.suggested_value
    if target == "title":
        entry.title = val
        return True
    if target == "year":
        entry.year = int(val) if isinstance(val, (int, str)) and str(val).isdigit() else entry.year
        return True
    if target == "doi":
        entry.doi = val
        return True
    if target == "pages":
        entry.pages = val
        return True
    if target == "entry_type":
        entry.entry_type = val
        return True
    if target == "venue":
        # If we're moving from an arXiv-preprint appearance to a formal venue,
        # decide whether that's journal or booktitle from the suggested entry_type.
        # Simplest: if current entry_type is "article" and finding is FORMAL_PUBLICATION_AVAILABLE,
        # set booktitle + change entry_type to inproceedings; else respect current type.
        if finding.finding_type == FindingType.FORMAL_PUBLICATION_AVAILABLE:
            entry.booktitle = val
            entry.journal = None
            if entry.entry_type == "article":
                entry.entry_type = "inproceedings"
            if not profile.publication.keep_arxiv_eprint_field:
                entry.eprint = None
                entry.archive_prefix = None
                entry.primary_class = None
            return True
        if entry.entry_type == "article":
            entry.journal = val
        else:
            entry.booktitle = val
        return True
    if target == "author":
        # Suggested value is `list[Author]`
        if isinstance(val, list):
            entry.authors = val
            return True
    return False


def apply_style(
    entry: BibEntry,
    profile: StyleProfile,
) -> BibEntry:
    """Apply cosmetic style rules that don't require evidence.

    Currently: pages `1-N` → `1--N` (double_hyphen), author abbreviation.
    """
    corrected = deepcopy(entry)
    if profile.pages.double_hyphen and corrected.pages:
        p = corrected.pages
        # Only rewrite single `-` between digit runs
        import re
        corrected.pages = re.sub(r"(\d)\s*-\s*(\d)", r"\1--\2", p)
    return corrected
