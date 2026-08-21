"""Markdown audit report (§41 layout + §46 payload)."""
from __future__ import annotations

from ..schemas import AuditFinding, AuditReport


_SEVERITY_MARKS = {
    "info": "ℹ️",
    "warning": "⚠️",
    "error": "❌",
    "critical": "🚨",
}


def render_markdown_report(report: AuditReport) -> str:
    out: list[str] = []
    out.append(f"# Reference audit — `{report.input_path}`")
    out.append("")
    out.append(f"- Entries scanned: **{report.entries_total}**")
    out.append(f"- Entries with findings: **{report.entries_with_findings}**")
    out.append(f"- Generated at: {report.generated_at.isoformat()}")
    out.append("")

    summary = report.summary()
    if summary:
        out.append("## Summary")
        out.append("")
        out.append("| Finding type | Count |")
        out.append("| --- | ---: |")
        for k, v in sorted(summary.items(), key=lambda kv: -kv[1]):
            out.append(f"| `{k}` | {v} |")
        out.append("")

    if not report.findings:
        out.append("_No findings — every entry parses cleanly and matches its authoritative sources._")
        return "\n".join(out) + "\n"

    # Group by entry key
    by_key: dict[str, list[AuditFinding]] = {}
    for f in report.findings:
        by_key.setdefault(f.entry_key, []).append(f)

    out.append("## Findings")
    out.append("")
    for key, findings in sorted(by_key.items()):
        out.append(f"### `@{key}`")
        out.append("")
        for f in findings:
            mark = _SEVERITY_MARKS.get(f.severity, "•")
            out.append(f"- {mark} **{f.finding_type.value}** — confidence: `{f.confidence}`")
            if f.field:
                out.append(f"  - field: `{f.field}`")
            if f.current_value is not None:
                out.append(f"  - before: `{_fmt(f.current_value)}`")
            if f.suggested_value is not None:
                out.append(f"  - after:  `{_fmt(f.suggested_value)}`")
            if f.explanation:
                out.append(f"  - reason: {f.explanation}")
            if f.conflict is not None:
                out.append(f"  - conflict class: `{f.conflict.value}`")
            if f.evidence:
                out.append("  - evidence:")
                for c in f.evidence:
                    out.append(f"    - `{c.source}` (tier {c.authority_tier}) → {c.source_url}")
        out.append("")
    return "\n".join(out) + "\n"


def _fmt(v) -> str:
    if isinstance(v, list):
        return ", ".join(_fmt_one(x) for x in v)
    return _fmt_one(v)


def _fmt_one(x) -> str:
    # Author model → prefer formatted; else raw; else display()
    if hasattr(x, "family") and hasattr(x, "given"):
        return x.formatted or getattr(x, "raw", "") or (x.family or "")
    return str(x)
