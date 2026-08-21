"""LLM adapter tests.

All HTTP is mocked with respx; no real API keys are used.
"""
from __future__ import annotations

import httpx
import pytest
import respx

from cpr.llm.base import StubLLMClient
from cpr.llm.factory import build_client
from cpr.llm.openai_compat import DeepSeekClient, OpenAIClient, _parse_json
from cpr.llm.anthropic import AnthropicClient


# ---------- _parse_json extraction -------------------------------------------

def test_parse_json_direct():
    assert _parse_json('{"ok": true}') == {"ok": True}


def test_parse_json_fenced():
    text = '```json\n{"ok": true, "issues": []}\n```'
    assert _parse_json(text) == {"ok": True, "issues": []}


def test_parse_json_with_prose():
    text = 'Sure, here is the JSON: {"ok": true, "confidence": "high"} — hope that helps!'
    assert _parse_json(text) == {"ok": True, "confidence": "high"}


def test_parse_json_none_on_garbage():
    assert _parse_json("this is not json at all") is None


# ---------- stub client is truly a no-op ------------------------------------

@pytest.mark.asyncio
async def test_stub_client_never_fails():
    c = StubLLMClient()
    r = await c.sanity_check("@article{x, title={t}}")
    assert r.ok is True
    assert r.confidence == "low"
    tb = await c.tie_break({"title": "t"}, [{"title": "t"}])
    assert tb.chosen_index is None
    await c.aclose()


# ---------- factory selects correctly ---------------------------------------

def test_factory_off_returns_stub():
    assert build_client("off").name == "stub"


def test_factory_auto_without_keys_returns_stub(monkeypatch, tmp_path, chdir_tmp=None):
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.chdir(tmp_path)  # so ./deepseekkey doesn't exist
    assert build_client("auto").name == "stub"


def test_factory_deepseek_from_env(monkeypatch, tmp_path):
    monkeypatch.setenv("DEEPSEEK_API_KEY", "test-key-xyz")
    monkeypatch.chdir(tmp_path)
    c = build_client("deepseek")
    assert c.name == "deepseek"


def test_factory_missing_key_falls_back_to_stub(monkeypatch, tmp_path):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.chdir(tmp_path)
    c = build_client("openai")
    assert c.name == "stub"


# ---------- OpenAI-compat sanity_check happy + sad path ----------------------

@pytest.mark.asyncio
async def test_deepseek_sanity_check_ok(respx_mock_ctx):
    respx_mock_ctx.post("https://api.deepseek.com/v1/chat/completions").mock(
        return_value=httpx.Response(
            200,
            json={
                "choices": [
                    {"message": {"content": '{"ok": true, "issues": [], "confidence": "high"}'}}
                ]
            },
        )
    )
    c = DeepSeekClient(api_key="test", model="deepseek-chat")
    r = await c.sanity_check("@article{x, title={t}}")
    assert r.ok is True
    assert r.confidence == "high"
    await c.aclose()


@pytest.mark.asyncio
async def test_deepseek_sanity_check_flags_issues(respx_mock_ctx):
    respx_mock_ctx.post("https://api.deepseek.com/v1/chat/completions").mock(
        return_value=httpx.Response(
            200,
            json={
                "choices": [
                    {
                        "message": {
                            "content": '{"ok": false, "issues": ["unbalanced braces"], "confidence": "high"}'
                        }
                    }
                ]
            },
        )
    )
    c = DeepSeekClient(api_key="test")
    r = await c.sanity_check("@article{x, title={t}")
    assert r.ok is False
    assert "unbalanced braces" in r.issues
    await c.aclose()


@pytest.mark.asyncio
async def test_openai_http_error_falls_back(respx_mock_ctx):
    respx_mock_ctx.post("https://api.openai.com/v1/chat/completions").mock(
        return_value=httpx.Response(500, text="Server error")
    )
    c = OpenAIClient(api_key="test")
    r = await c.sanity_check("@article{x}")
    # Degrades to low-confidence OK rather than raising
    assert r.ok is True
    assert r.confidence == "low"
    await c.aclose()


@pytest.mark.asyncio
async def test_anthropic_sanity_check(respx_mock_ctx):
    respx_mock_ctx.post("https://api.anthropic.com/v1/messages").mock(
        return_value=httpx.Response(
            200,
            json={
                "content": [
                    {"type": "text", "text": '{"ok": true, "issues": [], "confidence": "medium"}'}
                ]
            },
        )
    )
    c = AnthropicClient(api_key="test")
    r = await c.sanity_check("@article{x, title={t}}")
    assert r.ok is True
    assert r.confidence == "medium"
    await c.aclose()


@pytest.mark.asyncio
async def test_tie_break_with_null_chosen_index(respx_mock_ctx):
    respx_mock_ctx.post("https://api.deepseek.com/v1/chat/completions").mock(
        return_value=httpx.Response(
            200,
            json={
                "choices": [
                    {
                        "message": {
                            "content": '{"chosen_index": null, "reason": "no candidate matches", "confidence": "high"}'
                        }
                    }
                ]
            },
        )
    )
    c = DeepSeekClient(api_key="test")
    r = await c.tie_break({"title": "X"}, [{"title": "Y"}])
    assert r.chosen_index is None
    assert r.confidence == "high"
    await c.aclose()
