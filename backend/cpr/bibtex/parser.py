"""BibTeX parser wrapping `bibtexparser` v2.

Produces `BibEntry` records with normalized fields and preserved
citation keys, entry types (lowercased) and source positions.
"""
from __future__ import annotations

from pathlib import Path

import bibtexparser
from bibtexparser.library import Library
from bibtexparser.model import Entry, Field

from ..schemas import BibEntry, SourcePosition
from .names import parse_person_list


_TEXT_FIELDS = {
    "title", "journal", "booktitle", "publisher", "organization",
    "address", "series", "edition", "isbn", "issn", "note", "month",
    "url", "doi", "eprint", "primaryclass", "archiveprefix",
    "volume", "number", "pages",
}


def _unbrace_value(v: str) -> str:
    """Strip a single balanced outer `{...}` if the whole value is wrapped."""
    v = v.strip()
    if len(v) >= 2 and v.startswith("{") and v.endswith("}"):
        # Only unwrap if the braces are balanced end-to-end (no unmatched
        # closer inside the outer pair).
        depth = 0
        for i, ch in enumerate(v):
            if ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0 and i < len(v) - 1:
                    return v
        return v[1:-1]
    # Strip surrounding double quotes similarly
    if len(v) >= 2 and v.startswith('"') and v.endswith('"'):
        return v[1:-1]
    return v


def _clean_field(v: str) -> str:
    return _unbrace_value(v).strip()


def _to_int_or_none(v: str) -> int | None:
    v = _clean_field(v)
    if not v:
        return None
    # Some years are "2024a" or contain LaTeX; extract the first 4-digit run.
    import re
    m = re.search(r"\d{4}", v)
    return int(m.group(0)) if m else None


def _entry_to_bibentry(entry: Entry) -> BibEntry:
    fields_by_key: dict[str, Field] = {f.key.lower(): f for f in entry.fields}
    field_order = [f.key for f in entry.fields]

    def get(name: str) -> str | None:
        f = fields_by_key.get(name.lower())
        if f is None:
            return None
        return _clean_field(f.value)

    author_raw = get("author") or ""
    editor_raw = get("editor") or ""

    known_keys = {
        "author", "editor", "title", "journal", "booktitle", "year",
        "month", "volume", "number", "pages", "doi", "url", "eprint",
        "archiveprefix", "primaryclass", "publisher", "organization",
        "address", "series", "edition", "isbn", "issn", "note",
    }
    raw_fields: dict[str, str] = {}
    for f in entry.fields:
        if f.key.lower() not in known_keys:
            raw_fields[f.key] = _clean_field(f.value)

    line = entry.start_line
    src_pos: SourcePosition | None = None
    if line is not None:
        src_pos = SourcePosition(line_start=line, line_end=line)

    be = BibEntry(
        key=entry.key,
        entry_type=entry.entry_type.lower(),
        title=get("title"),
        authors=parse_person_list(author_raw) if author_raw else [],
        editors=parse_person_list(editor_raw) if editor_raw else [],
        journal=get("journal"),
        booktitle=get("booktitle"),
        year=_to_int_or_none(get("year") or ""),
        month=get("month"),
        volume=get("volume"),
        number=get("number"),
        pages=get("pages"),
        doi=get("doi"),
        url=get("url"),
        eprint=get("eprint"),
        archive_prefix=get("archiveprefix"),
        primary_class=get("primaryclass"),
        publisher=get("publisher"),
        organization=get("organization"),
        address=get("address"),
        series=get("series"),
        edition=get("edition"),
        isbn=get("isbn"),
        issn=get("issn"),
        note=get("note"),
        raw_fields=raw_fields,
        field_order=field_order,
        source_position=src_pos,
    )
    return be


def parse_bibtex_string(text: str) -> list[BibEntry]:
    """Parse a BibTeX string. Comments and @string/@preamble are ignored."""
    lib: Library = bibtexparser.parse_string(text)
    return [_entry_to_bibentry(e) for e in lib.entries]


def parse_bibtex_file(path: str | Path) -> list[BibEntry]:
    """Parse a BibTeX file."""
    p = Path(path)
    text = p.read_text(encoding="utf-8")
    return parse_bibtex_string(text)
