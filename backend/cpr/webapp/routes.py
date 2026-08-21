"""FastAPI routes for the bibcpr web UI.

Endpoints:
  GET  /                          → index.html
  POST /api/upload                → accepts .bib file
  POST /api/paste                 → accepts pasted text
  POST /api/audit/{sid}           → run audit against providers (network)
  POST /api/audit-offline/{sid}   → run audit without network
  POST /api/apply                 → apply user-selected findings
  GET  /api/download/{sid}/{kind} → download bib/md/json

Everything is bound to localhost by default; nothing is persisted to
disk. See webapp/session.py for the (in-memory) session model.
"""
from __future__ import annotations

import difflib
from pathlib import Path

from fastapi import APIRouter, File, HTTPException, UploadFile
from fastapi.responses import HTMLResponse, PlainTextResponse

from ..audit.engine import AuditContext, build_audit_report, run_audit
from ..bibtex.parser import parse_bibtex_string
from ..bibtex.writer import write_entries
from ..providers.arxiv import ArxivProvider
from ..providers.cache import NullCache, get_default_cache
from ..providers.crossref import CrossrefProvider
from ..providers.dblp import DBLPProvider
from ..providers.openreview import OpenReviewProvider
from ..report.json_report import render_json_report
from ..report.markdown import render_markdown_report
from ..style.engine import apply_findings, apply_style
from ..style.profile import load_default_profile
from .models import (
    ApplyRequest,
    ApplyResponse,
    AuditResponse,
    PasteRequest,
    UploadResponse,
)
from .session import get_store

router = APIRouter()

_STATIC_DIR = Path(__file__).parent / "static"


@router.get("/", response_class=HTMLResponse)
async def index() -> HTMLResponse:
    html = (_STATIC_DIR / "index.html").read_text(encoding="utf-8")
    return HTMLResponse(html)


@router.get("/health")
async def health() -> dict:
    return {"ok": True}


# ---------------------------------------------------------------------------
# Upload / paste
# ---------------------------------------------------------------------------
@router.post("/api/upload", response_model=UploadResponse)
async def upload(file: UploadFile = File(...)) -> UploadResponse:
    raw = await file.read()
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError:
        raise HTTPException(status_code=400, detail="File must be UTF-8 encoded")
    try:
        entries = parse_bibtex_string(text)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Failed to parse .bib: {exc}")
    state = get_store().create(bib_text=text, filename=file.filename or "uploaded.bib")
    state.entries = entries
    return UploadResponse(session_id=state.id, filename=state.filename, n_entries=len(entries))


@router.post("/api/paste", response_model=UploadResponse)
async def paste(req: PasteRequest) -> UploadResponse:
    try:
        entries = parse_bibtex_string(req.bib_text)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Failed to parse .bib: {exc}")
    state = get_store().create(bib_text=req.bib_text, filename=req.filename)
    state.entries = entries
    return UploadResponse(session_id=state.id, filename=state.filename, n_entries=len(entries))


# ---------------------------------------------------------------------------
# Audit
# ---------------------------------------------------------------------------
async def _run(sid: str, no_network: bool) -> AuditResponse:
    state = get_store().get(sid)
    if state is None:
        raise HTTPException(status_code=404, detail=f"Unknown session {sid}")
    if no_network:
        cache = NullCache()
        providers = []
    else:
        cache = get_default_cache()
        providers = [
            CrossrefProvider(cache=cache),
            DBLPProvider(cache=cache),
            OpenReviewProvider(cache=cache),
            ArxivProvider(cache=cache),
        ]
    ctx = AuditContext(input_path=state.filename, providers=providers, no_network=no_network)
    try:
        findings, canonicals = await run_audit(state.entries, ctx)
    finally:
        for p in providers:
            await p.aclose()
    report = build_audit_report(state.filename, state.entries, findings)
    state.report = report
    state.canonicals = canonicals
    state.markdown_report = render_markdown_report(report)
    state.json_report = render_json_report(report)
    return AuditResponse(
        session_id=state.id,
        report=report,
        entry_keys=[e.key for e in state.entries],
    )


@router.post("/api/audit/{sid}", response_model=AuditResponse)
async def audit(sid: str) -> AuditResponse:
    return await _run(sid, no_network=False)


@router.post("/api/audit-offline/{sid}", response_model=AuditResponse)
async def audit_offline(sid: str) -> AuditResponse:
    return await _run(sid, no_network=True)


# ---------------------------------------------------------------------------
# Apply
# ---------------------------------------------------------------------------
@router.post("/api/apply", response_model=ApplyResponse)
async def apply(req: ApplyRequest) -> ApplyResponse:
    state = get_store().get(req.session_id)
    if state is None:
        raise HTTPException(status_code=404, detail=f"Unknown session {req.session_id}")
    if state.report is None:
        raise HTTPException(status_code=400, detail="Run /api/audit first")

    profile = load_default_profile()

    # Build the accepted set. If `accepted` is None → auto-apply verified+high.
    # If explicit → allow any confidence (user has taken responsibility).
    accepted_keys: set[str] | None
    if req.accepted is None:
        accepted_keys = None  # sentinel: use default gate
    else:
        accepted_keys = set(req.accepted)

    corrected_entries = []
    applied_findings = []
    for entry in state.entries:
        entry_findings = [f for f in state.report.findings if f.entry_key == entry.key]
        if accepted_keys is None:
            selected = entry_findings
            gate = {"verified", "high"}
        else:
            selected = [
                f for f in entry_findings
                if f"{f.entry_key}::{f.finding_type.value}" in accepted_keys
            ]
            # user explicit → override gate
            gate = {"verified", "high", "medium", "low"}
        c, applied = apply_findings(entry, selected, profile, gate=gate)
        c = apply_style(c, profile)
        corrected_entries.append(c)
        applied_findings.extend(applied)

    text = write_entries(
        corrected_entries,
        field_order=profile.fields.order,
        drop_if_empty=profile.fields.drop_if_empty,
    )
    state.corrected_bib_text = text

    orig_lines = state.bib_text.splitlines()
    new_lines = text.splitlines()
    added = sum(1 for _ in difflib.ndiff(orig_lines, new_lines) if _.startswith("+ "))
    removed = sum(1 for _ in difflib.ndiff(orig_lines, new_lines) if _.startswith("- "))

    return ApplyResponse(
        session_id=state.id,
        n_applied=len(applied_findings),
        diff_summary={"lines_added": added, "lines_removed": removed},
    )


# ---------------------------------------------------------------------------
# Download
# ---------------------------------------------------------------------------
@router.get("/api/download/{sid}/{kind}", response_class=PlainTextResponse)
async def download(sid: str, kind: str) -> PlainTextResponse:
    state = get_store().get(sid)
    if state is None:
        raise HTTPException(status_code=404, detail=f"Unknown session {sid}")
    if kind == "corrected":
        if state.corrected_bib_text is None:
            raise HTTPException(status_code=400, detail="Run /api/apply first")
        return PlainTextResponse(
            state.corrected_bib_text,
            media_type="application/x-bibtex",
            headers={"Content-Disposition": f'attachment; filename="{state.filename.rsplit(".", 1)[0]}.corrected.bib"'},
        )
    if kind == "markdown":
        if state.markdown_report is None:
            raise HTTPException(status_code=400, detail="Run /api/audit first")
        return PlainTextResponse(
            state.markdown_report,
            media_type="text/markdown",
            headers={"Content-Disposition": 'attachment; filename="reference-audit.md"'},
        )
    if kind == "json":
        if state.json_report is None:
            raise HTTPException(status_code=400, detail="Run /api/audit first")
        return PlainTextResponse(
            state.json_report,
            media_type="application/json",
            headers={"Content-Disposition": 'attachment; filename="reference-audit.json"'},
        )
    if kind == "original":
        return PlainTextResponse(
            state.bib_text,
            media_type="application/x-bibtex",
            headers={"Content-Disposition": f'attachment; filename="{state.filename}"'},
        )
    raise HTTPException(status_code=404, detail=f"Unknown kind: {kind}")


# ---------------------------------------------------------------------------
# Diff (server-computed unified diff for one entry)
# ---------------------------------------------------------------------------
@router.get("/api/diff/{sid}/{key}", response_class=PlainTextResponse)
async def diff_entry(sid: str, key: str) -> PlainTextResponse:
    state = get_store().get(sid)
    if state is None:
        raise HTTPException(status_code=404, detail=f"Unknown session {sid}")
    if state.corrected_bib_text is None:
        raise HTTPException(status_code=400, detail="Run /api/apply first")
    orig_entry = _extract_entry_text(state.bib_text, key)
    new_entry = _extract_entry_text(state.corrected_bib_text, key)
    diff = "\n".join(
        difflib.unified_diff(
            orig_entry.splitlines(),
            new_entry.splitlines(),
            fromfile=f"{key} (before)",
            tofile=f"{key} (after)",
            lineterm="",
        )
    )
    return PlainTextResponse(diff or "(no changes)")


def _extract_entry_text(bib_text: str, key: str) -> str:
    """Best-effort brace-balanced slice of one @entry{key,...} block."""
    needle = "{" + key + ","
    i = bib_text.find(needle)
    if i < 0:
        needle = "{" + key + " "
        i = bib_text.find(needle)
    if i < 0:
        return ""
    # walk back to the '@'
    at = bib_text.rfind("@", 0, i)
    if at < 0:
        return ""
    # walk forward matching braces
    depth = 0
    j = at
    while j < len(bib_text):
        c = bib_text[j]
        if c == "{":
            depth += 1
        elif c == "}":
            depth -= 1
            if depth == 0:
                return bib_text[at : j + 1]
        j += 1
    return bib_text[at:]
