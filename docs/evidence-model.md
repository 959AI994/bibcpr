# Evidence model

## Tenets

1. **Every field-level fact carries provenance.** A value without an
   `EvidenceClaim` is not a fact — it is a *belief inherited from the
   input `.bib`* and is preserved unchanged.
2. **Authoritative sources outrank convenient ones.** DOI-registrar
   records (Crossref) and program-committee records (OpenReview)
   outrank aggregators (DBLP), which outrank preprint servers (arXiv),
   which outrank web search.
3. **Conflicts are named, not averaged.** A disagreement between
   Crossref and DBLP is a `ConflictClass` with an explicit resolution
   rule — never a majority vote.

## Authority tiers (§6)

| Tier | Sources                                                    | Notes |
|------|------------------------------------------------------------|-------|
| A    | Crossref (DOI registrar), OpenReview program record        | Highest. |
| B    | DBLP, ACM DL, IEEE Xplore, PMLR, ACL Anthology             | Publisher aggregators. Phase 1 ships DBLP only. |
| C    | arXiv metadata, semantic-scholar summaries                 | Useful for identity, not for canonical venue. |
| D    | Web search results                                         | Phase 2. |

## `EvidenceClaim`

```python
class EvidenceClaim:
    field: str                                 # "title", "year", "authors", ...
    value: Any
    source: Literal["Crossref","DBLP","arXiv","OpenReview"]
    source_url: str
    authority_tier: Literal["A","B","C","D"]
    retrieved_at: datetime
```

## `CanonicalField[T]`

```python
class CanonicalField[T]:
    value: T | None
    evidence: list[EvidenceClaim]
    conflict: ConflictClass | None
```

- `value` is set only when at least one `EvidenceClaim` supports it.
- If two sources disagree, `conflict` is set and `value` is chosen by
  the conflict class rule (typically: prefer highest tier).

## Confidence policy (§24)

| Confidence | Definition                                                     | Auto-fix? |
|------------|----------------------------------------------------------------|-----------|
| verified   | ≥2 sources from tier A or B agree                              | Yes       |
| high       | Exactly one tier-A source, no contradiction                    | Yes       |
| medium     | Exactly one tier-B source, or resolved A/B conflict            | Only with `--interactive` |
| low        | Only tier-C source, or unresolved contradiction                | Never — reported only |

## Named conflict classes (§8)

| Class                                | Trigger | Rule |
|--------------------------------------|---------|------|
| `online_vs_issue_year`               | Crossref reports different `published-online` vs `published-print` year | Prefer `published-print` (journal issue year) unless entry_type=@online. |
| `arxiv_vs_formal_publication`        | arXiv record exists AND DBLP/Crossref record for a formally-published version exists | Prefer the formal record; raise `FORMAL_PUBLICATION_AVAILABLE`. |
| `ieee_pages_vs_acm_article_number`   | Publisher indicates ACM article-numbering (pages "N:1--N:M") but original entry has `1--N` | Rewrite pages only if positive ACM/DBLP evidence exists. |

## The no-hallucination invariant

> For any `AuditFinding` where `len(evidence) == 0`,
> `suggested_value == current_value`.

This is enforced by a test in `tests/test_audit_engine.py` that runs
across all cases. Any bug that produces a suggestion without evidence
fails the whole suite.
