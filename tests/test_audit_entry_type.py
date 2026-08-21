"""Entry-type mismatch audit tests."""
from datetime import datetime, timezone

from cpr.audit.entry_type import audit_entry_type
from cpr.bibtex.parser import parse_bibtex_string
from cpr.resolver.canonical import build_canonical
from cpr.schemas import EvidenceRecord, FindingType, PublicationIdentity


def _mk(source, tier, entry_type):
    return EvidenceRecord(
        identity=PublicationIdentity(),
        source=source,
        source_url="https://example",
        authority_tier=tier,
        retrieved_at=datetime.now(timezone.utc),
        entry_type=entry_type,
    )


def test_article_flagged_as_inproceedings():
    e = parse_bibtex_string("@article{k, title={T}, year={2020}}")[0]
    r = _mk("DBLP", "B", "inproceedings")
    r2 = _mk("Crossref", "A", "inproceedings")
    canon = build_canonical(PublicationIdentity(), [r, r2])
    findings = audit_entry_type(e, canon)
    assert len(findings) == 1
    assert findings[0].finding_type == FindingType.ENTRY_TYPE_MISMATCH
    assert findings[0].suggested_value == "inproceedings"


def test_matching_entry_type_no_finding():
    e = parse_bibtex_string("@inproceedings{k, title={T}, year={2020}}")[0]
    r = _mk("Crossref", "A", "inproceedings")
    canon = build_canonical(PublicationIdentity(), [r])
    assert audit_entry_type(e, canon) == []


def test_no_evidence_no_finding():
    e = parse_bibtex_string("@article{k, title={T}, year={2020}}")[0]
    canon = build_canonical(PublicationIdentity(), [])
    assert audit_entry_type(e, canon) == []
