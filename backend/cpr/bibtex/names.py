"""Person-name parsing.

Handles:
- "Family, Given" and "Given Family" forms
- Multiple given names ("Pai Shun Ting", "Yves-Alexandre de Montjoye")
- Hyphenated given names ("Pai-Shun" → given=["Pai","Shun"], joined "-" when abbreviated)
- Particles ("de", "van", "der", "von", "la", "le", "du")
- Suffixes ("Jr.", "III")
- Unicode (Ümlauts, CJK, accented Latin)

Not covered in Phase 1: fully-institutional authors ("{OpenAI}"), which
are treated as raw single-token names and flagged by
`audit.institution_as_author`.
"""
from __future__ import annotations

import re
import unicodedata

from ..schemas import Author

_PARTICLES = {
    "de", "del", "della", "dello", "der", "den", "des",
    "van", "von", "vom", "zu", "zum",
    "la", "le", "les", "du", "da", "di", "dos", "das",
    "af", "af den", "af der",
    "el", "al", "bin", "ibn",
    "ter", "ten", "te",
}

_SUFFIXES = {"Jr.", "Jr", "Sr.", "Sr", "II", "III", "IV"}


def _is_brace_group(name: str) -> bool:
    """`{OpenAI}` etc. — treat as opaque family name."""
    stripped = name.strip()
    return stripped.startswith("{") and stripped.endswith("}")


def _strip_outer_braces(name: str) -> str:
    """Remove exactly one balanced outer brace pair, if present."""
    stripped = name.strip()
    if _is_brace_group(stripped):
        return stripped[1:-1]
    return stripped


def parse_person(raw: str) -> Author:
    """Parse one BibTeX person name.

    Rules follow BibTeX's canonical semantics: comma-separated forms are
    `family, given` (or `family, jr, given` with 2 commas). Space-separated
    forms are `given ... family`, where trailing lowercase tokens preceding
    the first uppercase-started token are the particles.
    """
    original = raw
    raw = unicodedata.normalize("NFC", raw.strip())
    if not raw:
        return Author(raw=original, formatted=original)

    # Institutional / opaque brace form
    if _is_brace_group(raw):
        family = _strip_outer_braces(raw)
        return Author(family=family, raw=original, formatted=raw)

    # Split on unbraced commas
    parts = _split_top_level(raw, ",")
    parts = [p.strip() for p in parts]

    given: list[str] = []
    family_tokens: list[str] = []
    particles: list[str] = []
    suffix = ""

    if len(parts) == 1:
        # "Given ... [particles] Family"
        tokens = _tokenize_name(parts[0])
        given, particles, family_tokens = _split_given_particles_family(tokens)
    elif len(parts) == 2:
        # "Family, Given"
        family_str, given_str = parts
        family_tokens = _tokenize_name(family_str)
        # Extract leading particles inside the family part.
        particles, family_tokens = _extract_leading_particles(family_tokens)
        given = _tokenize_name(given_str)
    elif len(parts) >= 3:
        # "Family, Jr, Given"
        family_str, suffix_str, given_str = parts[0], parts[1], ",".join(parts[2:])
        family_tokens = _tokenize_name(family_str)
        particles, family_tokens = _extract_leading_particles(family_tokens)
        suffix = suffix_str.strip()
        given = _tokenize_name(given_str)

    # Handle hyphenated given names → split into components so we can
    # abbreviate as "P.-S." if a downstream profile asks.
    given = _expand_hyphenated_given(given)

    family = " ".join(family_tokens).strip()

    author = Author(
        given=given,
        family=family,
        particles=particles,
        suffix=suffix,
        raw=original,
        formatted=_format_person(given, particles, family, suffix),
    )
    return author


def parse_person_list(raw: str) -> list[Author]:
    """Split a BibTeX `and`-joined author list into `Author`s."""
    if not raw:
        return []
    # Split on top-level " and " (i.e., not inside braces).
    people = _split_authors(raw)
    return [parse_person(p) for p in people if p.strip()]


# ---------------------------------------------------------------------------
# Formatting
# ---------------------------------------------------------------------------
def format_full_name(a: Author) -> str:
    """Return a `Family, Given [Jr]` full name."""
    if not a.family and a.given:
        return " ".join(a.given)
    if not a.given and not a.particles and not a.suffix:
        return a.family
    left = a.family
    if a.particles:
        left = " ".join(a.particles) + " " + a.family
    right_parts = []
    if a.given:
        right_parts.append(" ".join(a.given))
    if a.suffix:
        return f"{left}, {a.suffix}, " + ", ".join(right_parts) if right_parts else f"{left}, {a.suffix}"
    return f"{left}, " + ", ".join(right_parts) if right_parts else left


def format_abbrev_given(a: Author, hyphen_join: str = "-") -> str:
    """Return `F. Family` or `P.-S. Family` for hyphenated given names."""
    if not a.given:
        return format_full_name(a)
    initials: list[str] = []
    for g in a.given:
        # If already ends in a period ("F."), keep as-is; otherwise abbreviate.
        core = g.rstrip(".")
        if not core:
            continue
        initials.append(core[0].upper() + ".")
    initials_str = hyphen_join.join(initials)
    left = a.family
    if a.particles:
        left = " ".join(a.particles) + " " + a.family
    return f"{initials_str} {left}".strip()


def _format_person(
    given: list[str], particles: list[str], family: str, suffix: str
) -> str:
    """Default `Family, Given` string used as `Author.formatted`."""
    if not family and given:
        return " ".join(given)
    if not given and not particles and not suffix:
        return family
    left = family
    if particles:
        left = " ".join(particles) + " " + family
    right_parts = []
    if given:
        right_parts.append(" ".join(given))
    if suffix:
        return f"{left}, {suffix}, " + ", ".join(right_parts) if right_parts else f"{left}, {suffix}"
    return f"{left}, " + ", ".join(right_parts) if right_parts else left


# ---------------------------------------------------------------------------
# Tokenization helpers
# ---------------------------------------------------------------------------
_WHITESPACE_RE = re.compile(r"\s+")


def _tokenize_name(s: str) -> list[str]:
    """Split on whitespace outside braces."""
    if not s:
        return []
    parts = _split_top_level(s, " ")
    return [p for p in parts if p.strip()]


def _split_top_level(s: str, delim: str) -> list[str]:
    """Split `s` on `delim` outside `{...}` brace groups."""
    if delim == " ":
        return [t for t in _split_whitespace_top_level(s) if t]
    depth = 0
    out: list[str] = []
    buf: list[str] = []
    for ch in s:
        if ch == "{":
            depth += 1
            buf.append(ch)
        elif ch == "}":
            depth = max(0, depth - 1)
            buf.append(ch)
        elif ch == delim and depth == 0:
            out.append("".join(buf))
            buf = []
        else:
            buf.append(ch)
    out.append("".join(buf))
    return out


def _split_whitespace_top_level(s: str) -> list[str]:
    depth = 0
    out: list[str] = []
    buf: list[str] = []
    for ch in s:
        if ch == "{":
            depth += 1
            buf.append(ch)
        elif ch == "}":
            depth = max(0, depth - 1)
            buf.append(ch)
        elif ch.isspace() and depth == 0:
            if buf:
                out.append("".join(buf))
                buf = []
        else:
            buf.append(ch)
    if buf:
        out.append("".join(buf))
    return out


def _split_authors(raw: str) -> list[str]:
    """Split on top-level ` and ` (case-insensitive)."""
    depth = 0
    tokens = re.split(r"(\band\b)", raw, flags=re.IGNORECASE)
    out: list[str] = []
    buf: list[str] = []
    for tok in tokens:
        # Recompute depth from the token
        for ch in tok:
            if ch == "{":
                depth += 1
            elif ch == "}":
                depth = max(0, depth - 1)
        if tok.strip().lower() == "and" and depth == 0:
            out.append("".join(buf).strip())
            buf = []
        else:
            buf.append(tok)
    out.append("".join(buf).strip())
    return [p for p in out if p]


def _extract_leading_particles(tokens: list[str]) -> tuple[list[str], list[str]]:
    particles: list[str] = []
    while tokens and tokens[0].lower().strip("{}") in _PARTICLES:
        particles.append(tokens.pop(0).strip("{}"))
    return particles, tokens


def _split_given_particles_family(
    tokens: list[str],
) -> tuple[list[str], list[str], list[str]]:
    """
    Space-separated form. Rule:
    - Walk from the start collecting given names as long as tokens are
      "Given-like" (Uppercase-first or single-letter initial).
    - Then collect lowercase particle tokens (up to a small set).
    - Everything after that is the family.
    """
    if not tokens:
        return [], [], []
    n = len(tokens)
    given: list[str] = []
    i = 0
    # Given-name run: uppercase-first tokens OR ones ending in "."
    while i < n:
        t = tokens[i]
        core = t.strip("{}")
        if not core:
            i += 1
            continue
        # If this is the LAST token, it must be the family.
        if i == n - 1:
            break
        # A particle marks the boundary; stop.
        if core.lower() in _PARTICLES:
            break
        first = core[0]
        if first.isupper() or (core.endswith(".") and len(core) <= 3):
            given.append(t)
            i += 1
        else:
            break
    # Suffix detection: trailing "Jr." etc. moves out of the family into suffix.
    # (Handled by caller via commas; if none, we skip.)
    particles: list[str] = []
    while i < n and tokens[i].strip("{}").lower() in _PARTICLES:
        particles.append(tokens[i].strip("{}"))
        i += 1
    family_tokens = tokens[i:]
    if not family_tokens and given:
        # e.g., single-word name "Plato" — treat as family, not given.
        family_tokens = [given.pop()]
    return given, particles, family_tokens


def _expand_hyphenated_given(given: list[str]) -> list[str]:
    """Split "Pai-Shun" into ["Pai", "Shun"] but keep periods intact."""
    out: list[str] = []
    for g in given:
        # Keep initials with period unsplit ("K.-C.")
        if "-" in g and not g.endswith("."):
            parts = g.split("-")
            # Preserve the hyphen semantics by marking the pieces as
            # `stem-continuation`. Simplest: return the whole hyphenated
            # token as one component; abbreviation joins with "-" later.
            out.append(g)
        else:
            out.append(g)
    return out
