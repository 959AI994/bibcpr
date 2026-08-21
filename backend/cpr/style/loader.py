"""YAML → StyleProfile loader."""
from __future__ import annotations

from pathlib import Path

import yaml

from .profile import StyleProfile


def load_profile(path: str | Path) -> StyleProfile:
    """Load a `StyleProfile` from a YAML file."""
    p = Path(path)
    data = yaml.safe_load(p.read_text(encoding="utf-8"))
    return StyleProfile.model_validate(data)
