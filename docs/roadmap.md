# Roadmap

CPR is being built in six phases. **Phase 1 is the CLI MVP shipped in
this repository today.** Phases 2–6 are enumerated with acceptance
criteria so that future sessions can pick up cleanly.

## Phase 1 — CLI MVP  ✅ (current)

- `cpr check` / `cpr fix` / `cpr verify` / `cpr explain`
- BibTeX parser (bibtexparser v2) with citation-key preservation
- Providers: Crossref, DBLP, arXiv, OpenReview
- SQLite disk cache under `~/.cache/cpr/`
- Resolver with named `ConflictClass` rules
- Audit engine covering 7 finding types (§23 subset)
- Default `sjtu-ectl` style profile
- LLM interface (stub only)
- Offline test suite with 10 golden BibTeX cases (§44)

**Definition of Done (§49):** all 12 bullets pass.

## Phase 2 — Deep verification

- Publisher-page evidence: ACM DL, IEEE Xplore, Springer, PMLR, ACL Anthology
- Web-search providers: Exa / Tavily / Brave / Serper
- Real LLM ambiguity resolver replacing `llm/stub.py`
- ACM article-number heuristic wired to positive ACM DL / DBLP evidence
- Expanded conflict classes: `venue_abbreviation_expansion`,
  `series_vs_journal`, `preprint_version_mismatch`

**Acceptance:** ≥ 90 % of §45 benchmark cases resolved verified/high;
zero false-positive fixes.

## Phase 3 — LaTeX-aware semantic citation audit

- `\cite{}` extraction from `.tex` sources
- Cross-check that the claim on the citing line is supported by the
  cited paper's abstract/results
- New finding types: `WRONG_PAPER_CITED`, `CLAIM_NOT_SUPPORTED_BY_SOURCE`
- `cpr audit ./paper-project/` project mode (§2)

**Acceptance:** flags at least 3 of the 10 §44 cases whose semantic
error is not detectable from BibTeX alone.

## Phase 4 — Agent surface

- MCP server exposing check/fix/verify tools (§30)
- Full Skill file `skills/correct-paper-reference/SKILL.md` wired for
  Claude Code, Cursor, and Gemini CLI (§31)
- Structured explanations flow through the MCP interface

**Acceptance:** an agent can call CPR via MCP and receive structured
findings with evidence.

## Phase 5 — Browser extension

- Overleaf adapter (§29)
- Side-panel UI that overlays audit findings on the editor
- Local backend or remote API

**Acceptance:** in-Overleaf demo of `cpr check` producing findings on
the currently open `.bib`.

## Phase 6 — Web app + hosted service

- React + Vite + Tailwind front-end (§33, §42)
- Hosted backend with accounts, quotas, private cache
- Team style profiles

**Acceptance:** `curl https://…/api/v1/check` returns identical JSON
to the CLI, subject to auth.
