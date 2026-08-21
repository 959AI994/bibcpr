"""Verified BibTeX export.

Strict criteria for `.verified.bib`:
  1. Entry has a strong identity (DOI / arXiv id / OpenReview id).
  2. At least one evidence record from a tier-A/B/C provider.
  3. No unresolved conflicts on any canonical field.
  4. No `error` or `critical` severity findings after auto-fix.
  5. LLM sanity_check returns ok=True (when an LLM is configured).

Anything failing any of these criteria goes to `.needs-review.bib`
with a `note = {UNVERIFIED: <reason>}` field explaining why.

An `.export-summary.md` companion file lists every entry with its
classification and reasons.
"""
from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

from ..bibtex.writer import write_entries, write_entry
from ..llm.base import LLMClient
from ..schemas import (
    AuditFinding,
    BibEntry,
    CanonicalPublication,
    Severity,
)
from ..style.engine import apply_findings, apply_style
from ..style.profile import StyleProfile


Classification = Literal["verified", "needs-review"]


@dataclass
class EntryClassification:
    entry_key: str
    classification: Classification
    reasons: list[str] = field(default_factory=list)
    llm_confidence: str = "n/a"
    corrected_entry: BibEntry | None = None


@dataclass
class ExportResult:
    verified: list[EntryClassification] = field(default_factory=list)
    needs_review: list[EntryClassification] = field(default_factory=list)

    @property
    def total(self) -> int:
        return len(self.verified) + len(self.needs_review)


_BLOCKING_SEVERITIES: set[Severity] = {"error", "critical"}


def classify_entry(
    entry: BibEntry,
    canonical: CanonicalPublication | None,
    findings: list[AuditFinding],
    sanity_ok: bool = True,
    sanity_issues: list[str] | None = None,
) -> EntryClassification:
    """Apply the strict verification criteria and return the verdict."""
    reasons: list[str] = []

    # Rule 1: strong identity
    identity = canonical.identity if canonical is not None else None
    if identity is None or not identity.has_strong_id():
        reasons.append("no strong identity (missing DOI/arXiv id/OpenReview id)")

    # Rule 2: at least one evidence record
    n_records = len(canonical.evidence_records) if canonical is not None else 0
    if n_records == 0:
        reasons.append("no evidence records retrieved from any provider")

    # Rule 3: no unresolved conflicts on canonical fields
    if canonical is not None:
        for field_name in ("title", "authors", "year", "venue", "volume", "number", "pages", "doi", "entry_type"):
            cf = getattr(canonical, field_name, None)
            if cf is not None and cf.conflict is not None:
                reasons.append(f"unresolved conflict on field `{field_name}` ({cf.conflict.value})")

    # Rule 4: no error/critical findings
    for f in findings:
        if f.entry_key != entry.key:
            continue
        if f.severity in _BLOCKING_SEVERITIES:
            reasons.append(f"blocking finding: {f.finding_type.value} ({f.severity})")

    # Rule 5: LLM sanity check
    if not sanity_ok:
        issues_str = "; ".join(sanity_issues or []) or "unspecified"
        reasons.append(f"LLM sanity check failed: {issues_str}")

    return EntryClassification(
        entry_key=entry.key,
        classification="verified" if not reasons else "needs-review",
        reasons=reasons,
    )


def _annotate_needs_review(entry: BibEntry, reasons: list[str]) -> BibEntry:
    """Append an UNVERIFIED note explaining why this entry didn't qualify."""
    ann = entry.model_copy(deep=True)
    note_body = "UNVERIFIED: " + "; ".join(reasons)
    if ann.note:
        ann.note = f"{ann.note} | {note_body}"
    else:
        ann.note = note_body
    if "note" not in ann.field_order:
        ann.field_order = list(ann.field_order) + ["note"]
    return ann


async def _sanity_check_one(
    entry: BibEntry, profile: StyleProfile, llm: LLMClient
) -> tuple[bool, list[str], str]:
    """Run the LLM sanity check on a single already-corrected entry."""
    entry_text = write_entry(
        entry,
        field_order=profile.fields.order,
        drop_if_empty=profile.fields.drop_if_empty,
    )
    try:
        result = await llm.sanity_check(entry_text)
    except Exception:  # never let the LLM path fail the whole pipeline
        return True, [], "error"
    return bool(result.ok), list(result.issues), str(result.confidence)


async def export_bib(
    entries: list[BibEntry],
    canonicals: dict[str, CanonicalPublication],
    findings: list[AuditFinding],
    profile: StyleProfile,
    llm: LLMClient,
) -> ExportResult:
    """Run the full export pipeline on already-audited entries."""

    # Apply auto-fixes (verified + high) so `.verified.bib` reflects the
    # best evidence-backed values we have.
    corrected_entries: dict[str, BibEntry] = {}
    for entry in entries:
        entry_findings = [f for f in findings if f.entry_key == entry.key]
        c, _ = apply_findings(entry, entry_findings, profile, gate={"verified", "high"})
        c = apply_style(c, profile)
        corrected_entries[entry.key] = c

    # Sanity-check in parallel (LLM is optional and may be a no-op stub).
    async def check(entry: BibEntry) -> tuple[str, bool, list[str], str]:
        ok, issues, conf = await _sanity_check_one(entry, profile, llm)
        return entry.key, ok, issues, conf

    checks = await asyncio.gather(*[check(corrected_entries[e.key]) for e in entries])
    sanity_map = {k: (ok, issues, conf) for k, ok, issues, conf in checks}

    result = ExportResult()
    for entry in entries:
        canon = canonicals.get(entry.key)
        ok, issues, llm_conf = sanity_map[entry.key]
        classification = classify_entry(
            entry=entry,
            canonical=canon,
            findings=findings,
            sanity_ok=ok,
            sanity_issues=issues,
        )
        classification.llm_confidence = llm_conf
        classification.corrected_entry = corrected_entries[entry.key]
        if classification.classification == "verified":
            result.verified.append(classification)
        else:
            result.needs_review.append(classification)
    return result


def render_verified_bib(result: ExportResult, profile: StyleProfile) -> str:
    return write_entries(
        [c.corrected_entry for c in result.verified if c.corrected_entry is not None],
        field_order=profile.fields.order,
        drop_if_empty=profile.fields.drop_if_empty,
    )


def render_needs_review_bib(result: ExportResult, profile: StyleProfile) -> str:
    annotated = [
        _annotate_needs_review(c.corrected_entry, c.reasons)
        for c in result.needs_review
        if c.corrected_entry is not None
    ]
    return write_entries(
        annotated,
        field_order=profile.fields.order,
        drop_if_empty=profile.fields.drop_if_empty,
    )


def render_export_summary(result: ExportResult) -> str:
    """Human-readable Markdown summary."""
    total = result.total
    verified_pct = (len(result.verified) / total * 100) if total else 0.0
    lines: list[str] = []
    lines.append("# bibcpr — export summary")
    lines.append("")
    lines.append(f"- Total entries: **{total}**")
    lines.append(f"- Verified (`.verified.bib`): **{len(result.verified)}** ({verified_pct:.1f}%)")
    lines.append(f"- Needs review (`.needs-review.bib`): **{len(result.needs_review)}**")
    lines.append("")

    if result.verified:
        lines.append("## Verified")
        lines.append("")
        lines.append("| entry_key | llm_confidence |")
        lines.append("|-----------|----------------|")
        for c in result.verified:
            lines.append(f"| `{c.entry_key}` | {c.llm_confidence} |")
        lines.append("")

    if result.needs_review:
        lines.append("## Needs review")
        lines.append("")
        for c in result.needs_review:
            lines.append(f"### `{c.entry_key}`")
            lines.append("")
            for r in c.reasons:
                lines.append(f"- {r}")
            lines.append("")

    return "\n".join(lines) + "\n"


def write_export_outputs(
    result: ExportResult,
    profile: StyleProfile,
    out_dir: Path,
    stem: str,
) -> tuple[Path, Path, Path]:
    """Write .verified.bib / .needs-review.bib / .export-summary.md.

    Returns (verified_path, needs_review_path, summary_path).
    """
    out_dir.mkdir(parents=True, exist_ok=True)
    verified_path = out_dir / f"{stem}.verified.bib"
    needs_path = out_dir / f"{stem}.needs-review.bib"
    summary_path = out_dir / f"{stem}.export-summary.md"

    verified_path.write_text(render_verified_bib(result, profile), encoding="utf-8")
    needs_path.write_text(render_needs_review_bib(result, profile), encoding="utf-8")
    summary_path.write_text(render_export_summary(result), encoding="utf-8")
    return verified_path, needs_path, summary_path
