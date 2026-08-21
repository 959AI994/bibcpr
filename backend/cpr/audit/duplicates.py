"""DUPLICATE_PUBLICATION detection across entries in the same bibliography (§20)."""
from __future__ import annotations

from ..bibtex.identity import normalize_title
from ..schemas import AuditFinding, BibEntry, FindingType
from .findings import build_finding


def audit_duplicates(entries: list[BibEntry]) -> list[AuditFinding]:
    findings: list[AuditFinding] = []
    seen: dict[str, list[BibEntry]] = {}
    for e in entries:
        key = _dedup_key(e)
        if key is None:
            continue
        seen.setdefault(key, []).append(e)
    for group in seen.values():
        if len(group) <= 1:
            continue
        canonical = group[0]
        for dup in group[1:]:
            findings.append(build_finding(
                entry_key=dup.key,
                finding_type=FindingType.DUPLICATE_PUBLICATION,
                severity="warning",
                field=None,
                current_value=None,      # report-only; no auto-fix
                suggested_value=None,
                explanation=(
                    f"This entry appears to duplicate `{canonical.key}` "
                    "(same DOI or same title+year). Duplicates are reported "
                    "but not removed automatically."
                ),
                evidence=[],
                confidence="low",        # explicit: not auto-fixable
            ))
    return findings


def _dedup_key(entry: BibEntry) -> str | None:
    if entry.doi:
        return f"doi::{entry.doi.strip().lower()}"
    if entry.title and entry.year:
        return f"tit::{normalize_title(entry.title)}::{entry.year}"
    return None
