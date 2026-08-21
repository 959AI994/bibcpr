"""Tests for the export/verify module and `cpr export` CLI.

These tests all run offline — no LLM API is invoked (`--llm off` or
stub) and no evidence providers are hit (`--no-network`).
"""
from __future__ import annotations

from pathlib import Path

import pytest
from typer.testing import CliRunner

from cpr.cli import app
from cpr.bibtex.parser import parse_bibtex_file
from cpr.llm.base import StubLLMClient
from cpr.schemas import (
    AuditFinding,
    BibEntry,
    CanonicalField,
    CanonicalPublication,
    ConflictClass,
    EvidenceRecord,
    FindingType,
    PublicationIdentity,
)
from cpr.style.profile import load_default_profile
from cpr.verify.exporter import (
    classify_entry,
    export_bib,
    write_export_outputs,
)


BIB_DIR = Path(__file__).parent / "bibs"


# ---------- unit: classify_entry --------------------------------------------

def _bib_entry(key: str = "e1", title: str | None = "Some Paper", year: int | None = 2023) -> BibEntry:
    return BibEntry(key=key, entry_type="article", title=title, year=year)


def _canon_with_strong_id_and_evidence() -> CanonicalPublication:
    ident = PublicationIdentity(doi="10.1000/xyz123")
    rec = EvidenceRecord(
        identity=ident,
        source="Crossref",
        source_url="https://api.crossref.org/works/10.1000/xyz123",
        authority_tier="A",
        title="Some Paper",
    )
    return CanonicalPublication(identity=ident, evidence_records=[rec])


def test_classify_verified_when_all_criteria_pass():
    entry = _bib_entry()
    canon = _canon_with_strong_id_and_evidence()
    verdict = classify_entry(entry, canon, findings=[], sanity_ok=True)
    assert verdict.classification == "verified"
    assert verdict.reasons == []


def test_classify_needs_review_when_no_strong_id():
    entry = _bib_entry()
    canon = CanonicalPublication(identity=PublicationIdentity())  # no DOI/arxiv/OR
    verdict = classify_entry(entry, canon, findings=[], sanity_ok=True)
    assert verdict.classification == "needs-review"
    assert any("no strong identity" in r for r in verdict.reasons)


def test_classify_needs_review_when_no_evidence():
    entry = _bib_entry()
    canon = CanonicalPublication(identity=PublicationIdentity(doi="10.1/x"))
    # DOI present but no evidence_records
    verdict = classify_entry(entry, canon, findings=[], sanity_ok=True)
    assert verdict.classification == "needs-review"
    assert any("no evidence records" in r for r in verdict.reasons)


def test_classify_blocks_on_unresolved_conflict():
    entry = _bib_entry()
    canon = _canon_with_strong_id_and_evidence()
    canon.year = CanonicalField[int](
        value=2023, evidence=[], conflict=ConflictClass.ONLINE_VS_ISSUE_YEAR
    )
    verdict = classify_entry(entry, canon, findings=[], sanity_ok=True)
    assert verdict.classification == "needs-review"
    assert any("unresolved conflict on field `year`" in r for r in verdict.reasons)


def test_classify_blocks_on_error_severity_finding():
    entry = _bib_entry()
    canon = _canon_with_strong_id_and_evidence()
    f = AuditFinding(
        entry_key=entry.key,
        finding_type=FindingType.YEAR_MISMATCH,
        severity="error",
        confidence="high",
        field="year",
        current_value=2023,
        suggested_value=2022,
        explanation="Crossref says 2022, entry says 2023",
    )
    verdict = classify_entry(entry, canon, findings=[f], sanity_ok=True)
    assert verdict.classification == "needs-review"
    assert any("blocking finding" in r for r in verdict.reasons)


def test_classify_blocks_on_sanity_check_fail():
    entry = _bib_entry()
    canon = _canon_with_strong_id_and_evidence()
    verdict = classify_entry(
        entry, canon, findings=[], sanity_ok=False, sanity_issues=["unbalanced braces"]
    )
    assert verdict.classification == "needs-review"
    assert any("LLM sanity check failed" in r for r in verdict.reasons)


# ---------- integration: export_bib end-to-end (offline) ---------------------

@pytest.mark.asyncio
async def test_export_bib_offline_all_needs_review():
    """With no providers and no evidence, every entry lands in needs-review."""
    entries = parse_bibtex_file(BIB_DIR / "case_04_institution_as_author.bib")
    # No providers → no evidence
    canonicals: dict[str, CanonicalPublication] = {}
    for e in entries:
        canonicals[e.key] = CanonicalPublication(identity=PublicationIdentity())
    findings: list[AuditFinding] = []
    profile = load_default_profile()
    llm = StubLLMClient()

    result = await export_bib(entries, canonicals, findings, profile, llm)
    assert len(result.verified) == 0
    assert len(result.needs_review) == len(entries)
    # Every needs-review entry has at least one reason
    for c in result.needs_review:
        assert len(c.reasons) > 0


@pytest.mark.asyncio
async def test_export_write_outputs_creates_all_three_files(tmp_path):
    entries = parse_bibtex_file(BIB_DIR / "case_04_institution_as_author.bib")
    canonicals = {e.key: CanonicalPublication(identity=PublicationIdentity()) for e in entries}
    profile = load_default_profile()

    result = await export_bib(entries, canonicals, [], profile, StubLLMClient())
    v_path, n_path, s_path = write_export_outputs(result, profile, tmp_path, "case_04")

    assert v_path.exists() and v_path.name == "case_04.verified.bib"
    assert n_path.exists() and n_path.name == "case_04.needs-review.bib"
    assert s_path.exists() and s_path.name == "case_04.export-summary.md"
    # needs-review file should contain the UNVERIFIED annotation
    text = n_path.read_text(encoding="utf-8")
    assert "UNVERIFIED" in text
    # summary should mention totals
    summary = s_path.read_text(encoding="utf-8")
    assert "Total entries" in summary


@pytest.mark.asyncio
async def test_export_verified_when_evidence_provided():
    """Force a canonical with a strong id + evidence → entry qualifies."""
    entries = parse_bibtex_file(BIB_DIR / "case_04_institution_as_author.bib")
    assert len(entries) == 1
    key = entries[0].key
    canonicals = {key: _canon_with_strong_id_and_evidence()}
    profile = load_default_profile()

    result = await export_bib(entries, canonicals, [], profile, StubLLMClient())
    assert len(result.verified) == 1
    assert result.verified[0].entry_key == key


# ---------- CLI smoke test ---------------------------------------------------

def test_cli_export_offline(tmp_path):
    """End-to-end: `cpr export` with --no-network and --llm off."""
    runner = CliRunner()
    bib_src = BIB_DIR / "case_04_institution_as_author.bib"
    out_dir = tmp_path / "out"
    result = runner.invoke(
        app,
        ["export", str(bib_src), "--out-dir", str(out_dir), "--no-network", "--llm", "off"],
    )
    assert result.exit_code == 0, result.stdout
    assert (out_dir / f"{bib_src.stem}.verified.bib").exists()
    assert (out_dir / f"{bib_src.stem}.needs-review.bib").exists()
    assert (out_dir / f"{bib_src.stem}.export-summary.md").exists()
