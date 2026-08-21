"""CLI end-to-end tests (offline mode)."""
import subprocess
import sys
from pathlib import Path

import pytest


HERE = Path(__file__).parent
BIB = HERE / "bibs" / "case_10_preprint_no_formal.bib"


def _run_cli(args: list[str], cwd: Path):
    return subprocess.run(
        [sys.executable, "-m", "cpr.cli", *args],
        cwd=str(cwd),
        capture_output=True,
        text=True,
        timeout=30,
    )


def test_cli_check_no_network(tmp_path: Path):
    r = _run_cli(["check", str(BIB), "--no-network"], cwd=tmp_path)
    assert r.returncode == 0, r.stderr
    assert "entries scanned" in r.stdout


def test_cli_fix_dry_run_writes_nothing(tmp_path: Path):
    target = tmp_path / "in.bib"
    target.write_text(BIB.read_text(encoding="utf-8"), encoding="utf-8")
    r = _run_cli(["fix", str(target), "--dry-run", "--no-network"], cwd=tmp_path)
    assert r.returncode == 0, r.stderr
    # Original unchanged
    assert target.read_text(encoding="utf-8") == BIB.read_text(encoding="utf-8")
    assert not (tmp_path / "in.corrected.bib").exists()


def test_cli_fix_writes_corrected(tmp_path: Path):
    target = tmp_path / "in.bib"
    target.write_text(BIB.read_text(encoding="utf-8"), encoding="utf-8")
    r = _run_cli(["fix", str(target), "--no-network"], cwd=tmp_path)
    assert r.returncode == 0, r.stderr
    corrected = tmp_path / "in.corrected.bib"
    assert corrected.exists()
    # Reports also written
    assert (tmp_path / "reference-audit.md").exists()
    assert (tmp_path / "reference-audit.json").exists()
    # Key set preserved
    assert "@article{case10," in corrected.read_text(encoding="utf-8")


def test_cli_explain(tmp_path: Path):
    r = _run_cli(["explain", str(BIB), "case10", "--no-network"], cwd=tmp_path)
    assert r.returncode == 0, r.stderr
    assert "case10" in r.stdout


def test_cli_verify(tmp_path: Path):
    r = _run_cli(["verify", str(BIB), "case10", "--no-network"], cwd=tmp_path)
    assert r.returncode == 0, r.stderr
    assert "case10" in r.stdout
