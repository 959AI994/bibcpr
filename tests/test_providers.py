"""Provider tests using recorded fixtures. All calls are respx-mocked."""
import httpx
import pytest

from cpr.providers.arxiv import ArxivProvider
from cpr.providers.cache import NullCache
from cpr.providers.crossref import CrossrefProvider
from cpr.providers.dblp import DBLPProvider
from cpr.providers.openreview import OpenReviewProvider


@pytest.mark.asyncio
async def test_crossref_by_doi(respx_mock_ctx, crossref_fixture):
    payload = crossref_fixture("attention")
    respx_mock_ctx.get("https://api.crossref.org/works/10.48550%2Farxiv.1706.03762").mock(
        return_value=httpx.Response(200, json=payload)
    )
    p = CrossrefProvider(cache=NullCache())
    rec = await p.fetch_by_doi("10.48550/arxiv.1706.03762")
    await p.aclose()
    assert rec is not None
    assert rec.title == "Attention Is All You Need"
    assert rec.year == 2017
    assert len(rec.authors) == 8
    assert rec.authors[0].family == "Vaswani"
    assert rec.authority_tier == "A"


@pytest.mark.asyncio
async def test_dblp_search(respx_mock_ctx, dblp_fixture):
    payload = dblp_fixture("attention")
    respx_mock_ctx.get("https://dblp.org/search/publ/api").mock(
        return_value=httpx.Response(200, json=payload)
    )
    p = DBLPProvider(cache=NullCache())
    rec = await p.fetch_by_doi("10.5555/3295222.3295349")
    await p.aclose()
    assert rec is not None
    assert rec.venue == "NeurIPS"
    assert rec.year == 2017
    assert rec.entry_type == "inproceedings"
    assert rec.authority_tier == "B"


@pytest.mark.asyncio
async def test_arxiv_by_id(respx_mock_ctx, arxiv_fixture):
    xml = arxiv_fixture("attention")
    respx_mock_ctx.get("http://export.arxiv.org/api/query").mock(
        return_value=httpx.Response(200, text=xml)
    )
    p = ArxivProvider(cache=NullCache())
    rec = await p.fetch_by_arxiv("1706.03762")
    await p.aclose()
    assert rec is not None
    assert rec.title == "Attention Is All You Need"
    assert rec.year == 2017
    assert rec.doi == "10.48550/arxiv.1706.03762"
    assert rec.formal_publication_available is True
    assert rec.arxiv_id.startswith("1706.03762")
    assert rec.authority_tier == "C"


@pytest.mark.asyncio
async def test_openreview_search(respx_mock_ctx, openreview_fixture):
    payload = openreview_fixture("sample")
    respx_mock_ctx.get("https://api2.openreview.net/notes").mock(
        return_value=httpx.Response(200, json=payload)
    )
    p = OpenReviewProvider(cache=NullCache())
    rec = await p.fetch_by_openreview("ExampleForum2024")
    await p.aclose()
    assert rec is not None
    assert rec.title == "A Sample OpenReview Paper"
    assert rec.venue == "ICLR 2024 Poster"
    assert rec.year == 2024
    assert rec.authority_tier == "A"


@pytest.mark.asyncio
async def test_crossref_404_returns_none(respx_mock_ctx):
    respx_mock_ctx.get("https://api.crossref.org/works/10.9999%2Fnope").mock(
        return_value=httpx.Response(404)
    )
    p = CrossrefProvider(cache=NullCache())
    rec = await p.fetch_by_doi("10.9999/nope")
    await p.aclose()
    assert rec is None
