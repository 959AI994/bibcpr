# bibcpr — Correct Paper Reference

> **Evidence first, LLM second — never hallucinate metadata.**

`bibcpr` is an auditing / verification / repair agent for BibTeX
bibliographies. It reads your `references.bib`, retrieves authoritative
metadata from Crossref, DBLP, arXiv and OpenReview, detects factual errors
and formatting issues, and produces a corrected `.bib` plus a Markdown
audit report — with every non-trivial change backed by evidence and a
confidence label.

The command-line entry point is `cpr` (short for **C**orrect **P**aper
**R**eference); the distribution / repo name is `bibcpr` to avoid
collision with unrelated `cpr` packages.

- Repository: <https://github.com/959AI994/bibcpr>
- Contact: Jingxin Wang · <jingxin.wang@sjtu.edu.cn>

## Status

**Phase 1 CLI MVP** (see [`docs/roadmap.md`](docs/roadmap.md)).

Later phases add publisher-page verifiers, LaTeX-aware semantic citation
audit, an MCP server + Skill, a browser extension for Overleaf, and a
hosted web app.

## Install

```bash
git clone https://github.com/959AI994/bibcpr.git
cd bibcpr

# recommended: use uv with Python 3.12
uv venv --python 3.12 .venv
uv pip install --python .venv/bin/python -e ".[dev]"
# or plain pip:
pip install -e ".[dev]"
```

Requires Python 3.12+.

## Quick start

```bash
# Read-only audit (no writes)
cpr check ./references.bib

# Machine-readable report
cpr check ./references.bib --json audit.json --report audit.md

# Auto-apply verified + high-confidence fixes
cpr fix ./references.bib --output ./references.corrected.bib

# Prompt per finding
cpr fix ./references.bib --interactive

# Deep-dive one entry
cpr verify ./references.bib chen2024attention
cpr explain ./references.bib chen2024attention
```

Global flags: `--no-network`, `--cache-dir`, `--config`, `--profile sjtu-ectl`, `-v`, `-vv`.

## Web UI (desktop-style, local-only)

`bibcpr` ships with a small local web app so anyone can drag-drop a
`.bib` file and review findings visually — no terminal required after
install.

```bash
cpr serve
# → serving on http://127.0.0.1:8765
# → browser opens automatically
```

The UI:

- Drag-drop or paste a `.bib` file
- Live audit against Crossref / DBLP / arXiv / OpenReview
- Filter findings by type (venue_mismatch, author_mismatch, …)
- Expand any finding to see **before / after / reason / evidence URLs**
- Accept or reject each finding individually (verified + high are
  pre-checked; medium requires your decision; low is never
  auto-checked)
- One-click download of `corrected.bib`, `audit.md`, `audit.json`
- Per-entry inline diff view

The server binds to `127.0.0.1` by default — **your bibliography
never leaves your machine.** Use `--host 0.0.0.0` to expose it (and
be aware of the privacy implications).

Extra flags:

```bash
cpr serve --port 9000            # different port
cpr serve --no-open              # don't auto-open the browser
```

## Core promise

1. Every field in a `CanonicalPublication` carries a list of
   `EvidenceClaim`s. Empty evidence → the field is *unverified* and the
   original value is preserved untouched.
2. Auto-fix is only applied when confidence is **verified** or **high**.
   Medium requires `--interactive`; low is never modified.
3. Citation keys are preserved by default — reformatting a bibliography
   never breaks `\cite{}` calls in your `.tex` files.

## Layout

```
backend/cpr/       Python package (parser, providers, resolver, audit, style, CLI)
backend/cpr/webapp/ Local FastAPI web UI (cpr serve)
configs/           YAML style profiles (default: sjtu-ectl)
docs/              Architecture, evidence model, style policy, roadmap
skills/            Agent-facing Skill scaffold
tests/             Offline unit tests + 10 golden BibTeX cases + webapp tests
benchmark/         §45 baseline metrics
apps/, packages/   Stubs for later phases
```

## License

MIT. See [`LICENSE`](LICENSE).

## Citation & contact

If `bibcpr` helps you clean up a paper's bibliography, please open an
issue or drop me a note.

- Maintainer: **Jingxin Wang** — <jingxin.wang@sjtu.edu.cn>
- Issues / PRs: <https://github.com/959AI994/bibcpr/issues>
