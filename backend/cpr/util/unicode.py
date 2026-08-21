"""Unicode utilities: NFC normalization + minimal LaTeX ↔ Unicode."""
from __future__ import annotations

import re
import unicodedata


_LATEX_TO_UNICODE = {
    r"\'{a}": "á", r"\'{e}": "é", r"\'{i}": "í", r"\'{o}": "ó", r"\'{u}": "ú",
    r"\'{A}": "Á", r"\'{E}": "É", r"\'{I}": "Í", r"\'{O}": "Ó", r"\'{U}": "Ú",
    r'\"{a}': "ä", r'\"{o}': "ö", r'\"{u}': "ü", r'\"{A}': "Ä", r'\"{O}': "Ö", r'\"{U}': "Ü",
    r"\`{a}": "à", r"\`{e}": "è", r"\`{i}": "ì", r"\`{o}": "ò", r"\`{u}": "ù",
    r"\^{a}": "â", r"\^{e}": "ê", r"\^{i}": "î", r"\^{o}": "ô", r"\^{u}": "û",
    r"\~{n}": "ñ", r"\~{N}": "Ñ",
    r"\c{c}": "ç", r"\c{C}": "Ç",
    r"\ss": "ß",
    r"\'a": "á", r"\'e": "é", r"\'i": "í", r"\'o": "ó", r"\'u": "ú",
    r"\`a": "à", r"\`e": "è", r"\`i": "ì", r"\`o": "ò", r"\`u": "ù",
}

_UNICODE_TO_LATEX = {v: k for k, v in _LATEX_TO_UNICODE.items() if not k.startswith(r"\'a")}


def to_unicode(text: str) -> str:
    """Convert `\"{u}` style TeX escapes to Unicode. Fully idempotent on pure Unicode."""
    if not text:
        return text
    for tex, uni in _LATEX_TO_UNICODE.items():
        text = text.replace(tex, uni)
    return unicodedata.normalize("NFC", text)


def to_latex(text: str) -> str:
    """Convert Unicode accented characters to LaTeX escape sequences."""
    if not text:
        return text
    out = []
    for ch in text:
        out.append(_UNICODE_TO_LATEX.get(ch, ch))
    return "".join(out)


def nfc(text: str) -> str:
    """NFC normalize a string."""
    if not text:
        return text
    return unicodedata.normalize("NFC", text)
