"""arXiv provider.

Docs: https://arxiv.org/help/api/user-manual
Endpoint: http://export.arxiv.org/api/query?id_list=... or ?search_query=...
Response: Atom XML.
"""
from __future__ import annotations

from datetime import datetime
from xml.etree.ElementTree import Element

from defusedxml.ElementTree import fromstring as _fromstring

from ..schemas import (
    AuthorityTier,
    Author,
    EvidenceRecord,
    PublicationIdentity,
    SearchQuery,
    SearchResult,
)
from .base import BaseHttpProvider


_ATOM = "{http://www.w3.org/2005/Atom}"
_ARXIV = "{http://arxiv.org/schemas/atom}"


def _text(el: Element | None) -> str | None:
    if el is None or el.text is None:
        return None
    return el.text.strip() or None


def _parse_arxiv_author(name: str) -> Author:
    tokens = name.strip().split()
    if len(tokens) >= 2:
        family = tokens[-1]
        given = tokens[:-1]
    else:
        family = name.strip()
        given = []
    return Author(given=given, family=family, raw=name, formatted=f"{family}, {' '.join(given)}" if given else family)


def _entry_to_record(entry: Element) -> EvidenceRecord | None:
    id_el = entry.find(f"{_ATOM}id")
    id_text = _text(id_el) or ""
    # `http://arxiv.org/abs/2301.12345v1`
    arxiv_id = id_text.rsplit("/", 1)[-1] if id_text else ""
    if not arxiv_id:
        return None

    title = _text(entry.find(f"{_ATOM}title"))
    published = _text(entry.find(f"{_ATOM}published"))
    year: int | None = None
    if published:
        try:
            year = datetime.fromisoformat(published.replace("Z", "+00:00")).year
        except ValueError:
            year = None
    doi_el = entry.find(f"{_ARXIV}doi")
    doi = (_text(doi_el) or "").lower() or None
    journal_ref = _text(entry.find(f"{_ARXIV}journal_ref"))

    authors: list[Author] = []
    for a in entry.findall(f"{_ATOM}author"):
        n = _text(a.find(f"{_ATOM}name"))
        if n:
            authors.append(_parse_arxiv_author(n))

    ident = PublicationIdentity(doi=doi, arxiv_id=arxiv_id)

    return EvidenceRecord(
        identity=ident,
        source="arXiv",
        source_url=f"https://arxiv.org/abs/{arxiv_id}",
        authority_tier="C",
        title=title,
        authors=authors,
        year=year,
        venue=journal_ref,   # arXiv's opinion on where it was published
        volume=None,
        number=None,
        pages=None,
        doi=doi,
        entry_type="article" if not doi else None,   # heuristic; overridden by Crossref/DBLP
        publisher=None,
        arxiv_id=arxiv_id,
        formal_publication_available=bool(doi),
    )


class ArxivProvider(BaseHttpProvider):
    name = "arXiv"
    authority_tier: AuthorityTier = "C"
    base_url = "http://export.arxiv.org/api/query"

    async def fetch_by_doi(self, doi: str) -> EvidenceRecord | None:
        # arXiv API doesn't do DOI lookup directly; skip.
        return None

    async def fetch_by_arxiv(self, arxiv_id: str) -> EvidenceRecord | None:
        if not arxiv_id:
            return None
        text = await self._get_text(self.base_url, params={"id_list": arxiv_id})
        if not text:
            return None
        try:
            root = _fromstring(text)
        except Exception:
            return None
        entries = root.findall(f"{_ATOM}entry")
        if not entries:
            return None
        return _entry_to_record(entries[0])

    async def search(self, query: SearchQuery) -> list[SearchResult]:
        parts: list[str] = []
        if query.title:
            parts.append(f'ti:"{query.title}"')
        if query.first_author_family:
            parts.append(f'au:"{query.first_author_family}"')
        if not parts:
            return []
        params = {"search_query": " AND ".join(parts), "max_results": "5"}
        text = await self._get_text(self.base_url, params=params)
        if not text:
            return []
        try:
            root = _fromstring(text)
        except Exception:
            return []
        out: list[SearchResult] = []
        for entry in root.findall(f"{_ATOM}entry"):
            rec = _entry_to_record(entry)
            if rec is None:
                continue
            out.append(SearchResult(identity=rec.identity, score=1.0, record=rec))
        return out
