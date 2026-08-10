"""Portrait file serving helpers — path-traversal-safe local URLs.

Lesson 13 (Linear Algebra Intuition) artifact: the FAL portrait pipeline
writes creature art into data/creatures/ (registry + content-addressed PNGs).
The TMA renders those PNGs through a single /creature-art route; these
helpers keep URL building and path sanitisation pure so they can be unit
tested offline (the Reflex module itself is never imported by tests — see
tests/test_iter6_regression.py for that convention).

Filenames are content-addressed (blake2b → 32 hex chars) and immutable, so
a long Cache-Control on the route is safe.
"""

from __future__ import annotations

import os
import re
from pathlib import Path

# portrait_<32 hex>.png | thumb_<32 hex>.png — nothing else is servable.
_PORTRAIT_RE = re.compile(r"^(portrait|thumb)_[0-9a-f]{32}\.png$")


def creature_art_url(path_or_name: str) -> str:
    """Local /creature-art URL for a portrait file ('' when not resolvable)."""
    name = os.path.basename(str(path_or_name))
    if _PORTRAIT_RE.match(name):
        return f"/creature-art?name={name}"
    return ""


def portrait_file_path(name: str, data_dir: str = "data") -> Path | None:
    """Resolve a portrait name under data_dir/creatures (traversal-safe).

    Returns None for names that are not valid portrait filenames, resolve
    outside the creatures dir, or do not exist on disk.
    """
    if not _PORTRAIT_RE.match(str(name)):
        return None
    base = (Path(data_dir) / "creatures").resolve()
    fp = (base / name).resolve()
    if not str(fp).startswith(str(base) + os.sep):
        return None
    if not fp.is_file():
        return None
    return fp
