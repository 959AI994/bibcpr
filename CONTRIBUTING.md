# Contributing

## Development setup

```bash
uv pip install -e ".[dev]"
pytest -q
```

Python 3.12+ is required. All development happens against real HTTP APIs
gated by a persistent SQLite cache under `~/.cache/cpr/`; unit tests use
recorded fixtures under `tests/fixtures/`.

## Design tenets

1. **Evidence first.** Every metadata change carries `{before, after,
   reason, evidence, confidence}`. Auto-fix requires
   `confidence ∈ {verified, high}`. See `docs/evidence-model.md`.
2. **Preserve citation keys.** Reformatting must not break `\cite{}`.
3. **Conflicts are typed, not voted on.** New conflict classes live in
   `backend/cpr/resolver/conflicts.py`.
4. **No hallucination.** If evidence is empty, the field is
   `unverified` and the original value is preserved.

## Adding a provider

1. Implement `EvidenceProvider` from `backend/cpr/providers/base.py`.
2. Register in `backend/cpr/providers/__init__.py`.
3. Add fixtures under `tests/fixtures/<provider>/`.
4. Add a `test_providers.py::test_<provider>_fixture` case.

## Adding an audit rule

1. Add the finding to `FindingType` in `backend/cpr/schemas.py`.
2. Add the auditor module under `backend/cpr/audit/`.
3. Register it in `backend/cpr/audit/engine.py`.
4. Add golden cases under `tests/bibs/` + `tests/bibs/expected/`.

## Tests

- `pytest tests/ -q` must pass offline. Any test hitting the network is a bug.
- Golden regressions in `tests/bibs/` are byte-diffed against
  `tests/bibs/expected/`.
- Invariant tests enforce §0 (no hallucination) and §18 (key
  preservation) across all cases.
