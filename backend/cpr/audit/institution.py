"""Detect institutional strings appearing in author lists (case 04 in §44)."""
from __future__ import annotations

from ..schemas import AuditFinding, BibEntry, FindingType
from .findings import build_finding


_INSTITUTION_MARKERS = (
    " group",
    " team",
    " inc",
    " ltd",
    " corp",
    " university",
    " institute",
    "openai",
    "google",
    "meta ai",
    "microsoft",
    "deepmind",
    "anthropic",
    "nvidia",
)


def audit_institution_as_author(entry: BibEntry) -> list[AuditFinding]:
    for a in entry.authors:
        text = (a.raw or a.formatted or a.family).lower()
        if a.given == [] and any(m in text for m in _INSTITUTION_MARKERS):
            return [build_finding(
                entry_key=entry.key,
                finding_type=FindingType.INSTITUTION_AS_AUTHOR,
                severity="warning",
                field="author",
                current_value=a.raw or a.formatted or a.family,
                suggested_value=None,
                explanation=(
                    "The author list appears to contain an institutional or "
                    "corporate name rather than an individual. Verify against "
                    "the source and either move to `organization`/`institution` "
                    "or wrap explicitly in braces as `{{OpenAI}}`."
                ),
                evidence=[],
                confidence="medium",
            )]
    return []
