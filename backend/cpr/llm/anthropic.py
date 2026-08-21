"""Anthropic Messages API adapter.

Anthropic differs from OpenAI-chat: single `system` param + `messages`
list, no `response_format=json_object` mode. We prompt-engineer the
JSON output and parse.
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
from .openai_compat import _parse_json
from .prompts import (
    infer_id_prompt,
    resolve_conflict_prompt,
    sanity_check_prompt,
    system_prompt,
    tie_break_prompt,
)

log = logging.getLogger(__name__)


class AnthropicClient:
    """Adapter for Anthropic Messages API (`POST /v1/messages`)."""

    name: str = "anthropic"

    def __init__(
        self,
        api_key: str,
        model: str = "claude-haiku-4-5-20251001",
        timeout: float = 30.0,
    ):
        self._api_key = api_key
        self._model = model
        self._timeout = timeout
        self._client: httpx.AsyncClient | None = None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(
                timeout=self._timeout,
                headers={
                    "x-api-key": self._api_key,
                    "anthropic-version": "2023-06-01",
                    "Content-Type": "application/json",
                },
            )
        return self._client

    async def aclose(self) -> None:
        if self._client is not None:
            await self._client.aclose()
            self._client = None

    async def _chat(self, user_prompt: str) -> dict[str, Any] | None:
        payload = {
            "model": self._model,
            "system": system_prompt(),
            "max_tokens": 1024,
            "temperature": 0.0,
            "messages": [{"role": "user", "content": user_prompt}],
        }
        try:
            client = await self._get_client()
            r = await client.post("https://api.anthropic.com/v1/messages", json=payload)
        except httpx.HTTPError as e:
            log.warning("anthropic: HTTP error: %s", e)
            return None
        if r.status_code >= 400:
            log.warning("anthropic: HTTP %s: %s", r.status_code, r.text[:200])
            return None
        try:
            data = r.json()
            content = data["content"][0]["text"]
        except Exception as e:
            log.warning("anthropic: bad response shape: %s", e)
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
