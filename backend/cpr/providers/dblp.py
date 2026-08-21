"""DBLP provider.

Docs: https://dblp.org/faq/13501473.html
- /search/publ/api?q=...&format=json : bibliographic search
- Each hit contains a DBLP key; the venue/year/type are structured.
"""
from __future__ import annotations

from ..schemas import (
    AuthorityTier,
    Author,
    EvidenceRecord,
    PublicationIdentity,
    SearchQuery,
    SearchResult,
)
from .base import BaseHttpProvider


def _split_dblp_author_field(a) -> list[dict]:
    """DBLP returns `authors.author` as either a dict, list of dicts, or list of strings."""
    if a is None:
        return []
    if isinstance(a, dict):
        return [a]
    if isinstance(a, list):
        return a
    return []


def _dblp_author_to_our_author(a) -> Author:
    if isinstance(a, str):
        text = a
    elif isinstance(a, dict):
        text = a.get("text", "") or ""
    else:
        text = ""
    # DBLP disambiguates duplicates like "John Smith 0001"; strip trailing 4-digit id.
    parts = text.strip().rsplit(" ", 1)
    if len(parts) == 2 and parts[1].isdigit() and len(parts[1]) == 4:
        text = parts[0]
    tokens = text.split()
    if len(tokens) >= 2:
        family = tokens[-1]
        given = tokens[:-1]
    else:
        family = text
        given = []
    return Author(
        given=given,
        family=family,
        raw=text,
        formatted=f"{family}, {' '.join(given)}" if given else family,
    )


_DBLP_TYPE_MAP = {
    "Journal Articles": "article",
    "Conference and Workshop Papers": "inproceedings",
    "Books and Theses": "book",
    "Parts in Books or Collections": "incollection",
    "Editorship": "proceedings",
    "Informal and Other Publications": "misc",
}


def _hit_to_record(hit: dict) -> EvidenceRecord:
    info = hit.get("info", {}) or {}
    title = info.get("title")
    if title:
        title = title.rstrip(".")
    authors_raw = _split_dblp_author_field((info.get("authors") or {}).get("author"))
    authors = [_dblp_author_to_our_author(a) for a in authors_raw]
    year_raw = info.get("year")
    year = int(year_raw) if year_raw and str(year_raw).isdigit() else None
    venue = info.get("venue")
    volume = info.get("volume")
    number = info.get("number")
    pages = info.get("pages")
    doi = info.get("doi")
    if isinstance(doi, str):
        doi = doi.lower()
    type_ = _DBLP_TYPE_MAP.get(info.get("type", ""), None)
    url = info.get("url") or info.get("ee") or ""
    dblp_key = info.get("key")
    ident = PublicationIdentity(doi=doi)

    return EvidenceRecord(
        identity=ident,
        source="DBLP",
        source_url=url or (f"https://dblp.org/rec/{dblp_key}" if dblp_key else "https://dblp.org"),
        authority_tier="B",
        title=title,
        authors=authors,
        year=year,
        venue=venue,
        volume=str(volume) if volume is not None else None,
        number=str(number) if number is not None else None,
        pages=pages,
        doi=doi,
        entry_type=type_,
        publisher=None,
    )


class DBLPProvider(BaseHttpProvider):
    name = "DBLP"
    authority_tier: AuthorityTier = "B"
    base_url = "https://dblp.org"

    async def fetch_by_doi(self, doi: str) -> EvidenceRecord | None:
        if not doi:
            return None
        params = {"q": doi, "format": "json", "h": "5"}
        data = await self._get_json(f"{self.base_url}/search/publ/api", params=params)
        return self._first_matching_hit(data, doi=doi)

    async def fetch_by_arxiv(self, arxiv_id: str) -> EvidenceRecord | None:
        if not arxiv_id:
            return None
        params = {"q": arxiv_id, "format": "json", "h": "5"}
        data = await self._get_json(f"{self.base_url}/search/publ/api", params=params)
        return self._first_matching_hit(data)

    async def search(self, query: SearchQuery) -> list[SearchResult]:
        parts: list[str] = []
        if query.title:
            parts.append(query.title)
        if query.first_author_family:
            parts.append(query.first_author_family)
        if query.year:
            parts.append(str(query.year))
        if not parts:
            return []
        params = {"q": " ".join(parts), "format": "json", "h": "5"}
        data = await self._get_json(f"{self.base_url}/search/publ/api", params=params)
        return self._all_hits(data)

    # ---- helpers -----------------------------------------------------------
    @staticmethod
    def _hits(data: dict | None) -> list[dict]:
        if not data:
            return []
        hits = (data.get("result") or {}).get("hits") or {}
        hit = hits.get("hit") or []
        if isinstance(hit, dict):
            return [hit]
        return hit or []

    def _first_matching_hit(self, data: dict | None, doi: str | None = None) -> EvidenceRecord | None:
        hits = self._hits(data)
        if not hits:
            return None
        if doi:
            for h in hits:
                info = h.get("info", {}) or {}
                if (info.get("doi") or "").lower() == doi.lower():
                    return _hit_to_record(h)
        # Fall back to the top-scoring hit
        return _hit_to_record(hits[0])

    def _all_hits(self, data: dict | None) -> list[SearchResult]:
        out: list[SearchResult] = []
        for h in self._hits(data):
            rec = _hit_to_record(h)
            score_raw = h.get("@score", "0")
            try:
                score = float(score_raw)
            except (TypeError, ValueError):
                score = 0.0
            out.append(SearchResult(identity=rec.identity, score=score, record=rec))
        return out
