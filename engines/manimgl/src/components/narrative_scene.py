"""engines/manimgl/src/components/narrative_scene.py
NarrativeScene — ManimGL (thin adapter + macode_layout narrative mixin).
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[4]
_BIN = ROOT / "bin"
if str(_BIN) not in sys.path:
    sys.path.insert(0, str(_BIN))

from macode_layout.narrative_mixin import NarrativeSceneMixin  # noqa: E402

from components.zoned_scene import ZoneScene
from manimlib import *


class NarrativeScene(NarrativeSceneMixin, ZoneScene):
    """Narrative staging; shared logic in macode_layout."""

    NARRATIVE_PROFILE: str = "definition_reveal"

    CREATION_ANIM = ShowCreation
    FADEIN_ANIM = FadeIn
    WRITE_ANIM = Write

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._narrative: dict[str, Any] = {}
        self._stages_played: set[str] = set()
        self._stage_start_times: dict[str, float] = {}
        self._narrative_time_origin: float = 0.0

    def _macode_narratives_dir(self) -> Path:
        return Path(__file__).resolve().parent.parent / "templates" / "narratives"
