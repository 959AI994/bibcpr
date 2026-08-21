"""Web UI route tests.

All tests use `/api/audit-offline/{sid}` so they run without network
and match the offline-CI policy the rest of the suite follows.
"""
from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from cpr.webapp.server import create_app
from cpr.webapp.session import get_store


BIB_DIR = Path(__file__).parent / "bibs"


@pytest.fixture()
def client():
    # Fresh session store per test
    get_store()._sessions.clear()
    app = create_app()
    with TestClient(app) as c:
        yield c


def _load_case(name: str) -> str:
    return (BIB_DIR / name).read_text(encoding="utf-8")


def test_health(client):
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json() == {"ok": True}


def test_index_page(client):
    r = client.get("/")
    assert r.status_code == 200
    assert "bibcpr" in r.text
    assert "<title>bibcpr" in r.text


def test_paste_then_offline_audit_then_apply_then_download(client):
    bib = _load_case("case_04_institution_as_author.bib")

    # Paste
    r = client.post("/api/paste", json={"bib_text": bib, "filename": "case_04.bib"})
    assert r.status_code == 200, r.text
    sid = r.json()["session_id"]
    assert r.json()["n_entries"] == 1

    # Audit (offline; no providers)
    r = client.post(f"/api/audit-offline/{sid}")
    assert r.status_code == 200, r.text
    report = r.json()["report"]
    # institution-as-author should fire even offline
    types = {f["finding_type"] for f in report["findings"]}
    assert "institution_as_author" in types

    # Apply with default gate (accepted=None)
    r = client.post("/api/apply", json={"session_id": sid, "accepted": None})
    assert r.status_code == 200, r.text
    assert "n_applied" in r.json()

    # Downloads
    r = client.get(f"/api/download/{sid}/corrected")
    assert r.status_code == 200
    assert r.text.startswith("@")

    r = client.get(f"/api/download/{sid}/markdown")
    assert r.status_code == 200
    assert "# Reference audit" in r.text

    r = client.get(f"/api/download/{sid}/json")
    assert r.status_code == 200
    import json
    assert "findings" in json.loads(r.text)


def test_upload_endpoint(client):
    # Two entries with the same title+year → duplicate_publication
    bib = b"""
@article{a,
  title = {Same Paper},
  author = {Alice},
  year = {2023}
}
@article{b,
  title = {Same Paper},
  author = {Alice},
  year = {2023}
}
"""
    r = client.post(
        "/api/upload",
        files={"file": ("dup.bib", bib, "application/x-bibtex")},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["filename"] == "dup.bib"
    assert body["n_entries"] == 2

    sid = body["session_id"]
    r = client.post(f"/api/audit-offline/{sid}")
    assert r.status_code == 200
    types = {f["finding_type"] for f in r.json()["report"]["findings"]}
    assert "duplicate_publication" in types


def test_apply_with_explicit_accepted_ids(client):
    bib = _load_case("case_04_institution_as_author.bib")
    r = client.post("/api/paste", json={"bib_text": bib})
    sid = r.json()["session_id"]
    client.post(f"/api/audit-offline/{sid}")

    # Apply with an empty accepted set → nothing applied
    r = client.post("/api/apply", json={"session_id": sid, "accepted": []})
    assert r.status_code == 200
    assert r.json()["n_applied"] == 0

    # corrected bib should still exist and equal (semantically) the original
    r = client.get(f"/api/download/{sid}/corrected")
    assert r.status_code == 200


def test_download_before_audit_returns_400(client):
    r = client.post("/api/paste", json={"bib_text": "@misc{x, title={t}}"})
    sid = r.json()["session_id"]
    r = client.get(f"/api/download/{sid}/markdown")
    assert r.status_code == 400


def test_download_corrected_before_apply_returns_400(client):
    r = client.post("/api/paste", json={"bib_text": "@misc{x, title={t}}"})
    sid = r.json()["session_id"]
    client.post(f"/api/audit-offline/{sid}")
    r = client.get(f"/api/download/{sid}/corrected")
    assert r.status_code == 400


def test_unknown_session(client):
    r = client.post("/api/audit-offline/nope")
    assert r.status_code == 404
    r = client.get("/api/download/nope/markdown")
    assert r.status_code == 404


def test_malformed_bib_upload(client):
    r = client.post("/api/paste", json={"bib_text": "not-a-bib"})
    # bibtexparser is lenient — expect either 200 with 0 entries or 400
    assert r.status_code in (200, 400)
    if r.status_code == 200:
        assert r.json()["n_entries"] == 0


def test_diff_endpoint_after_apply(client):
    bib = _load_case("case_04_institution_as_author.bib")
    r = client.post("/api/paste", json={"bib_text": bib})
    sid = r.json()["session_id"]
    client.post(f"/api/audit-offline/{sid}")
    client.post("/api/apply", json={"session_id": sid, "accepted": None})

    # find the entry key from the paste
    entry_key = "case04"  # from tests/bibs/case_04
    r = client.get(f"/api/diff/{sid}/{entry_key}")
    assert r.status_code == 200
    # either a real diff or "(no changes)"
    assert r.text  # non-empty
