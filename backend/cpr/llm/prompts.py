"""Prompt templates for LLM skills.

Each template is a small, deterministic function of its inputs. All
templates end with a JSON-schema instruction so the model returns
structured output we can parse without hallucinated wrappers.
"""
from __future__ import annotations

import json
from typing import Any


_SYSTEM_ROLE = (
    "You are a strict bibliographic assistant for a BibTeX auditor. "
    "You never invent metadata. When asked to make a decision, you "
    "return only JSON matching the requested schema. If you are "
    "unsure, you say so explicitly by returning confidence='low'."
)


def system_prompt() -> str:
    return _SYSTEM_ROLE


def sanity_check_prompt(entry_text: str) -> str:
    return (
        "Below is a serialized BibTeX entry that a downstream tool "
        "wants to publish as 'verified'. Look ONLY for obvious errors:\n"
        "  - unbalanced braces\n"
        "  - missing required field for the entry_type\n"
        "  - year that is clearly impossible (<1600 or >2100)\n"
        "  - venue that looks nothing like a real conference/journal name\n"
        "  - author list that looks like an institution (contains 'Inc', 'Ltd', 'Institute', etc.)\n\n"
        "Do not comment on style or capitalization.\n\n"
        f"Entry:\n```\n{entry_text}\n```\n\n"
        "Reply with JSON exactly of the form:\n"
        '{"ok": true|false, "issues": ["string", ...], "confidence": "low"|"medium"|"high"}'
    )


def tie_break_prompt(query: dict[str, Any], candidates: list[dict[str, Any]]) -> str:
    return (
        "Given the following BibTeX query and a list of candidate "
        "records from evidence providers, choose the candidate that "
        "most likely refers to the same publication. If none match, "
        "return chosen_index=null.\n\n"
        f"Query:\n{json.dumps(query, indent=2, ensure_ascii=False)}\n\n"
        f"Candidates:\n{json.dumps(candidates, indent=2, ensure_ascii=False)}\n\n"
        "Reply with JSON:\n"
        '{"chosen_index": int|null, "reason": "string", "confidence": "low"|"medium"|"high"}'
    )


def resolve_conflict_prompt(field: str, values: list[dict[str, Any]]) -> str:
    return (
        f"Two or more evidence sources disagree on the field `{field}`. "
        "Each candidate is a dict with `value`, `source`, and "
        "`authority_tier` (A > B > C). Prefer higher authority tier. "
        "If you cannot choose confidently, return confidence='low' and "
        "chosen_value=null.\n\n"
        f"Candidates:\n{json.dumps(values, indent=2, ensure_ascii=False)}\n\n"
        "Reply with JSON:\n"
        '{"chosen_value": <same type as candidate value or null>, '
        '"reason": "string", "confidence": "low"|"medium"|"high"}'
    )


def infer_id_prompt(entry: dict[str, Any]) -> str:
    return (
        "You are given a raw BibTeX entry that has NO DOI, arXiv id, "
        "or OpenReview id. Suggest a plausible DOI or arXiv id ONLY "
        "if you are highly confident. It is completely acceptable to "
        "return both as null. Never invent an id.\n\n"
        f"Entry:\n{json.dumps(entry, indent=2, ensure_ascii=False)}\n\n"
        "Reply with JSON:\n"
        '{"doi": "10.xxxx/..."|null, "arxiv_id": "NNNN.NNNNN"|null, '
        '"reason": "string", "confidence": "low"|"medium"|"high"}'
    )
