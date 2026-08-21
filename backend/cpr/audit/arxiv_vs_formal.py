"""FORMAL_PUBLICATION_AVAILABLE detector (§10)."""
from __future__ import annotations

from ..schemas import AuditFinding, BibEntry, CanonicalPublication, FindingType
from .findings import build_finding


def audit_arxiv_vs_formal(entry: BibEntry, canon: CanonicalPublication) -> list[AuditFinding]:
    # This finding fires when: entry looks like an arXiv preprint AND at
    # least one formal (Crossref/DBLP/OpenReview) evidence record exists.
    looks_like_preprint = (
        (entry.eprint is not None)
        or ((entry.archive_prefix or "").lower() == "arxiv")
        or ((entry.journal or "").lower().startswith("arxiv"))
    )
    if not looks_like_preprint:
        return []
    formal_records = [
        r for r in canon.evidence_records if r.source in ("Crossref", "DBLP", "OpenReview") and r.venue
    ]
    if not formal_records:
        return []
    top = formal_records[0]
    # Only the `venue` claim(s) count as evidence for this venue-field finding.
    evidence = [c for r in formal_records for c in r.to_claims() if c.field == "venue"]
    return [build_finding(
        entry_key=entry.key,
        finding_type=FindingType.FORMAL_PUBLICATION_AVAILABLE,
        severity="warning",
        field="venue",
        current_value=entry.journal or entry.booktitle,
        suggested_value=top.venue,
        explanation=(
            f"This entry is an arXiv preprint, but a formal publication is "
            f"available via {top.source} at {top.source_url}. Prefer the "
            "formal record."
        ),
        evidence=evidence,
    )]
