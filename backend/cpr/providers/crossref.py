"""Crossref provider.

Docs: https://api.crossref.org
- /works/{doi}   : Full record by DOI.
- /works?query.bibliographic=... : Free-text search.
"""
from __future__ import annotations

import urllib.parse

from ..schemas import (
    AuthorityTier,
    Author,
    EvidenceRecord,
    PublicationIdentity,
    SearchQuery,
    SearchResult,
)
from .base import BaseHttpProvider


_TYPE_MAP = {
    "journal-article": "article",
    "proceedings-article": "inproceedings",
    "book-chapter": "incollection",
    "book": "book",
    "monograph": "book",
    "posted-content": "misc",       # preprint on Crossref
    "report": "techreport",
    "dissertation": "phdthesis",
}


def _crossref_author_to_our_author(a: dict) -> Author:
    family = (a.get("family") or "").strip()
    given_raw = (a.get("given") or "").strip()
    given = [g for g in given_raw.split() if g]
    return Author(
        given=given,
        family=family,
        raw=f"{given_raw} {family}".strip(),
        formatted=f"{family}, {given_raw}" if family and given_raw else family or given_raw,
    )


def _extract_year(msg: dict) -> int | None:
    for key in ("published-print", "published-online", "issued", "published"):
        parts = msg.get(key, {}).get("date-parts", [])
        if parts and parts[0]:
            y = parts[0][0]
            if isinstance(y, int):
                return y
            if isinstance(y, str) and y.isdigit():
                return int(y)
    return None


def _extract_venue(msg: dict) -> str | None:
    ct = msg.get("container-title") or []
    if ct:
        return ct[0]
    et = msg.get("event", {}).get("name")
    return et


def _msg_to_record(msg: dict) -> EvidenceRecord:
    doi = (msg.get("DOI") or "").lower() or None
    ident = PublicationIdentity(doi=doi)
    title_list = msg.get("title") or []
    title = title_list[0] if title_list else None
    authors_raw = msg.get("author") or []
    authors = [_crossref_author_to_our_author(a) for a in authors_raw]
    year = _extract_year(msg)
    venue = _extract_venue(msg)
    volume = msg.get("volume")
    issue = msg.get("issue")
    pages = msg.get("page")
    publisher = msg.get("publisher")
    entry_type = _TYPE_MAP.get(msg.get("type", ""), None)
    source_url = msg.get("URL") or (f"https://doi.org/{doi}" if doi else "https://api.crossref.org")

    return EvidenceRecord(
        identity=ident,
        source="Crossref",
        source_url=source_url,
        authority_tier="A",
        title=title,
        authors=authors,
        year=year,
        venue=venue,
        volume=str(volume) if volume is not None else None,
        number=str(issue) if issue is not None else None,
        pages=pages,
        doi=doi,
        entry_type=entry_type,
        publisher=publisher,
    )


class CrossrefProvider(BaseHttpProvider):
    name = "Crossref"
    authority_tier: AuthorityTier = "A"
    base_url = "https://api.crossref.org"

    async def fetch_by_doi(self, doi: str) -> EvidenceRecord | None:
        if not doi:
            return None
        # Crossref DOIs are case-insensitive; encode path.
        url = f"{self.base_url}/works/{urllib.parse.quote(doi, safe='/')}"
        data = await self._get_json(url)
        if not data or "message" not in data:
            return None
        return _msg_to_record(data["message"])

    async def fetch_by_arxiv(self, arxiv_id: str) -> EvidenceRecord | None:
        # Crossref sometimes indexes arXiv preprints via 10.48550/arXiv.XXXX.YYYYY
        candidate = f"10.48550/arXiv.{arxiv_id}"
        return await self.fetch_by_doi(candidate)

    async def search(self, query: SearchQuery) -> list[SearchResult]:
        params: dict[str, str] = {"rows": "5"}
        parts: list[str] = []
        if query.title:
            parts.append(query.title)
        if query.first_author_family:
            parts.append(query.first_author_family)
        if query.year:
            parts.append(str(query.year))
        if not parts:
            return []
        params["query.bibliographic"] = " ".join(parts)
        data = await self._get_json(f"{self.base_url}/works", params=params)
        if not data:
            return []
        items = data.get("message", {}).get("items", []) or []
        out: list[SearchResult] = []
        for it in items:
            rec = _msg_to_record(it)
            out.append(SearchResult(identity=rec.identity, score=float(it.get("score", 0.0)), record=rec))
        return out
