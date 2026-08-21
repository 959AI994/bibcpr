"""Request / response models for the web UI."""
from __future__ import annotations

from pydantic import BaseModel

from ..schemas import AuditReport


class PasteRequest(BaseModel):
    bib_text: str
    filename: str = "pasted.bib"


class UploadResponse(BaseModel):
    session_id: str
    filename: str
    n_entries: int


class AuditResponse(BaseModel):
    session_id: str
    report: AuditReport
    # We include the raw entries so the UI can look up field-level context.
    entry_keys: list[str]


class ApplyRequest(BaseModel):
    session_id: str
    # Findings identified by (entry_key, finding_type). If empty, defaults
    # to auto-apply of verified+high (matches CLI `cpr fix`).
    accepted: list[str] | None = None  # ["<entry_key>::<finding_type>", ...]


class ApplyResponse(BaseModel):
    session_id: str
    n_applied: int
    diff_summary: dict[str, int]  # {"lines_added": …, "lines_removed": …}
