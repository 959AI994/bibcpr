# CPR benchmark

`cases.jsonl` seeds the §45 baseline. Each row is one of §44's ten
canonical failure modes. Phase 1 does not require the benchmark to
pass automatically — it exists to capture metrics against which
Phase 2 and later improvements can be measured.

Metrics of interest (to be computed in Phase 2):

- **Precision:** fraction of auto-applied fixes that a human agrees
  with.
- **Recall:** fraction of intended fixes actually auto-applied.
- **Evidence coverage:** fraction of entries for which at least one
  tier-A source was retrieved.
- **Confidence calibration:** for each confidence bucket, agreement
  rate with human reviewers.

Runtime target: `< 200ms/entry` amortized with a warm cache.
