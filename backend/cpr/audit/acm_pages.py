"""ACM article-number rule (§9).

Only rewrite pages `1--N` to `N:1--N:M` when a Crossref/DBLP record for
this DOI reports pages in that structured form. Never inferred from page
count alone.
"""
from __future__ import annotations

from ..schemas import AuditFinding, BibEntry, CanonicalPublication, FindingType
from .findings import build_finding


def _is_acm_article_number(pages: str | None) -> bool:
    if not pages:
        return False
    return ":" in pages


def audit_acm_pages(entry: BibEntry, canon: CanonicalPublication) -> list[AuditFinding]:
    # Look for positive evidence in the raw records.
    acm_style_records = [
        r for r in canon.evidence_records
        if r.pages and _is_acm_article_number(r.pages) and r.authority_tier in ("A", "B")
    ]
    if not acm_style_records:
        return []
    top = acm_style_records[0]
    if entry.pages and _is_acm_article_number(entry.pages):
        # Already in ACM form; check for exact match
        if entry.pages.strip() == top.pages.strip():
            return []
    evidence = []
    for r in acm_style_records:
        for c in r.to_claims():
            if c.field == "pages":
                evidence.append(c)
    return [build_finding(
        entry_key=entry.key,
        finding_type=FindingType.ACM_ARTICLE_NUMBER_SUGGESTED,
        severity="info",
        field="pages",
        current_value=entry.pages,
        suggested_value=top.pages,
        explanation=(
            "The publisher uses ACM article-number pagination (`N:M--N:P`) "
            "for this record. The current `pages` value should be replaced "
            "with the article-numbered range."
        ),
        evidence=evidence,
    )]
