"""Resolver layer: evidence records → canonical publication."""
from .canonical import build_canonical
from .conflicts import detect_conflicts, resolve_conflict
from .confidence import classify_confidence

__all__ = [
    "build_canonical",
    "detect_conflicts",
    "resolve_conflict",
    "classify_confidence",
]
