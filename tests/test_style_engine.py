"""Style engine tests: gating, arXiv→formal demotion, cosmetic pages."""
from datetime import datetime, timezone

from cpr.audit.arxiv_vs_formal import audit_arxiv_vs_formal
from cpr.bibtex.parser import parse_bibtex_string
from cpr.resolver.canonical import build_canonical
from cpr.schemas import EvidenceRecord, PublicationIdentity
from cpr.style.engine import apply_findings, apply_style
from cpr.style.profile import load_default_profile


def _mk_formal(venue="NeurIPS 2017"):
    return EvidenceRecord(
        identity=PublicationIdentity(),
        source="Crossref",
        source_url="https://doi.org/x",
        authority_tier="A",
        retrieved_at=datetime.now(timezone.utc),
        venue=venue,
        entry_type="inproceedings",
    )


def test_arxiv_to_conference_demotion():
    profile = load_default_profile()
    text = """
    @article{k, author={Ashish Vaswani}, title={Attention Is All You Need},
              eprint={1706.03762}, archivePrefix={arXiv},
              journal={arXiv preprint}, year={2017}}
    """
    entry = parse_bibtex_string(text)[0]
    r = _mk_formal()
    canon = build_canonical(PublicationIdentity(), [r])
    findings = audit_arxiv_vs_formal(entry, canon)
    assert findings and findings[0].confidence in ("verified", "high")
    corrected, applied = apply_findings(entry, findings, profile)
    assert len(applied) == 1
    assert corrected.entry_type == "inproceedings"
    assert corrected.booktitle == "NeurIPS 2017"
    assert corrected.journal is None
    assert corrected.key == "k"  # citation key preserved
    assert corrected.eprint == "1706.03762"  # kept per sjtu-ectl policy


def test_medium_confidence_not_auto_applied():
    profile = load_default_profile()
    text = "@article{k, title={T}, year={2020}}"
    entry = parse_bibtex_string(text)[0]
    r_b_only = EvidenceRecord(
        identity=PublicationIdentity(), source="DBLP",
        source_url="https://x", authority_tier="B",
        retrieved_at=datetime.now(timezone.utc),
        title="Different Title",
    )
    canon = build_canonical(PublicationIdentity(), [r_b_only])
    # Manually build a title finding via metadata audit
    from cpr.audit.metadata import audit_metadata
    findings = audit_metadata(entry, canon)
    # Single tier-B is medium → not applied under default gate
    corrected, applied = apply_findings(entry, findings, profile)
    assert applied == []
    assert corrected.title == "T"


def test_cosmetic_pages_double_hyphen():
    profile = load_default_profile()
    text = "@article{k, title={T}, pages={1-15}, year={2020}}"
    entry = parse_bibtex_string(text)[0]
    corrected = apply_style(entry, profile)
    assert corrected.pages == "1--15"
