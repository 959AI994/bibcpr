"""Detect @article-vs-@inproceedings entry-type mismatches (§11)."""
from __future__ import annotations

from ..schemas import AuditFinding, BibEntry, CanonicalPublication, FindingType
from .findings import build_finding


def audit_entry_type(entry: BibEntry, canon: CanonicalPublication) -> list[AuditFinding]:
    if not canon.entry_type.value or not canon.entry_type.evidence:
        return []
    canonical_type = canon.entry_type.value
    if entry.entry_type == canonical_type:
        return []
    # Only propose downgrades or upgrades when the current type is inconsistent
    # (article vs inproceedings, book vs incollection).
    swaps = {
        ("article", "inproceedings"),
        ("inproceedings", "article"),
        ("misc", "article"),
        ("misc", "inproceedings"),
        ("article", "incollection"),
    }
    if (entry.entry_type, canonical_type) not in swaps:
        return []
    return [build_finding(
        entry_key=entry.key,
        finding_type=FindingType.ENTRY_TYPE_MISMATCH,
        severity="warning",
        field="entry_type",
        current_value=entry.entry_type,
        suggested_value=canonical_type,
        explanation=(
            f"Entry type `@{entry.entry_type}` disagrees with the canonical "
            f"record which classifies this as `@{canonical_type}`."
        ),
        evidence=canon.entry_type.evidence,
    )]
