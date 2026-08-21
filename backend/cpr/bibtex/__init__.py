"""BibTeX layer: text ↔ typed entries."""
from .parser import parse_bibtex_file, parse_bibtex_string
from .writer import write_entries
from .identity import extract_identity, normalize_title
from .names import parse_person, parse_person_list

__all__ = [
    "parse_bibtex_file",
    "parse_bibtex_string",
    "write_entries",
    "extract_identity",
    "normalize_title",
    "parse_person",
    "parse_person_list",
]
