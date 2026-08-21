"""Publication identity: mapping BibEntry → PublicationIdentity for providers."""
from __future__ import annotations

import re
import unicodedata

from ..schemas import BibEntry, PublicationIdentity


_DOI_RE = re.compile(r"10\.\d{4,9}/[-._;()/:A-Z0-9]+", re.IGNORECASE)
_ARXIV_ID_RE = re.compile(
    r"(?:arxiv[:\s/])?"
    r"(?P<id>\d{4}\.\d{4,5}(?:v\d+)?|[a-z\-]+(?:\.[A-Z]{2})?/\d{7}(?:v\d+)?)",
    re.IGNORECASE,
)
_OPENREVIEW_RE = re.compile(
    r"openreview\.net/(?:pdf|forum|attachment)\?id=(?P<id>[A-Za-z0-9\-]+)",
    re.IGNORECASE,
)


def normalize_title(title: str) -> str:
    """Aggressive title normalization for identity matching.

    - NFC-normalize
    - Lowercase
    - Strip LaTeX braces / dollar-math shells
    - Collapse whitespace and punctuation
    """
    if not title:
        return ""
    t = unicodedata.normalize("NFC", title)
    # Strip LaTeX commands like \emph{...} → the content
    t = re.sub(r"\\[a-zA-Z]+\s*\{([^}]*)\}", r"\1", t)
    # Strip braces
    t = re.sub(r"[{}]", "", t)
    # Strip dollar-math delimiters
    t = re.sub(r"\$([^$]*)\$", r"\1", t)
    # Lowercase
    t = t.lower()
    # Replace punctuation with spaces
    t = re.sub(r"[^\w\s]", " ", t, flags=re.UNICODE)
    # Collapse whitespace
    t = re.sub(r"\s+", " ", t).strip()
    return t


def _extract_doi(entry: BibEntry) -> str | None:
    if entry.doi:
        m = _DOI_RE.search(entry.doi)
        if m:
            return m.group(0).lower()
        return entry.doi.strip().lower() or None
    if entry.url:
        m = _DOI_RE.search(entry.url)
        if m:
            return m.group(0).lower()
    return None


def _extract_arxiv_id(entry: BibEntry) -> str | None:
    if entry.eprint:
        v = entry.eprint.strip()
        m = _ARXIV_ID_RE.search(v)
        if m:
            return m.group("id")
    for candidate in (entry.url, entry.note, entry.journal, entry.booktitle):
        if not candidate:
            continue
        if "arxiv" in candidate.lower():
            m = _ARXIV_ID_RE.search(candidate)
            if m:
                return m.group("id")
    return None


def _extract_openreview_id(entry: BibEntry) -> str | None:
    for candidate in (entry.url, entry.note):
        if not candidate:
            continue
        m = _OPENREVIEW_RE.search(candidate)
        if m:
            return m.group("id")
    return None


def _first_author_family(entry: BibEntry) -> str | None:
    if not entry.authors:
        return None
    return entry.authors[0].family or None


def extract_identity(entry: BibEntry) -> PublicationIdentity:
    """Compute a `PublicationIdentity` for one BibEntry."""
    return PublicationIdentity(
        doi=_extract_doi(entry),
        arxiv_id=_extract_arxiv_id(entry),
        openreview_id=_extract_openreview_id(entry),
        title_normalized=normalize_title(entry.title) if entry.title else None,
        first_author_family=_first_author_family(entry),
        year=entry.year,
    )
