"""CPR CLI.

Subcommands:
  check   read-only audit
  fix     apply verified+high fixes; write .corrected.bib
  verify  deep-dive one entry
  explain human-readable per-entry report
"""
from __future__ import annotations

import asyncio
import json
import shutil
import sys
from pathlib import Path
from typing import Annotated, Any, Optional

import typer
from rich.console import Console
from rich.table import Table

from .audit.engine import AuditContext, build_audit_report, run_audit
from .bibtex.parser import parse_bibtex_file
from .bibtex.writer import write_entries
from .providers.arxiv import ArxivProvider
from .providers.cache import DiskCache, NullCache, get_default_cache
from .providers.crossref import CrossrefProvider
from .providers.dblp import DBLPProvider
from .providers.openreview import OpenReviewProvider
from .report.json_report import render_json_report
from .report.markdown import render_markdown_report
from .schemas import AuditReport, Confidence
from .style.engine import apply_findings, apply_style
from .style.profile import StyleProfile, load_default_profile
from .style.loader import load_profile
from .util.logging import setup_logging


app = typer.Typer(
    name="cpr",
    help="Correct Paper Reference — evidence-first BibTeX auditing/repair.",
    no_args_is_help=True,
)
console = Console()


def _build_providers(cache) -> list:
    return [
        CrossrefProvider(cache=cache),
        DBLPProvider(cache=cache),
        OpenReviewProvider(cache=cache),
        ArxivProvider(cache=cache),
    ]


async def _run_pipeline(
    bib_path: Path,
    no_network: bool,
    cache_dir: Path | None,
) -> tuple[AuditReport, dict, list]:
    entries = parse_bibtex_file(bib_path)
    cache = get_default_cache() if cache_dir is None else DiskCache(cache_dir / "cache.sqlite")
    if no_network:
        cache = NullCache()
    providers = [] if no_network else _build_providers(cache)
    ctx = AuditContext(input_path=str(bib_path), providers=providers, no_network=no_network)
    try:
        findings, canonicals = await run_audit(entries, ctx)
    finally:
        for p in providers:
            await p.aclose()
    report = build_audit_report(str(bib_path), entries, findings)
    return report, canonicals, entries


def _print_summary(report: AuditReport) -> None:
    console.print(f"[bold]{report.entries_total}[/bold] entries scanned, [bold]{report.entries_with_findings}[/bold] with findings.")
    summary = report.summary()
    if not summary:
        console.print("[green]No findings.[/green]")
        return
    table = Table(title="Findings by type")
    table.add_column("Finding")
    table.add_column("Count", justify="right")
    for k, v in sorted(summary.items(), key=lambda kv: -kv[1]):
        table.add_row(k, str(v))
    console.print(table)


# ---------------------------------------------------------------------------
# `cpr check`
# ---------------------------------------------------------------------------
@app.command()
def check(
    bib: Annotated[Path, typer.Argument(exists=True, dir_okay=False, readable=True)],
    json_path: Annotated[Optional[Path], typer.Option("--json", help="Write machine-readable JSON report.")] = None,
    report_path: Annotated[Optional[Path], typer.Option("--report", help="Write Markdown report.")] = None,
    no_network: Annotated[bool, typer.Option("--no-network", help="Skip evidence fetch (offline mode).")] = False,
    cache_dir: Annotated[Optional[Path], typer.Option("--cache-dir")] = None,
    profile_name: Annotated[str, typer.Option("--profile")] = "sjtu-ectl",
    verbose: Annotated[int, typer.Option("-v", "--verbose", count=True)] = 0,
):
    """Read-only audit — never writes .bib."""
    setup_logging(verbose)
    report, _, _ = asyncio.run(_run_pipeline(bib, no_network, cache_dir))
    _print_summary(report)
    if json_path is not None:
        json_path.write_text(render_json_report(report), encoding="utf-8")
        console.print(f"[dim]JSON report: {json_path}[/dim]")
    if report_path is not None:
        report_path.write_text(render_markdown_report(report), encoding="utf-8")
        console.print(f"[dim]Markdown report: {report_path}[/dim]")


# ---------------------------------------------------------------------------
# `cpr fix`
# ---------------------------------------------------------------------------
@app.command()
def fix(
    bib: Annotated[Path, typer.Argument(exists=True, dir_okay=False, readable=True)],
    output: Annotated[Optional[Path], typer.Option("--output")] = None,
    in_place: Annotated[bool, typer.Option("--in-place")] = False,
    backup: Annotated[bool, typer.Option("--backup")] = False,
    dry_run: Annotated[bool, typer.Option("--dry-run")] = False,
    interactive: Annotated[bool, typer.Option("--interactive")] = False,
    config: Annotated[Optional[Path], typer.Option("--config")] = None,
    no_network: Annotated[bool, typer.Option("--no-network")] = False,
    cache_dir: Annotated[Optional[Path], typer.Option("--cache-dir")] = None,
    profile_name: Annotated[str, typer.Option("--profile")] = "sjtu-ectl",
    verbose: Annotated[int, typer.Option("-v", "--verbose", count=True)] = 0,
):
    """Auto-apply verified/high findings; write corrected .bib."""
    setup_logging(verbose)
    profile: StyleProfile = load_profile(config) if config else load_default_profile()
    report, canonicals, entries = asyncio.run(_run_pipeline(bib, no_network, cache_dir))
    _print_summary(report)

    gate: set[Confidence] = {"verified", "high"}
    if interactive:
        gate.add("medium")

    corrected_entries = []
    applied_findings = []
    for entry in entries:
        entry_findings = [f for f in report.findings if f.entry_key == entry.key]
        # If interactive, prompt for each medium finding
        selected = list(entry_findings)
        if interactive:
            selected = _interactive_select(entry_findings)
        c, applied = apply_findings(entry, selected, profile, gate=gate)
        c = apply_style(c, profile)
        corrected_entries.append(c)
        applied_findings.extend(applied)

    text = write_entries(
        corrected_entries,
        field_order=profile.fields.order,
        drop_if_empty=profile.fields.drop_if_empty,
    )

    if dry_run:
        console.print("[yellow]--dry-run: no files written.[/yellow]")
        console.print(f"Would apply [bold]{len(applied_findings)}[/bold] finding(s).")
        return

    if in_place:
        if backup:
            shutil.copy2(bib, bib.with_suffix(bib.suffix + ".bak"))
        bib.write_text(text, encoding="utf-8")
        out = bib
    else:
        out = output or bib.with_suffix(".corrected.bib")
        out.write_text(text, encoding="utf-8")
    console.print(f"[green]Wrote {out}[/green] — applied [bold]{len(applied_findings)}[/bold] finding(s).")

    # Always write the audit report alongside the output.
    md_path = out.with_name("reference-audit.md")
    md_path.write_text(render_markdown_report(report), encoding="utf-8")
    json_path = out.with_name("reference-audit.json")
    json_path.write_text(render_json_report(report), encoding="utf-8")
    console.print(f"[dim]Reports: {md_path}, {json_path}[/dim]")


def _interactive_select(findings: list) -> list:
    accepted = []
    for f in findings:
        if f.confidence in ("verified", "high"):
            accepted.append(f)
            continue
        if f.confidence == "low" or f.suggested_value is None:
            continue
        # medium: prompt
        console.print(f"\n[bold]{f.entry_key}[/bold] — [yellow]{f.finding_type.value}[/yellow] (confidence: {f.confidence})")
        console.print(f"  before: {f.current_value}")
        console.print(f"  after:  {f.suggested_value}")
        console.print(f"  reason: {f.explanation}")
        try:
            resp = typer.prompt("Apply? [y/N]", default="n").lower()
        except EOFError:
            resp = "n"
        if resp.startswith("y"):
            accepted.append(f)
    return accepted


# ---------------------------------------------------------------------------
# `cpr verify`
# ---------------------------------------------------------------------------
@app.command()
def verify(
    bib: Annotated[Path, typer.Argument(exists=True, dir_okay=False, readable=True)],
    key: Annotated[str, typer.Argument()],
    no_network: Annotated[bool, typer.Option("--no-network")] = False,
    cache_dir: Annotated[Optional[Path], typer.Option("--cache-dir")] = None,
    verbose: Annotated[int, typer.Option("-v", "--verbose", count=True)] = 0,
):
    """Deep-dive one entry: show all evidence records + findings."""
    setup_logging(verbose)
    report, canonicals, entries = asyncio.run(_run_pipeline(bib, no_network, cache_dir))
    canon = canonicals.get(key)
    if canon is None:
        console.print(f"[red]No entry named `{key}` in {bib}[/red]")
        raise typer.Exit(2)
    console.print(f"[bold]@{key}[/bold]")
    console.print(f"Identity: DOI={canon.identity.doi!r}, arXiv={canon.identity.arxiv_id!r}")
    if not canon.evidence_records:
        console.print("[yellow]No evidence records retrieved.[/yellow]")
    for r in canon.evidence_records:
        console.print(f"  - [cyan]{r.source}[/cyan] tier {r.authority_tier}: {r.source_url}")
        if r.title:
            console.print(f"      title: {r.title}")
        if r.year:
            console.print(f"      year: {r.year}")
        if r.venue:
            console.print(f"      venue: {r.venue}")
        if r.pages:
            console.print(f"      pages: {r.pages}")
    findings = [f for f in report.findings if f.entry_key == key]
    if findings:
        console.print(f"\n[bold]{len(findings)} finding(s):[/bold]")
        for f in findings:
            console.print(f"  - {f.finding_type.value} ({f.confidence}) — {f.explanation}")


# ---------------------------------------------------------------------------
# `cpr explain`
# ---------------------------------------------------------------------------
@app.command()
def explain(
    bib: Annotated[Path, typer.Argument(exists=True, dir_okay=False, readable=True)],
    key: Annotated[str, typer.Argument()],
    no_network: Annotated[bool, typer.Option("--no-network")] = False,
    cache_dir: Annotated[Optional[Path], typer.Option("--cache-dir")] = None,
    verbose: Annotated[int, typer.Option("-v", "--verbose", count=True)] = 0,
):
    """Human-readable per-entry report."""
    setup_logging(verbose)
    report, canonicals, entries = asyncio.run(_run_pipeline(bib, no_network, cache_dir))
    entry = next((e for e in entries if e.key == key), None)
    if entry is None:
        console.print(f"[red]No entry named `{key}` in {bib}[/red]")
        raise typer.Exit(2)
    findings = [f for f in report.findings if f.entry_key == key]
    canon = canonicals.get(key)
    console.print(f"[bold]@{key}[/bold] — {entry.entry_type}")
    if entry.title:
        console.print(f"  title: {entry.title}")
    if entry.authors:
        console.print(f"  authors: {', '.join(a.formatted or a.raw for a in entry.authors)}")
    if entry.year:
        console.print(f"  year: {entry.year}")
    if canon and canon.evidence_records:
        sources = ", ".join(r.source for r in canon.evidence_records)
        console.print(f"  evidence sources: {sources}")
    if not findings:
        console.print("  [green]no findings[/green]")
        return
    console.print(f"  [bold]{len(findings)}[/bold] finding(s):")
    for f in findings:
        console.print(f"    - {f.finding_type.value} ({f.severity}, {f.confidence})")
        if f.suggested_value is not None:
            console.print(f"        suggest: {f.suggested_value}")
        console.print(f"        reason:  {f.explanation}")


if __name__ == "__main__":
    app()
