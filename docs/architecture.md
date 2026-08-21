# Architecture (Phase 1)

## Module map

```
backend/cpr/
├── cli.py            Typer app: check / fix / verify / explain
├── schemas.py        Pydantic models shared across all layers
│
├── bibtex/           Layer 1 — text ↔ typed entries
│   ├── parser.py     bibtexparser v2 → BibEntry
│   ├── writer.py     BibEntry → BibTeX text (key- and order-preserving)
│   ├── identity.py   BibEntry → PublicationIdentity (query keys)
│   └── names.py      Person-name parsing (initials, particles, Unicode)
│
├── providers/        Layer 2 — external evidence
│   ├── base.py       EvidenceProvider Protocol + EvidenceRecord
│   ├── cache.py      SQLite disk cache (~/.cache/cpr/cache.sqlite)
│   ├── crossref.py   api.crossref.org  (tier A)
│   ├── openreview.py api2.openreview.net (tier A)
│   ├── dblp.py       dblp.org/search/publ/api (tier B)
│   └── arxiv.py      export.arxiv.org/api/query (tier C)
│
├── resolver/         Layer 3 — evidence → canonical publication
│   ├── canonical.py  Merge EvidenceRecord list → CanonicalPublication
│   ├── conflicts.py  Named ConflictClass rules
│   └── confidence.py verified / high / medium / low policy
│
├── audit/            Layer 4 — canonical vs original → findings
│   ├── engine.py     Orchestrates all auditors
│   ├── findings.py   AuditFinding constructors
│   ├── metadata.py   Field-level (author/title/year/pages/doi/venue)
│   ├── entry_type.py @article vs @inproceedings mismatch
│   ├── arxiv_vs_formal.py FORMAL_PUBLICATION_AVAILABLE detection
│   ├── acm_pages.py  ACM article-number rule (positive evidence only)
│   └── duplicates.py DUPLICATE_PUBLICATION grouping
│
├── style/            Layer 5 — normalize output
│   ├── profile.py    StyleProfile Pydantic model
│   ├── loader.py     YAML loader (default: sjtu-ectl)
│   └── engine.py     Apply StyleProfile → corrected BibEntry
│
├── llm/              Layer 6 — ambiguity resolver (stub in MVP)
│   └── stub.py       Interface only; raises NotImplementedError
│
├── report/           Layer 7 — human + machine output
│   ├── markdown.py   reference-audit.md
│   └── json_report.py reference-audit.json
│
└── util/
    ├── unicode.py    NFC + LaTeX ↔ Unicode
    └── logging.py    Structured explanations
```

## Dataflow

```
references.bib
    │
    ▼   bibtex.parser
BibEntry[]
    │
    ▼   bibtex.identity
PublicationIdentity[]      ── DOI, arXiv id, or (title,authors,year)
    │
    ▼   providers.* (parallel, cached under ~/.cache/cpr/)
EvidenceRecord[]           ── from Crossref, DBLP, arXiv, OpenReview
    │
    ▼   resolver.canonical + resolver.conflicts + resolver.confidence
CanonicalPublication[]     ── per-field {value, evidence[], conflict?}
    │
    ▼   audit.engine
AuditFinding[]             ── typed, severity, confidence, evidence
    │
    ▼   style.engine          (gated by confidence ∈ {verified, high})
CorrectedBibEntry[]
    │
    ├── bibtex.writer  → references.corrected.bib
    └── report.*       → reference-audit.md + reference-audit.json
```

## Extension points

| Add | Where |
|-----|-------|
| A new evidence provider          | `backend/cpr/providers/` implementing `EvidenceProvider` |
| A new audit rule                 | `backend/cpr/audit/` + register in `engine.py` |
| A new conflict class             | `backend/cpr/resolver/conflicts.py` |
| A new style profile              | Add YAML in `configs/` + reference by name |
| A new report format              | `backend/cpr/report/` |
| An LLM ambiguity resolver        | Replace `llm/stub.py` with concrete implementation |

## Async model

Provider fetches run under a single `asyncio` event loop invoked by the
Typer CLI. All I/O is `httpx.AsyncClient`. The SQLite cache uses
synchronous access inside an executor thread (small and short) — this is
fine for MVP; a future migration to `aiosqlite` is trivial.
