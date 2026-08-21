"""Shared pytest configuration.

Ensures unit tests never hit the network by using respx to mock all
provider HTTP calls, and provides fixture loaders that read recorded
responses from disk.
"""
from __future__ import annotations

import json
from pathlib import Path

import httpx
import pytest
import respx

FIXTURE_DIR = Path(__file__).parent / "fixtures"
BIB_DIR = Path(__file__).parent / "bibs"


@pytest.fixture
def crossref_fixture():
    def load(name: str) -> dict:
        return json.loads((FIXTURE_DIR / "crossref" / f"{name}.json").read_text(encoding="utf-8"))
    return load


@pytest.fixture
def dblp_fixture():
    def load(name: str) -> dict:
        return json.loads((FIXTURE_DIR / "dblp" / f"{name}.json").read_text(encoding="utf-8"))
    return load


@pytest.fixture
def arxiv_fixture():
    def load(name: str) -> str:
        return (FIXTURE_DIR / "arxiv" / f"{name}.xml").read_text(encoding="utf-8")
    return load


@pytest.fixture
def openreview_fixture():
    def load(name: str) -> dict:
        return json.loads((FIXTURE_DIR / "openreview" / f"{name}.json").read_text(encoding="utf-8"))
    return load


@pytest.fixture
def bibs_dir() -> Path:
    return BIB_DIR


@pytest.fixture
def respx_mock_ctx():
    """A respx mock context that fails if any un-mocked URL is called."""
    with respx.mock(assert_all_called=False) as m:
        yield m
