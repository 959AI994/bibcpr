"""StyleProfile Pydantic schema (§18)."""
from __future__ import annotations

from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, Field


class CitationKeyPolicy(BaseModel):
    strategy: Literal["preserve", "regenerate"] = "preserve"
    format: str = "{first_author_family}{year}{first_title_word}"


class PublicationPolicy(BaseModel):
    prefer_formal_over_preprint: bool = True
    demote_preprint_when_formal_available: bool = True
    keep_arxiv_eprint_field: bool = True


class AuthorPolicy(BaseModel):
    format: Literal["family, given", "given family"] = "family, given"
    join: str = " and "
    abbreviate_given: bool = False
    hyphenated_initials_join: str = "-"


class PagesPolicy(BaseModel):
    article_number_prefix: str | None = None
    double_hyphen: bool = True


class FieldsPolicy(BaseModel):
    order: list[str] = Field(default_factory=list)
    drop_if_empty: list[str] = Field(default_factory=list)


class UnicodePolicy(BaseModel):
    strategy: Literal["preserve", "latex_escape"] = "preserve"


class StyleProfile(BaseModel):
    name: str
    version: int = 1
    citation_key: CitationKeyPolicy = Field(default_factory=CitationKeyPolicy)
    publication: PublicationPolicy = Field(default_factory=PublicationPolicy)
    authors: AuthorPolicy = Field(default_factory=AuthorPolicy)
    pages: PagesPolicy = Field(default_factory=PagesPolicy)
    fields: FieldsPolicy = Field(default_factory=FieldsPolicy)
    unicode: UnicodePolicy = Field(default_factory=UnicodePolicy)


def load_default_profile() -> StyleProfile:
    """Load the shipped sjtu-ectl profile from `configs/sjtu-ectl.yaml`."""
    root = Path(__file__).resolve().parent.parent.parent.parent
    p = root / "configs" / "sjtu-ectl.yaml"
    if not p.exists():
        # Fallback to hardcoded default
        return StyleProfile(name="sjtu-ectl")
    data = yaml.safe_load(p.read_text(encoding="utf-8"))
    return StyleProfile.model_validate(data)
