"""Field-level metadata audits.

Each auditor compares one field of the original BibEntry to the
CanonicalPublication's canonical view and emits at most one finding
per (entry, field). §0: never emit a finding without evidence.
"""
from __future__ import annotations

from ..bibtex.identity import normalize_title
from ..schemas import (
    AuditFinding,
    BibEntry,
    CanonicalPublication,
    FindingType,
)
from .findings import finding_from_canonical_field, build_finding


def _authors_equivalent(orig: list, canon: list) -> bool:
    if len(orig) != len(canon):
        return False
    for a, b in zip(orig, canon):
        af = (a.family or "").strip().lower()
        bf = (b.family or "").strip().lower()
        if not af or not bf or af != bf:
            return False
    return True


def audit_metadata(entry: BibEntry, canon: CanonicalPublication) -> list[AuditFinding]:
    findings: list[AuditFinding] = []

    # Title
    if canon.title.value and canon.title.evidence:
        if entry.title is None or normalize_title(entry.title) != normalize_title(canon.title.value):
            f = build_finding(
                entry_key=entry.key,
                finding_type=FindingType.TITLE_MISMATCH,
                severity="warning",
                field="title",
                current_value=entry.title,
                suggested_value=canon.title.value,
                explanation=(
                    "The title in the BibTeX entry differs from the "
                    "canonical title reported by the authoritative source(s)."
                ),
                evidence=canon.title.evidence,
                conflict=canon.title.conflict,
            )
            findings.append(f)

    # Authors
    if canon.authors.value and canon.authors.evidence:
        if not _authors_equivalent(entry.authors, canon.authors.value):
            findings.append(build_finding(
                entry_key=entry.key,
                finding_type=FindingType.AUTHOR_MISMATCH,
                severity="warning",
                field="author",
                current_value=[a.formatted or a.raw for a in entry.authors],
                # Structured Author list so `apply_findings` can assign it directly.
                suggested_value=canon.authors.value,
                explanation=(
                    "The author list differs from the canonical list reported "
                    "by the authoritative source(s)."
                ),
                evidence=canon.authors.evidence,
                conflict=canon.authors.conflict,
            ))

    # Year
    f = finding_from_canonical_field(
        entry_key=entry.key,
        field="year",
        current_value=entry.year,
        canon=canon.year,
        finding_type=FindingType.YEAR_MISMATCH,
        severity="warning",
        explanation="Year differs from the authoritative record.",
    )
    if f is not None:
        findings.append(f)

    # Venue (journal / booktitle)
    current_venue = entry.journal or entry.booktitle
    if canon.venue.value and canon.venue.evidence:
        if (current_venue or "").strip().lower() != canon.venue.value.strip().lower():
            findings.append(build_finding(
                entry_key=entry.key,
                finding_type=FindingType.VENUE_MISMATCH,
                severity="warning",
                field="venue",
                current_value=current_venue,
                suggested_value=canon.venue.value,
                explanation="Venue differs from the authoritative record.",
                evidence=canon.venue.evidence,
                conflict=canon.venue.conflict,
            ))

    # DOI presence + agreement
    if canon.doi.value and canon.doi.evidence:
        if entry.doi is None:
            findings.append(build_finding(
                entry_key=entry.key,
                finding_type=FindingType.DOI_MISSING,
                severity="info",
                field="doi",
                current_value=None,
                suggested_value=canon.doi.value,
                explanation="DOI is missing from the BibTeX entry but is registered upstream.",
                evidence=canon.doi.evidence,
            ))
        elif entry.doi.strip().lower() != canon.doi.value.strip().lower():
            findings.append(build_finding(
                entry_key=entry.key,
                finding_type=FindingType.DOI_MISMATCH,
                severity="error",
                field="doi",
                current_value=entry.doi,
                suggested_value=canon.doi.value,
                explanation="DOI in the BibTeX entry does not match the authoritative record.",
                evidence=canon.doi.evidence,
            ))

    return findings
