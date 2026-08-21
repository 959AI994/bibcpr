"""LLM factory: pick a client based on user preference or env auto-detect.

Auto-detect order (matches the Skill doc):
  1. DEEPSEEK_API_KEY env var → DeepSeekClient
  2. ./deepseekkey file       → DeepSeekClient
  3. OPENAI_API_KEY env var   → OpenAIClient
  4. ANTHROPIC_API_KEY env var→ AnthropicClient
  5. nothing found            → StubLLMClient (no-op)

Explicit provider selection (`build_client("deepseek", ...)`) always
wins over auto-detect.
"""
from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Literal

from .anthropic import AnthropicClient
from .base import LLMClient, StubLLMClient
from .openai_compat import DeepSeekClient, OpenAIClient

log = logging.getLogger(__name__)

ProviderName = Literal["auto", "off", "deepseek", "openai", "anthropic", "stub"]


def _read_deepseek_key_file() -> str | None:
    """Read the first line of ./deepseekkey if it exists (user convenience)."""
    p = Path("deepseekkey")
    if not p.exists():
        return None
    try:
        for line in p.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#"):
                return line
    except OSError:
        return None
    return None


def build_client(
    provider: ProviderName = "auto",
    model: str | None = None,
) -> LLMClient:
    """Return a ready-to-use LLMClient.

    Never raises: if the requested provider is unconfigured we log a
    warning and fall back to StubLLMClient so the caller's pipeline
    can proceed.
    """
    model = model or os.environ.get("CPR_LLM_MODEL")

    if provider == "off" or provider == "stub":
        return StubLLMClient()

    if provider == "auto":
        # Try each in order
        if os.environ.get("DEEPSEEK_API_KEY"):
            provider = "deepseek"
        elif _read_deepseek_key_file():
            provider = "deepseek"
        elif os.environ.get("OPENAI_API_KEY"):
            provider = "openai"
        elif os.environ.get("ANTHROPIC_API_KEY"):
            provider = "anthropic"
        else:
            log.info("No LLM API key found — LLM checks disabled (stub client).")
            return StubLLMClient()

    if provider == "deepseek":
        key = os.environ.get("DEEPSEEK_API_KEY") or _read_deepseek_key_file()
        if not key:
            log.warning("DeepSeek requested but no key found — falling back to stub.")
            return StubLLMClient()
        return DeepSeekClient(api_key=key, model=model or "deepseek-chat")

    if provider == "openai":
        key = os.environ.get("OPENAI_API_KEY")
        if not key:
            log.warning("OpenAI requested but OPENAI_API_KEY not set — falling back to stub.")
            return StubLLMClient()
        return OpenAIClient(api_key=key, model=model or "gpt-4o-mini")

    if provider == "anthropic":
        key = os.environ.get("ANTHROPIC_API_KEY")
        if not key:
            log.warning("Anthropic requested but ANTHROPIC_API_KEY not set — falling back to stub.")
            return StubLLMClient()
        return AnthropicClient(api_key=key, model=model or "claude-haiku-4-5-20251001")

    log.warning("Unknown LLM provider %r — falling back to stub.", provider)
    return StubLLMClient()
