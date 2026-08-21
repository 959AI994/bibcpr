"""Core Pydantic models shared across all layers.

Every layer speaks in terms of these types. If you want to change the
shape of data flowing through CPR, this is where you start.
"""
from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Generic, Literal, TypeVar

from pydantic import BaseModel, ConfigDict, Field

T = TypeVar("T")

AuthorityTier = Literal["A", "B", "C", "D"]
Severity = Literal["info", "warning", "error", "critical"]
Confidence = Literal["low", "medium", "high", "verified"]
EntryType = Literal[
    "article",
    "inproceedings",
    "incollection",
    "book",
    "phdthesis",
    "mastersthesis",
    "techreport",
    "misc",
    "software",
    "online",
    "proceedings",
    "unpublished",
    "booklet",
    "manual",
]


# ---------------------------------------------------------------------------
# Names
# ---------------------------------------------------------------------------
class Author(BaseModel):
    """A parsed author name.

    `raw` is what was in the source .bib; `formatted` is what the writer
    should emit when we haven't changed the identity. When we *have*
    identified this author against evidence, `family` + `given` are
    canonical.
    """
    model_config = ConfigDict(frozen=False)

    given: list[str] = Field(default_factory=list)
    family: str = ""
    particles: list[str] = Field(default_factory=list)  # de / van / der / von
    suffix: str = ""                                     # Jr., III
    raw: str = ""
    formatted: str = ""

    def display(self) -> str:
        parts: list[str] = []
        if self.given:
            parts.append(" ".join(self.given))
        if self.particles:
            parts.append(" ".join(self.particles))
        if self.family:
            parts.append(self.family)
        if self.suffix:
            parts.append(self.suffix)
        return " ".join(p for p in parts if p)


# ---------------------------------------------------------------------------
# Source position (for diff generation)
# ---------------------------------------------------------------------------
class SourcePosition(BaseModel):
    line_start: int
    line_end: int


# ---------------------------------------------------------------------------
# BibEntry — a single parsed entry
# ---------------------------------------------------------------------------
class BibEntry(BaseModel):
    """A single BibTeX entry, parsed."""
    model_config = ConfigDict(frozen=False)

    key: str
    entry_type: str  # normalized lowercase; validated against EntryType at boundaries
    title: str | None = None
    authors: list[Author] = Field(default_factory=list)
    editors: list[Author] = Field(default_factory=list)
    journal: str | None = None
    booktitle: str | None = None
    year: int | None = None
    month: str | None = None
    volume: str | None = None
    number: str | None = None
    pages: str | None = None
    doi: str | None = None
    url: str | None = None
    eprint: str | None = None
    archive_prefix: str | None = None      # "arXiv"
    primary_class: str | None = None       # "cs.LG"
    publisher: str | None = None
    organization: str | None = None
    address: str | None = None
    series: str | None = None
    edition: str | None = None
    isbn: str | None = None
    issn: str | None = None
    note: str | None = None
    # Any field we don't otherwise recognize.
    raw_fields: dict[str, str] = Field(default_factory=dict)
    # Preserve original field-order for round-trip fidelity.
    field_order: list[str] = Field(default_factory=list)
    source_position: SourcePosition | None = None

    def get(self, field: str) -> Any:
        """Read a field by BibTeX field-name."""
        mapping = {
            "author": self.authors,
            "editor": self.editors,
            "archiveprefix": self.archive_prefix,
            "primaryclass": self.primary_class,
        }
        norm = field.lower()
        if norm in mapping:
            return mapping[norm]
        if hasattr(self, norm):
            return getattr(self, norm)
        return self.raw_fields.get(field) or self.raw_fields.get(norm)


# ---------------------------------------------------------------------------
# Publication identity — query key for providers
# ---------------------------------------------------------------------------
class PublicationIdentity(BaseModel):
    """A stable key for looking up a publication in evidence providers."""
    doi: str | None = None
    arxiv_id: str | None = None
    openreview_id: str | None = None
    title_normalized: str | None = None
    first_author_family: str | None = None
    year: int | None = None

    def has_strong_id(self) -> bool:
        return bool(self.doi or self.arxiv_id or self.openreview_id)


# ---------------------------------------------------------------------------
# Evidence
# ---------------------------------------------------------------------------
class EvidenceClaim(BaseModel):
    """A single (field, value) fact attested by an external source."""
    field: str
    value: Any
    source: Literal["Crossref", "DBLP", "arXiv", "OpenReview"]
    source_url: str
    authority_tier: AuthorityTier
    retrieved_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class EvidenceRecord(BaseModel):
    """One provider's complete record for one publication identity."""
    identity: PublicationIdentity
    source: Literal["Crossref", "DBLP", "arXiv", "OpenReview"]
    source_url: str
    authority_tier: AuthorityTier
    retrieved_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    # Parsed fields
    title: str | None = None
    authors: list[Author] = Field(default_factory=list)
    year: int | None = None
    venue: str | None = None            # journal or booktitle
    volume: str | None = None
    number: str | None = None
    pages: str | None = None
    doi: str | None = None
    entry_type: str | None = None       # provider's opinion on @article/@inproceedings
    publisher: str | None = None
    arxiv_id: str | None = None
    formal_publication_available: bool = False  # arXiv: set true if DOI is registered

    def to_claims(self) -> list[EvidenceClaim]:
        """Explode this record into per-field EvidenceClaim rows."""
        out: list[EvidenceClaim] = []
        common = dict(
            source=self.source,
            source_url=self.source_url,
            authority_tier=self.authority_tier,
            retrieved_at=self.retrieved_at,
        )
        if self.title is not None:
            out.append(EvidenceClaim(field="title", value=self.title, **common))
        if self.authors:
            out.append(EvidenceClaim(field="authors", value=[a.model_dump() for a in self.authors], **common))
        if self.year is not None:
            out.append(EvidenceClaim(field="year", value=self.year, **common))
        if self.venue is not None:
            out.append(EvidenceClaim(field="venue", value=self.venue, **common))
        if self.volume is not None:
            out.append(EvidenceClaim(field="volume", value=self.volume, **common))
        if self.number is not None:
            out.append(EvidenceClaim(field="number", value=self.number, **common))
        if self.pages is not None:
            out.append(EvidenceClaim(field="pages", value=self.pages, **common))
        if self.doi is not None:
            out.append(EvidenceClaim(field="doi", value=self.doi, **common))
        if self.entry_type is not None:
            out.append(EvidenceClaim(field="entry_type", value=self.entry_type, **common))
        if self.publisher is not None:
            out.append(EvidenceClaim(field="publisher", value=self.publisher, **common))
        return out


# ---------------------------------------------------------------------------
# Conflicts
# ---------------------------------------------------------------------------
class ConflictClass(str, Enum):
    ONLINE_VS_ISSUE_YEAR = "online_vs_issue_year"
    ARXIV_VS_FORMAL_PUBLICATION = "arxiv_vs_formal_publication"
    IEEE_PAGES_VS_ACM_ARTICLE_NUMBER = "ieee_pages_vs_acm_article_number"
    VENUE_ABBREVIATION_MISMATCH = "venue_abbreviation_mismatch"
    AUTHOR_ORDER_MISMATCH = "author_order_mismatch"
    UNRESOLVED = "unresolved"


class CanonicalField(BaseModel, Generic[T]):
    """A canonical field with provenance."""
    value: T | None = None
    evidence: list[EvidenceClaim] = Field(default_factory=list)
    conflict: ConflictClass | None = None

    def is_verified(self) -> bool:
        return self.value is not None and len(self.evidence) > 0


# ---------------------------------------------------------------------------
# Canonical publication
# ---------------------------------------------------------------------------
class CanonicalPublication(BaseModel):
    """The merged, evidence-backed view of a publication."""
    identity: PublicationIdentity
    title: CanonicalField[str] = Field(default_factory=lambda: CanonicalField[str]())
    authors: CanonicalField[list[Author]] = Field(default_factory=lambda: CanonicalField[list[Author]]())
    year: CanonicalField[int] = Field(default_factory=lambda: CanonicalField[int]())
    venue: CanonicalField[str] = Field(default_factory=lambda: CanonicalField[str]())
    volume: CanonicalField[str] = Field(default_factory=lambda: CanonicalField[str]())
    number: CanonicalField[str] = Field(default_factory=lambda: CanonicalField[str]())
    pages: CanonicalField[str] = Field(default_factory=lambda: CanonicalField[str]())
    doi: CanonicalField[str] = Field(default_factory=lambda: CanonicalField[str]())
    entry_type: CanonicalField[str] = Field(default_factory=lambda: CanonicalField[str]())
    publisher: CanonicalField[str] = Field(default_factory=lambda: CanonicalField[str]())

    # Auxiliary evidence-derived facts
    arxiv_id: str | None = None
    formal_publication_available: bool = False
    evidence_records: list[EvidenceRecord] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Findings
# ---------------------------------------------------------------------------
def _jsonable(v: Any) -> Any:
    """Coerce Pydantic models / lists thereof into plain-Python for JSON."""
    if v is None:
        return None
    if isinstance(v, BaseModel):
        return v.model_dump(mode="json")
    if isinstance(v, list):
        return [_jsonable(x) for x in v]
    if isinstance(v, dict):
        return {k: _jsonable(val) for k, val in v.items()}
    return v


class FindingType(str, Enum):
    # §23 finding taxonomy
    MISSING_REQUIRED_FIELD = "missing_required_field"
    AUTHOR_MISMATCH = "author_mismatch"
    TITLE_MISMATCH = "title_mismatch"
    YEAR_MISMATCH = "year_mismatch"
    VENUE_MISMATCH = "venue_mismatch"
    PAGES_MISMATCH = "pages_mismatch"
    DOI_MISMATCH = "doi_mismatch"
    DOI_MISSING = "doi_missing"
    ENTRY_TYPE_MISMATCH = "entry_type_mismatch"
    FORMAL_PUBLICATION_AVAILABLE = "formal_publication_available"
    ACM_ARTICLE_NUMBER_SUGGESTED = "acm_article_number_suggested"
    DUPLICATE_PUBLICATION = "duplicate_publication"
    INSTITUTION_AS_AUTHOR = "institution_as_author"
    UNVERIFIED_ENTRY = "unverified_entry"
    UNICODE_NORMALIZATION = "unicode_normalization"
    UNRESOLVED_CONFLICT = "unresolved_conflict"


class AuditFinding(BaseModel):
    """A single audit result attached to a BibEntry."""
    entry_key: str
    finding_type: FindingType
    severity: Severity
    confidence: Confidence
    field: str | None = None
    current_value: Any = None
    suggested_value: Any = None
    explanation: str = ""
    evidence: list[EvidenceClaim] = Field(default_factory=list)
    conflict: ConflictClass | None = None

    def is_auto_fixable(self) -> bool:
        """Auto-fix policy per §24."""
        return self.confidence in ("verified", "high") and self.suggested_value is not None

    def to_report_dict(self) -> dict[str, Any]:
        """Emit §46 payload: before/after/reason/evidence/confidence."""
        return {
            "entry_key": self.entry_key,
            "finding_type": self.finding_type.value,
            "severity": self.severity,
            "confidence": self.confidence,
            "field": self.field,
            "before": _jsonable(self.current_value),
            "after": _jsonable(self.suggested_value),
            "reason": self.explanation,
            "evidence": [c.model_dump(mode="json") for c in self.evidence],
            "conflict": self.conflict.value if self.conflict else None,
        }


# ---------------------------------------------------------------------------
# Provider search interface
# ---------------------------------------------------------------------------
class SearchQuery(BaseModel):
    title: str | None = None
    first_author_family: str | None = None
    year: int | None = None
    doi: str | None = None
    arxiv_id: str | None = None


class SearchResult(BaseModel):
    identity: PublicationIdentity
    score: float
    record: EvidenceRecord


# ---------------------------------------------------------------------------
# Audit report envelope
# ---------------------------------------------------------------------------
class AuditReport(BaseModel):
    input_path: str
    entries_total: int
    entries_with_findings: int
    findings: list[AuditFinding]
    generated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    def summary(self) -> dict[str, int]:
        counts: dict[str, int] = {}
        for f in self.findings:
            counts[f.finding_type.value] = counts.get(f.finding_type.value, 0) + 1
        return counts
