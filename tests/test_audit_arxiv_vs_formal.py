"""FORMAL_PUBLICATION_AVAILABLE audit tests (§10)."""
from datetime import datetime, timezone

from cpr.audit.arxiv_vs_formal import audit_arxiv_vs_formal
from cpr.bibtex.parser import parse_bibtex_string
from cpr.resolver.canonical import build_canonical
from cpr.schemas import EvidenceRecord, FindingType, PublicationIdentity


def _mk(source, tier, venue=None, entry_type=None):
    return EvidenceRecord(
        identity=PublicationIdentity(),
        source=source,
        source_url="https://example",
        authority_tier=tier,
        retrieved_at=datetime.now(timezone.utc),
        venue=venue,
        entry_type=entry_type,
    )


def test_finding_fires_when_arxiv_and_formal_evidence_both_present():
    text = """
    @article{k, author={A}, title={T}, eprint={1706.03762},
              archivePrefix={arXiv}, journal={arXiv preprint}, year={2017}}
    """
    e = parse_bibtex_string(text)[0]
    r = _mk("Crossref", "A", venue="NeurIPS 2017", entry_type="inproceedings")
    canon = build_canonical(PublicationIdentity(), [r])
    findings = audit_arxiv_vs_formal(e, canon)
    assert len(findings) == 1
    assert findings[0].finding_type == FindingType.FORMAL_PUBLICATION_AVAILABLE
    assert findings[0].suggested_value == "NeurIPS 2017"


def test_no_finding_when_no_formal_evidence():
    text = "@article{k, title={T}, eprint={1706.03762}, journal={arXiv}, year={2024}}"
    e = parse_bibtex_string(text)[0]
    canon = build_canonical(PublicationIdentity(), [])
    assert audit_arxiv_vs_formal(e, canon) == []


def test_no_finding_when_entry_is_not_a_preprint():
    text = "@inproceedings{k, title={T}, booktitle={NeurIPS}, year={2017}}"
    e = parse_bibtex_string(text)[0]
    r = _mk("Crossref", "A", venue="NeurIPS 2017")
    canon = build_canonical(PublicationIdentity(), [r])
    assert audit_arxiv_vs_formal(e, canon) == []
