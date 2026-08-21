"""JSON audit report (§46)."""
from __future__ import annotations

import json

from ..schemas import AuditReport


def render_json_report(report: AuditReport) -> str:
    payload = {
        "input_path": report.input_path,
        "entries_total": report.entries_total,
        "entries_with_findings": report.entries_with_findings,
        "generated_at": report.generated_at.isoformat(),
        "summary": report.summary(),
        "findings": [f.to_report_dict() for f in report.findings],
    }
    return json.dumps(payload, indent=2, sort_keys=True, default=str)
