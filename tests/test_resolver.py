"""Resolver: canonical merging + confidence classification."""
from datetime import datetime, timezone

import pytest

from cpr.resolver.canonical import build_canonical
from cpr.resolver.confidence import classify_confidence
from cpr.schemas import (
    Author,
    EvidenceClaim,
    EvidenceRecord,
    PublicationIdentity,
)


def _mk_record(source, tier, **kwargs):
    return EvidenceRecord(
        identity=PublicationIdentity(doi=kwargs.get("doi")),
        source=source,
        source_url="https://example",
        authority_tier=tier,
        retrieved_at=datetime.now(timezone.utc),
        **kwargs,
    )


def test_confidence_two_a_agree_is_verified():
    claims = [
        EvidenceClaim(field="title", value="Foo", source="Crossref", source_url="", authority_tier="A", retrieved_at=datetime.now(timezone.utc)),
        EvidenceClaim(field="title", value="Foo", source="OpenReview", source_url="", authority_tier="A", retrieved_at=datetime.now(timezone.utc)),
    ]
    assert classify_confidence(claims) == "verified"


def test_confidence_single_a_is_high():
    claims = [
        EvidenceClaim(field="title", value="Foo", source="Crossref", source_url="", authority_tier="A", retrieved_at=datetime.now(timezone.utc)),
    ]
    assert classify_confidence(claims) == "high"


def test_confidence_single_b_is_medium():
    claims = [
        EvidenceClaim(field="title", value="Foo", source="DBLP", source_url="", authority_tier="B", retrieved_at=datetime.now(timezone.utc)),
    ]
    assert classify_confidence(claims) == "medium"


def test_confidence_only_c_is_low():
    claims = [
        EvidenceClaim(field="title", value="Foo", source="arXiv", source_url="", authority_tier="C", retrieved_at=datetime.now(timezone.utc)),
    ]
    assert classify_confidence(claims) == "low"


def test_confidence_empty_is_low():
    assert classify_confidence([]) == "low"


def test_confidence_a_vs_b_disagree_is_low_without_resolution():
    claims = [
        EvidenceClaim(field="title", value="Foo", source="Crossref", source_url="", authority_tier="A", retrieved_at=datetime.now(timezone.utc)),
        EvidenceClaim(field="title", value="Bar", source="DBLP", source_url="", authority_tier="B", retrieved_at=datetime.now(timezone.utc)),
    ]
    assert classify_confidence(claims) == "low"


def test_confidence_a_vs_b_disagree_with_resolution_is_medium():
    claims = [
        EvidenceClaim(field="title", value="Foo", source="Crossref", source_url="", authority_tier="A", retrieved_at=datetime.now(timezone.utc)),
        EvidenceClaim(field="title", value="Bar", source="DBLP", source_url="", authority_tier="B", retrieved_at=datetime.now(timezone.utc)),
    ]
    assert classify_confidence(claims, conflict_resolved=True) == "medium"


def test_canonical_prefers_higher_tier():
    r_a = _mk_record("Crossref", "A", title="From Crossref", year=2023)
    r_b = _mk_record("DBLP", "B", title="From DBLP (wrong)", year=2023)
    ident = PublicationIdentity()
    canon = build_canonical(ident, [r_a, r_b])
    assert canon.title.value == "From Crossref"
    assert any(c.source == "Crossref" for c in canon.title.evidence)


def test_canonical_arxiv_vs_formal_prefers_formal_venue():
    r_ax = _mk_record("arXiv", "C", title="Foo", year=2023, venue="arXiv preprint")
    r_cr = _mk_record("Crossref", "A", title="Foo", year=2023, venue="NeurIPS 2023")
    canon = build_canonical(PublicationIdentity(), [r_ax, r_cr])
    assert canon.venue.value == "NeurIPS 2023"
