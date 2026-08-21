"""Verification / export module.

`classify_entry()` decides whether a corrected entry qualifies for the
strict `.verified.bib` output, or should land in `.needs-review.bib`
with an explanatory note. `export_bib()` runs the full pipeline end-to-
end and writes the three companion files.
"""
from .exporter import ExportResult, EntryClassification, classify_entry, export_bib

__all__ = ["ExportResult", "EntryClassification", "classify_entry", "export_bib"]
