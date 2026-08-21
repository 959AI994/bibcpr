"""Provider protocol shared by every evidence source."""
from __future__ import annotations

from typing import Protocol, runtime_checkable

import httpx

from ..schemas import (
    AuthorityTier,
    EvidenceRecord,
    SearchQuery,
    SearchResult,
)


class ProviderError(Exception):
    """Non-fatal failure from a provider (network / parse / 4xx)."""


@runtime_checkable
class EvidenceProvider(Protocol):
    """Contract every evidence source must satisfy."""
    name: str
    authority_tier: AuthorityTier

    async def fetch_by_doi(self, doi: str) -> EvidenceRecord | None: ...
    async def fetch_by_arxiv(self, arxiv_id: str) -> EvidenceRecord | None: ...
    async def search(self, query: SearchQuery) -> list[SearchResult]: ...


class BaseHttpProvider:
    """Mix-in with a shared `httpx.AsyncClient` and cache indirection.

    Concrete providers subclass this and add typed endpoint methods.
    """
    name: str = "Base"
    authority_tier: AuthorityTier = "D"
    base_url: str = ""

    def __init__(
        self,
        client: httpx.AsyncClient | None = None,
        cache=None,
        user_agent: str = "cpr/0.1.0 (+https://github.com/CPR)",
        timeout: float = 15.0,
    ):
        self._client = client
        self._own_client = client is None
        self._user_agent = user_agent
        self._timeout = timeout
        self._cache = cache

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(
                timeout=self._timeout,
                headers={"User-Agent": self._user_agent},
                follow_redirects=True,
            )
        return self._client

    async def aclose(self) -> None:
        if self._own_client and self._client is not None:
            await self._client.aclose()
            self._client = None

    async def _get_json(self, url: str, params: dict | None = None) -> dict | None:
        cache_key = ("json", url, tuple(sorted((params or {}).items())))
        if self._cache is not None:
            cached = self._cache.get(cache_key)
            if cached is not None:
                return cached
        client = await self._get_client()
        try:
            r = await client.get(url, params=params)
        except httpx.HTTPError as e:
            raise ProviderError(f"{self.name}: HTTP error for {url}: {e}") from e
        if r.status_code == 404:
            if self._cache is not None:
                self._cache.set(cache_key, None)
            return None
        if r.status_code >= 400:
            raise ProviderError(f"{self.name}: HTTP {r.status_code} for {url}")
        try:
            data = r.json()
        except Exception as e:
            raise ProviderError(f"{self.name}: bad JSON from {url}: {e}") from e
        if self._cache is not None:
            self._cache.set(cache_key, data)
        return data

    async def _get_text(self, url: str, params: dict | None = None) -> str | None:
        cache_key = ("text", url, tuple(sorted((params or {}).items())))
        if self._cache is not None:
            cached = self._cache.get(cache_key)
            if cached is not None:
                return cached
        client = await self._get_client()
        try:
            r = await client.get(url, params=params)
        except httpx.HTTPError as e:
            raise ProviderError(f"{self.name}: HTTP error for {url}: {e}") from e
        if r.status_code == 404:
            if self._cache is not None:
                self._cache.set(cache_key, None)
            return None
        if r.status_code >= 400:
            raise ProviderError(f"{self.name}: HTTP {r.status_code} for {url}")
        text = r.text
        if self._cache is not None:
            self._cache.set(cache_key, text)
        return text
