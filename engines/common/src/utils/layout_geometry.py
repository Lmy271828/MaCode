"""Re-export: canonical implementation in ``bin/macode_layout/layout_geometry.py``."""

from __future__ import annotations

import sys
from pathlib import Path

_REPO_BIN = Path(__file__).resolve().parents[4] / "bin"
if str(_REPO_BIN) not in sys.path:
    sys.path.insert(0, str(_REPO_BIN))

from macode_layout.layout_geometry import *  # noqa: E402,F403
