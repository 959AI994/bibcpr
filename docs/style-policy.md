# Style policy (§18) and the `sjtu-ectl` profile (§40)

A `StyleProfile` is a Pydantic model loaded from YAML that controls how
`CanonicalPublication` + original `BibEntry` are rendered back into
BibTeX.

## Profile schema

```yaml
name: sjtu-ectl
version: 1

citation_key:
  strategy: preserve          # preserve | regenerate
  # If regenerate, the format is:
  format: "{first_author_family}{year}{first_title_word}"

publication:
  prefer_formal_over_preprint: true    # §10
  demote_preprint_when_formal_available: true
  keep_arxiv_eprint_field: true        # keep as auxiliary reference

authors:
  format: "family, given"              # "Qian, Weikang"
  join: " and "
  abbreviate_given: false              # true → "W."
  hyphenated_initials_join: "-"        # "Pai-Shun" → "P.-S." when abbreviated

pages:
  article_number_prefix: null          # e.g. "Article " → "Article 42:1--42:23"
  double_hyphen: true                  # "1--10" not "1-10"

fields:
  # Order applied by the writer. Fields absent here are appended in original order.
  order:
    - author
    - title
    - booktitle
    - journal
    - year
    - volume
    - number
    - pages
    - publisher
    - doi
    - url
    - eprint
    - archivePrefix
    - primaryClass
  drop_if_empty:
    - abstract
    - keywords
    - note

unicode:
  strategy: preserve                   # preserve | latex_escape
  # If latex_escape, transliterate accents to LaTeX (e.g., ü → \"{u})
```

## `sjtu-ectl` default (Phase 1)

The default profile is a conservative, key-preserving profile intended
for the lab at SJTU ECTL that motivated this project. It:

- **Preserves citation keys** to keep existing `\cite{}` calls stable.
- **Prefers the formal publication** over the arXiv preprint when both
  exist and evidence agrees.
- **Keeps `eprint` / `archivePrefix` / `primaryClass`** as auxiliary
  fields when demoting an `@article`(arXiv) to `@inproceedings`(conf).
- **Uses `family, given` full names** joined by ` and `.
- **Does not** rewrite pages `1--N` to ACM `N:1--N:M` unless positive
  publisher evidence is available (§9).
- **Preserves Unicode** in author family names (NFC-normalized).

The full YAML lives at [`configs/sjtu-ectl.yaml`](../configs/sjtu-ectl.yaml).

## Confidence gate

The style engine only rewrites a field when the responsible
`AuditFinding` has `confidence ∈ {verified, high}`. Medium/low
findings are reported but never applied unless the user passes
`--interactive` (medium) — never for low.
