"""Merge EvidenceRecords → CanonicalPublication with per-field provenance."""
from __future__ import annotations

from typing import Any

from ..schemas import (
    Author,
    CanonicalField,
    CanonicalPublication,
    ConflictClass,
    EvidenceClaim,
    EvidenceRecord,
    PublicationIdentity,
)
from .conflicts import detect_conflicts


# Priority order for choosing a value when multiple sources agree:
_TIER_RANK = {"A": 3, "B": 2, "C": 1, "D": 0}


def _pick_best(values: list[tuple[Any, EvidenceRecord]]) -> tuple[Any, list[EvidenceRecord]]:
    """Return the highest-tier value + the list of records that support it."""
    if not values:
        return None, []
    # Rank each candidate by tier
    values_by_tier = sorted(values, key=lambda vr: -_TIER_RANK[vr[1].authority_tier])
    top = values_by_tier[0][0]
    supporting = [rec for v, rec in values if _same_value(v, top)]
    return top, supporting


def _same_value(a: Any, b: Any) -> bool:
    if a == b:
        return True
    if isinstance(a, str) and isinstance(b, str):
        return a.strip().lower().rstrip(".") == b.strip().lower().rstrip(".")
    return False


def _make_field(
    values: list[tuple[Any, EvidenceRecord]],
    conflict: ConflictClass | None = None,
    forced_value: Any = None,
) -> CanonicalField:
    if forced_value is not None:
        supporting = [rec for v, rec in values if _same_value(v, forced_value)]
        claims = [
            EvidenceClaim(
                field="",
                value=forced_value,
                source=rec.source,
                source_url=rec.source_url,
                authority_tier=rec.authority_tier,
                retrieved_at=rec.retrieved_at,
            )
            for rec in supporting
        ]
        return CanonicalField(value=forced_value, evidence=claims, conflict=conflict)

    value, supporting = _pick_best(values)
    claims = [
        EvidenceClaim(
            field="",
            value=value,
            source=rec.source,
            source_url=rec.source_url,
            authority_tier=rec.authority_tier,
            retrieved_at=rec.retrieved_at,
        )
        for rec in supporting
    ]
    return CanonicalField(value=value, evidence=claims, conflict=conflict)


def _collect(records: list[EvidenceRecord], attr: str) -> list[tuple[Any, EvidenceRecord]]:
    out: list[tuple[Any, EvidenceRecord]] = []
    for r in records:
        v = getattr(r, attr, None)
        if v is None or v == "" or v == []:
            continue
        out.append((v, r))
    return out


def _authors_equal(a: list[Author], b: list[Author]) -> bool:
    if len(a) != len(b):
        return False
    for x, y in zip(a, b):
        if (x.family or "").strip().lower() != (y.family or "").strip().lower():
            return False
    return True


def _pick_authors(records: list[EvidenceRecord]) -> CanonicalField[list[Author]]:
    candidates = [(r.authors, r) for r in records if r.authors]
    if not candidates:
        return CanonicalField[list[Author]](value=None, evidence=[])
    candidates_sorted = sorted(candidates, key=lambda vr: -_TIER_RANK[vr[1].authority_tier])
    top = candidates_sorted[0][0]
    supporting = [rec for v, rec in candidates if _authors_equal(v, top)]
    claims = [
        EvidenceClaim(
            field="authors",
            value=[a.model_dump() for a in top],
            source=rec.source,
            source_url=rec.source_url,
            authority_tier=rec.authority_tier,
            retrieved_at=rec.retrieved_at,
        )
        for rec in supporting
    ]
    return CanonicalField[list[Author]](value=top, evidence=claims)


def build_canonical(
    identity: PublicationIdentity, records: list[EvidenceRecord]
) -> CanonicalPublication:
    """Merge multiple provider records into one canonical view."""
    conflicts = detect_conflicts(records)

    forced: dict[str, Any] = {field: cls_val[1] for field, cls_val in conflicts.items() if cls_val[1] is not None}
    conflict_cls: dict[str, ConflictClass | None] = {field: cls_val[0] for field, cls_val in conflicts.items()}

    canon = CanonicalPublication(
        identity=identity,
        title=_make_field(_collect(records, "title"), conflict_cls.get("title")),
        authors=_pick_authors(records),
        year=_make_field(
            _collect(records, "year"),
            conflict_cls.get("year"),
            forced.get("year"),
        ),
        venue=_make_field(
            _collect(records, "venue"),
            conflict_cls.get("venue"),
            forced.get("venue"),
        ),
        volume=_make_field(_collect(records, "volume")),
        number=_make_field(_collect(records, "number")),
        pages=_make_field(
            _collect(records, "pages"),
            conflict_cls.get("pages"),
            # ACM article-number needs positive evidence — DON'T force here;
            # let the auditor decide with its confidence rules.
            None,
        ),
        doi=_make_field(_collect(records, "doi")),
        entry_type=_make_field(_collect(records, "entry_type")),
        publisher=_make_field(_collect(records, "publisher")),
        arxiv_id=next((r.arxiv_id for r in records if r.arxiv_id), None),
        formal_publication_available=any(r.formal_publication_available for r in records)
            or any(r.source in ("Crossref", "DBLP", "OpenReview") for r in records),
        evidence_records=list(records),
    )
    # Set the field name on each claim.
    for name in ("title", "authors", "year", "venue", "volume", "number", "pages", "doi", "entry_type", "publisher"):
        cf: CanonicalField = getattr(canon, name)
        for c in cf.evidence:
            c.field = name
    return canon
