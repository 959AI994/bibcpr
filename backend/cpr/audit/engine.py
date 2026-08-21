"""Audit engine: run all auditors, collect findings."""
from __future__ import annotations

import asyncio
from dataclasses import dataclass, field

from ..bibtex.identity import extract_identity
from ..providers.base import EvidenceProvider, ProviderError
from ..resolver.canonical import build_canonical
from ..schemas import (
    AuditFinding,
    AuditReport,
    BibEntry,
    CanonicalPublication,
    EvidenceRecord,
    FindingType,
    PublicationIdentity,
)
from .acm_pages import audit_acm_pages
from .arxiv_vs_formal import audit_arxiv_vs_formal
from .duplicates import audit_duplicates
from .entry_type import audit_entry_type
from .findings import build_finding
from .institution import audit_institution_as_author
from .metadata import audit_metadata


@dataclass
class AuditContext:
    input_path: str
    providers: list[EvidenceProvider] = field(default_factory=list)
    no_network: bool = False


async def _fetch_evidence(
    identity: PublicationIdentity, providers: list[EvidenceProvider]
) -> list[EvidenceRecord]:
    """Query every provider by every available id in parallel, dedup."""
    if not providers:
        return []
    tasks: list = []
    for p in providers:
        if identity.doi:
            tasks.append(_safe(p.fetch_by_doi(identity.doi)))
        if identity.arxiv_id:
            tasks.append(_safe(p.fetch_by_arxiv(identity.arxiv_id)))
    if not tasks:
        return []
    results = await asyncio.gather(*tasks)
    out: list[EvidenceRecord] = []
    for r in results:
        if r is not None:
            out.append(r)
    return out


async def _safe(coro):
    try:
        return await coro
    except ProviderError:
        return None


async def run_audit(entries: list[BibEntry], ctx: AuditContext) -> tuple[list[AuditFinding], dict[str, CanonicalPublication]]:
    """Run all auditors on `entries` and return findings + canonical publications."""
    findings: list[AuditFinding] = []
    canonicals: dict[str, CanonicalPublication] = {}

    # Cross-entry auditors first
    findings.extend(audit_duplicates(entries))
    for entry in entries:
        findings.extend(audit_institution_as_author(entry))

    # Per-entry evidence + audits (parallel across entries)
    async def process(entry: BibEntry) -> tuple[str, CanonicalPublication, list[AuditFinding]]:
        identity = extract_identity(entry)
        records: list[EvidenceRecord] = []
        if not ctx.no_network:
            records = await _fetch_evidence(identity, ctx.providers)
        canon = build_canonical(identity, records)
        per_findings: list[AuditFinding] = []
        per_findings.extend(audit_metadata(entry, canon))
        per_findings.extend(audit_entry_type(entry, canon))
        per_findings.extend(audit_arxiv_vs_formal(entry, canon))
        per_findings.extend(audit_acm_pages(entry, canon))
        if not records and not identity.has_strong_id():
            per_findings.append(build_finding(
                entry_key=entry.key,
                finding_type=FindingType.UNVERIFIED_ENTRY,
                severity="info",
                field=None,
                current_value=None,
                suggested_value=None,
                explanation=(
                    "This entry has no DOI, arXiv id, or OpenReview id — no "
                    "authoritative evidence could be retrieved. The entry is "
                    "preserved unchanged."
                ),
                evidence=[],
                confidence="low",
            ))
        return entry.key, canon, per_findings

    results = await asyncio.gather(*[process(e) for e in entries])
    for key, canon, per in results:
        canonicals[key] = canon
        findings.extend(per)
    return findings, canonicals


def build_audit_report(input_path: str, entries: list[BibEntry], findings: list[AuditFinding]) -> AuditReport:
    keys_with = {f.entry_key for f in findings}
    return AuditReport(
        input_path=input_path,
        entries_total=len(entries),
        entries_with_findings=len(keys_with),
        findings=findings,
    )
