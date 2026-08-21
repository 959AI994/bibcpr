"""BibTeX writer.

We write our own BibTeX serializer rather than round-trip through
bibtexparser v2, so we have deterministic field-ordering, brace policy
and Unicode strategy exactly matching the loaded `StyleProfile`.
"""
from __future__ import annotations

from typing import Iterable

from ..schemas import Author, BibEntry


def _needs_braces(value: str) -> bool:
    """A value needs `{...}` if it contains commas, spaces, or non-ASCII."""
    if not value:
        return True
    if "," in value or " " in value:
        return True
    # Preserve capitalization for anything containing uppercase mid-string
    return not value.isdigit()


def _wrap(value: str) -> str:
    if value is None:
        return "{}"
    # Never double-wrap: if user already has balanced outer braces, keep as-is.
    v = value.strip()
    if v.startswith("{") and v.endswith("}"):
        return v
    return "{" + v + "}"


def _format_authors(authors: list[Author]) -> str:
    parts: list[str] = []
    for a in authors:
        # Prefer canonical `Family, Given`; fall back to raw string.
        if a.family or a.given:
            left = a.family
            if a.particles:
                left = " ".join(a.particles) + " " + a.family
            right_bits: list[str] = []
            if a.given:
                right_bits.append(" ".join(a.given))
            if a.suffix:
                if right_bits:
                    parts.append(f"{left}, {a.suffix}, {', '.join(right_bits)}")
                else:
                    parts.append(f"{left}, {a.suffix}")
            elif right_bits:
                parts.append(f"{left}, {', '.join(right_bits)}")
            else:
                parts.append(left)
        else:
            parts.append(a.raw or a.formatted)
    return " and ".join(parts)


# Map (BibEntry attribute) → canonical BibTeX field name we emit
_ATTR_TO_FIELD: list[tuple[str, str, callable | None]] = [
    ("authors", "author", lambda v: _format_authors(v) if v else None),
    ("editors", "editor", lambda v: _format_authors(v) if v else None),
    ("title", "title", None),
    ("booktitle", "booktitle", None),
    ("journal", "journal", None),
    ("year", "year", lambda v: str(v) if v is not None else None),
    ("month", "month", None),
    ("volume", "volume", None),
    ("number", "number", None),
    ("pages", "pages", None),
    ("publisher", "publisher", None),
    ("organization", "organization", None),
    ("address", "address", None),
    ("series", "series", None),
    ("edition", "edition", None),
    ("isbn", "isbn", None),
    ("issn", "issn", None),
    ("doi", "doi", None),
    ("url", "url", None),
    ("eprint", "eprint", None),
    ("archive_prefix", "archivePrefix", None),
    ("primary_class", "primaryClass", None),
    ("note", "note", None),
]

_FIELD_TO_ATTR: dict[str, tuple[str, callable | None]] = {
    field.lower(): (attr, fmt) for attr, field, fmt in _ATTR_TO_FIELD
}
# camelCase alias
_FIELD_TO_ATTR["archiveprefix"] = ("archive_prefix", None)
_FIELD_TO_ATTR["primaryclass"] = ("primary_class", None)


def _get_field_value(entry: BibEntry, field_name: str) -> str | None:
    key = field_name.lower()
    if key in _FIELD_TO_ATTR:
        attr, fmt = _FIELD_TO_ATTR[key]
        raw_val = getattr(entry, attr, None)
        if fmt is not None:
            return fmt(raw_val)
        if raw_val is None or raw_val == "":
            return None
        return str(raw_val)
    # Unknown field: check raw_fields
    return entry.raw_fields.get(field_name) or entry.raw_fields.get(key)


def write_entry(
    entry: BibEntry,
    field_order: list[str] | None = None,
    drop_if_empty: Iterable[str] = (),
    canonical_field_case: dict[str, str] | None = None,
) -> str:
    """Serialize a single BibEntry to BibTeX text.

    `field_order` is the preferred order from the StyleProfile. Fields
    absent from it are appended in their original parse order.
    """
    canonical_field_case = canonical_field_case or {}
    lines: list[str] = []
    lines.append(f"@{entry.entry_type}{{{entry.key},")

    # Determine ordering: profile order first (only if the value is present),
    # then any remaining fields from entry.field_order not yet emitted, then
    # any known attribute fields we still haven't emitted.
    emitted: set[str] = set()
    ordered_fields: list[str] = []

    for f in field_order or []:
        if f.lower() in emitted:
            continue
        val = _get_field_value(entry, f)
        if val is None and f.lower() in {x.lower() for x in drop_if_empty}:
            emitted.add(f.lower())
            continue
        if val is None:
            emitted.add(f.lower())
            continue
        ordered_fields.append(f)
        emitted.add(f.lower())

    for f in entry.field_order:
        if f.lower() in emitted:
            continue
        val = _get_field_value(entry, f)
        if val is None and f.lower() in {x.lower() for x in drop_if_empty}:
            emitted.add(f.lower())
            continue
        if val is None:
            emitted.add(f.lower())
            continue
        ordered_fields.append(f)
        emitted.add(f.lower())

    # Any known-attribute fields we still haven't emitted but which have
    # values (e.g., because entry.field_order came from a partially-populated
    # source) — emit these last, in canonical order.
    for attr, canonical_field, fmt in _ATTR_TO_FIELD:
        if canonical_field.lower() in emitted:
            continue
        val = _get_field_value(entry, canonical_field)
        if val is None:
            continue
        ordered_fields.append(canonical_field)
        emitted.add(canonical_field.lower())

    # Now emit
    inner: list[str] = []
    for f in ordered_fields:
        val = _get_field_value(entry, f)
        if val is None:
            continue
        canonical = canonical_field_case.get(f.lower(), f)
        # Numeric year: no braces
        if f.lower() == "year" and val.isdigit():
            inner.append(f"  {canonical} = {val}")
        else:
            inner.append(f"  {canonical} = {_wrap(val)}")

    lines.append(",\n".join(inner))
    lines.append("}")
    return "\n".join(lines)


def write_entries(
    entries: Iterable[BibEntry],
    field_order: list[str] | None = None,
    drop_if_empty: Iterable[str] = (),
) -> str:
    canonical_case = {
        "archiveprefix": "archivePrefix",
        "primaryclass": "primaryClass",
    }
    chunks: list[str] = []
    for e in entries:
        chunks.append(write_entry(
            e,
            field_order=field_order,
            drop_if_empty=drop_if_empty,
            canonical_field_case=canonical_case,
        ))
    return "\n\n".join(chunks) + "\n"
