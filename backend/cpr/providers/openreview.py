"""OpenReview provider (API v2).

Docs: https://docs.openreview.net/
- GET https://api2.openreview.net/notes?id=... : one submission
- GET https://api2.openreview.net/notes?content.title=... : search

Notes carry:
  content.title.value, content.authors.value (list of names),
  content.venue.value, content.venueid.value (e.g., "ICLR.cc/2024/Conference"),
  content._bibtex.value  (canonical BibTeX we can consume)
"""
from __future__ import annotations

import re

from ..schemas import (
    AuthorityTier,
    Author,
    EvidenceRecord,
    PublicationIdentity,
    SearchQuery,
    SearchResult,
)
from .base import BaseHttpProvider


def _val(content: dict, key: str):
    v = content.get(key)
    if isinstance(v, dict):
        return v.get("value")
    return v


def _parse_author(name: str) -> Author:
    tokens = name.strip().split()
    if len(tokens) >= 2:
        family = tokens[-1]
        given = tokens[:-1]
    else:
        family = name.strip()
        given = []
    return Author(given=given, family=family, raw=name, formatted=f"{family}, {' '.join(given)}" if given else family)


_VENUE_YEAR_RE = re.compile(r"(19|20)\d{2}")


def _extract_year(content: dict) -> int | None:
    venueid = _val(content, "venueid") or ""
    m = _VENUE_YEAR_RE.search(venueid)
    if m:
        return int(m.group(0))
    venue = _val(content, "venue") or ""
    m = _VENUE_YEAR_RE.search(venue)
    if m:
        return int(m.group(0))
    return None


def _extract_venue(content: dict) -> str | None:
    return _val(content, "venue") or _val(content, "venueid") or None


def _note_to_record(note: dict) -> EvidenceRecord | None:
    content = note.get("content") or {}
    or_id = note.get("id")
    if not or_id:
        return None
    title = _val(content, "title")
    authors_raw = _val(content, "authors") or []
    authors = [_parse_author(n) for n in authors_raw if isinstance(n, str)]
    year = _extract_year(content)
    venue = _extract_venue(content)
    ident = PublicationIdentity(openreview_id=or_id)
    return EvidenceRecord(
        identity=ident,
        source="OpenReview",
        source_url=f"https://openreview.net/forum?id={or_id}",
        authority_tier="A",
        title=title,
        authors=authors,
        year=year,
        venue=venue,
        volume=None,
        number=None,
        pages=None,
        doi=None,
        entry_type="inproceedings" if venue and "Conference" in (venue or "") else None,
        publisher=None,
    )


class OpenReviewProvider(BaseHttpProvider):
    name = "OpenReview"
    authority_tier: AuthorityTier = "A"
    base_url = "https://api2.openreview.net"

    async def fetch_by_doi(self, doi: str) -> EvidenceRecord | None:
        # OpenReview doesn't index by DOI directly.
        return None

    async def fetch_by_arxiv(self, arxiv_id: str) -> EvidenceRecord | None:
        return None

    async def fetch_by_openreview(self, or_id: str) -> EvidenceRecord | None:
        if not or_id:
            return None
        params = {"id": or_id}
        data = await self._get_json(f"{self.base_url}/notes", params=params)
        if not data:
            return None
        notes = data.get("notes") or []
        if not notes:
            return None
        return _note_to_record(notes[0])

    async def search(self, query: SearchQuery) -> list[SearchResult]:
        if not query.title:
            return []
        params = {"content.title": query.title, "limit": "5"}
        data = await self._get_json(f"{self.base_url}/notes", params=params)
        if not data:
            return []
        out: list[SearchResult] = []
        for n in data.get("notes", []) or []:
            rec = _note_to_record(n)
            if rec is None:
                continue
            out.append(SearchResult(identity=rec.identity, score=1.0, record=rec))
        return out
