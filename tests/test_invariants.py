"""Invariant tests spanning every golden case:

1. §0 no-hallucination: For any AuditFinding where evidence == [],
   suggested_value must equal current_value (or be None).
2. §18 citation-key preservation: sorted(before.keys) == sorted(after.keys)
   after a fix run.
"""
import asyncio
from pathlib import Path

import pytest

from cpr.audit.engine import AuditContext, run_audit
from cpr.bibtex.parser import parse_bibtex_file
from cpr.bibtex.writer import write_entries
from cpr.style.engine import apply_findings, apply_style
from cpr.style.profile import load_default_profile


HERE = Path(__file__).parent
BIB_DIR = HERE / "bibs"


ALL_BIBS = sorted(BIB_DIR.glob("*.bib"))


@pytest.mark.parametrize("bib_path", ALL_BIBS, ids=lambda p: p.name)
def test_no_hallucination_invariant(bib_path: Path):
    entries = parse_bibtex_file(bib_path)
    ctx = AuditContext(input_path=str(bib_path), providers=[], no_network=True)
    findings, _ = asyncio.run(run_audit(entries, ctx))
    for f in findings:
        if not f.evidence:
            # No evidence — must not propose a change.
            # (`suggested_value is None` is acceptable; equality to current is too.)
            assert (
                f.suggested_value is None
                or f.suggested_value == f.current_value
            ), (
                f"Hallucination in {bib_path.name}: finding "
                f"{f.finding_type.value} on {f.entry_key} has no evidence "
                f"but proposes {f.suggested_value!r} != {f.current_value!r}"
            )


@pytest.mark.parametrize("bib_path", ALL_BIBS, ids=lambda p: p.name)
def test_citation_key_preservation_invariant(bib_path: Path):
    profile = load_default_profile()
    entries = parse_bibtex_file(bib_path)
    ctx = AuditContext(input_path=str(bib_path), providers=[], no_network=True)
    findings, _ = asyncio.run(run_audit(entries, ctx))

    corrected = []
    for e in entries:
        entry_findings = [f for f in findings if f.entry_key == e.key]
        c, _ = apply_findings(e, entry_findings, profile)
        c = apply_style(c, profile)
        corrected.append(c)

    input_keys = sorted(e.key for e in entries)
    output_keys = sorted(c.key for c in corrected)
    assert input_keys == output_keys, (
        f"citation keys changed for {bib_path.name}: {input_keys} → {output_keys}"
    )


def test_report_dict_serializable_across_all_findings():
    """Every AuditFinding.to_report_dict() must be JSON-serializable."""
    import json
    for bib_path in ALL_BIBS:
        entries = parse_bibtex_file(bib_path)
        ctx = AuditContext(input_path=str(bib_path), providers=[], no_network=True)
        findings, _ = asyncio.run(run_audit(entries, ctx))
        for f in findings:
            payload = f.to_report_dict()
            json.dumps(payload, default=str)
