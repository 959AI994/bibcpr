"""ACM article-number audit tests."""
from datetime import datetime, timezone

from cpr.audit.acm_pages import audit_acm_pages
from cpr.bibtex.parser import parse_bibtex_string
from cpr.resolver.canonical import build_canonical
from cpr.schemas import (
    EvidenceRecord,
    PublicationIdentity,
)


def _mk(source, tier, pages, doi=None):
    return EvidenceRecord(
        identity=PublicationIdentity(doi=doi),
        source=source,
        source_url="https://example",
        authority_tier=tier,
        retrieved_at=datetime.now(timezone.utc),
        pages=pages,
    )


def test_acm_pages_suggested_when_publisher_uses_article_numbering():
    text = """
    @inproceedings{k, author={A}, title={T}, booktitle={CCS}, year={2023},
                       pages={1--15}, doi={10.1145/3576915.3623063}}
    """
    entries = parse_bibtex_string(text)
    e = entries[0]
    r = _mk("Crossref", "A", "42:1--42:15", doi=e.doi)
    canon = build_canonical(PublicationIdentity(doi=e.doi), [r])
    findings = audit_acm_pages(e, canon)
    assert len(findings) == 1
    assert findings[0].suggested_value == "42:1--42:15"
    assert findings[0].confidence in ("verified", "high")


def test_acm_pages_no_suggestion_without_publisher_evidence():
    text = """
    @inproceedings{k, author={A}, title={T}, booktitle={CCS}, year={2023}, pages={1--15}}
    """
    entries = parse_bibtex_string(text)
    e = entries[0]
    # No records → no positive evidence → no ACM finding
    canon = build_canonical(PublicationIdentity(), [])
    findings = audit_acm_pages(e, canon)
    assert findings == []


def test_acm_pages_no_suggestion_when_only_tier_c_evidence():
    text = "@inproceedings{k, title={T}, pages={1--15}, doi={10.1/x}}"
    entries = parse_bibtex_string(text)
    e = entries[0]
    r = _mk("arXiv", "C", "42:1--42:15", doi="10.1/x")
    canon = build_canonical(PublicationIdentity(doi="10.1/x"), [r])
    findings = audit_acm_pages(e, canon)
    assert findings == []
