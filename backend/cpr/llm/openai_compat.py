"""Adapter for OpenAI-compatible chat endpoints (DeepSeek + OpenAI).

Both DeepSeek and OpenAI expose the same `POST /v1/chat/completions`
shape, so we share one adapter parameterized by base URL and model.

The adapter is thin on purpose:
- one round-trip per skill call
- structured output is enforced by prompt (`response_format=json_object`
  when the endpoint supports it; otherwise we tolerate a JSON string
  in the reply and parse it).
- unrecoverable errors → fall back to `low` confidence with a `reason`
  explaining the failure. Never raises to the caller.
"""
from __future__ import annotations

import json
import logging
from typing import Any

import httpx

from .base import (
    ConflictResolution,
    IdInference,
    SanityCheckResult,
    TieBreakResult,
)
from .prompts import (
    infer_id_prompt,
    resolve_conflict_prompt,
    sanity_check_prompt,
    system_prompt,
    tie_break_prompt,
)

log = logging.getLogger(__name__)


class OpenAICompatibleClient:
    """Thin async client for `POST /v1/chat/completions`."""

    def __init__(
        self,
        api_key: str,
        base_url: str,
        model: str,
        name: str,
        timeout: float = 30.0,
        supports_json_mode: bool = True,
    ):
        self.name = name
        self._api_key = api_key
        self._base_url = base_url.rstrip("/")
        self._model = model
        self._timeout = timeout
        self._client: httpx.AsyncClient | None = None
        self._supports_json_mode = supports_json_mode

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(
                timeout=self._timeout,
                headers={
                    "Authorization": f"Bearer {self._api_key}",
                    "Content-Type": "application/json",
                },
            )
        return self._client

    async def aclose(self) -> None:
        if self._client is not None:
            await self._client.aclose()
            self._client = None

    async def _chat(self, user_prompt: str) -> dict[str, Any] | None:
        """Send a single chat completion. Returns parsed JSON dict or None on failure."""
        payload: dict[str, Any] = {
            "model": self._model,
            "messages": [
                {"role": "system", "content": system_prompt()},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": 0.0,
        }
        if self._supports_json_mode:
            payload["response_format"] = {"type": "json_object"}
        try:
            client = await self._get_client()
            r = await client.post(f"{self._base_url}/chat/completions", json=payload)
        except httpx.HTTPError as e:
            log.warning("%s: HTTP error: %s", self.name, e)
            return None
        if r.status_code >= 400:
            log.warning("%s: HTTP %s: %s", self.name, r.status_code, r.text[:200])
            return None
        try:
            data = r.json()
            content = data["choices"][0]["message"]["content"]
        except Exception as e:
            log.warning("%s: bad response shape: %s", self.name, e)
            return None
        return _parse_json(content)

    async def sanity_check(self, entry_text: str) -> SanityCheckResult:
        parsed = await self._chat(sanity_check_prompt(entry_text))
        if parsed is None:
            return SanityCheckResult(ok=True, issues=[], confidence="low")
        try:
            return SanityCheckResult(**parsed)
        except Exception:
            return SanityCheckResult(ok=True, issues=[], confidence="low")

    async def tie_break(
        self, query: dict[str, Any], candidates: list[dict[str, Any]]
    ) -> TieBreakResult:
        parsed = await self._chat(tie_break_prompt(query, candidates))
        if parsed is None:
            return TieBreakResult(chosen_index=None, reason="LLM unavailable", confidence="low")
        try:
            return TieBreakResult(**parsed)
        except Exception:
            return TieBreakResult(chosen_index=None, reason="bad LLM reply", confidence="low")

    async def resolve_conflict(
        self, field: str, values: list[dict[str, Any]]
    ) -> ConflictResolution:
        parsed = await self._chat(resolve_conflict_prompt(field, values))
        if parsed is None:
            return ConflictResolution(chosen_value=None, reason="LLM unavailable", confidence="low")
        try:
            return ConflictResolution(**parsed)
        except Exception:
            return ConflictResolution(chosen_value=None, reason="bad LLM reply", confidence="low")

    async def infer_id(self, entry: dict[str, Any]) -> IdInference:
        parsed = await self._chat(infer_id_prompt(entry))
        if parsed is None:
            return IdInference(reason="LLM unavailable", confidence="low")
        try:
            return IdInference(**parsed)
        except Exception:
            return IdInference(reason="bad LLM reply", confidence="low")


def _parse_json(content: str) -> dict[str, Any] | None:
    """Best-effort JSON extraction from a chat-completion string.

    Some models wrap JSON in markdown fences (```json ... ```) or add
    prose before/after. We try (1) direct parse, (2) fenced-block
    extraction, (3) first `{ ... }` slice.
    """
    if not content:
        return None
    text = content.strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    # Strip ```json fences
    if text.startswith("```"):
        lines = text.splitlines()
        # drop the opening fence
        if lines[0].startswith("```"):
            lines = lines[1:]
        # drop the closing fence
        if lines and lines[-1].strip().startswith("```"):
            lines = lines[:-1]
        inner = "\n".join(lines).strip()
        try:
            return json.loads(inner)
        except json.JSONDecodeError:
            pass
    # First { ... } slice
    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1 and end > start:
        try:
            return json.loads(text[start : end + 1])
        except json.JSONDecodeError:
            return None
    return None


class DeepSeekClient(OpenAICompatibleClient):
    """DeepSeek is drop-in OpenAI-chat-compatible."""

    def __init__(self, api_key: str, model: str = "deepseek-chat", timeout: float = 30.0):
        super().__init__(
            api_key=api_key,
            base_url="https://api.deepseek.com/v1",
            model=model,
            name="deepseek",
            timeout=timeout,
            supports_json_mode=True,
        )


class OpenAIClient(OpenAICompatibleClient):
    """OpenAI."""

    def __init__(self, api_key: str, model: str = "gpt-4o-mini", timeout: float = 30.0):
        super().__init__(
            api_key=api_key,
            base_url="https://api.openai.com/v1",
            model=model,
            name="openai",
            timeout=timeout,
            supports_json_mode=True,
        )
