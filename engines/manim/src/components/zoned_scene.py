"""engines/manim/src/components/zoned_scene.py
ZoneScene — Declarative spatial constraint system for ManimCE (thin adapter + macode_layout mixin).
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[4]
_BIN = ROOT / "bin"
if str(_BIN) not in sys.path:
    sys.path.insert(0, str(_BIN))

from macode_layout.zone_layout_mixin import ZoneLayoutMixin  # noqa: E402

from manim import *


class ZoneScene(ZoneLayoutMixin, Scene):
    """Scene base with declarative zone placement (shared logic in macode_layout)."""

    LAYOUT_PROFILE: str = "lecture_3zones"

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._layout: dict[str, Any] = {}
        self._zones: dict[str, dict[str, Any]] = {}
        self._zone_objects: dict[str, list[Any]] = {}
        self._frame_size: tuple[float, float] = (0.0, 0.0)

    def setup(self):
        super().setup()
        self._inject_component_path()
        self._zone_load_layout(self.LAYOUT_PROFILE)
        self._frame_size = self._macode_camera_dimensions()
        self._zone_setup_snapshots()

    def _inject_component_path(self):
        adapter_src = Path(__file__).parent.parent
        path_str = str(adapter_src)
        if path_str not in sys.path:
            sys.path.insert(0, path_str)

    def _macode_layouts_dir(self) -> Path:
        return Path(__file__).resolve().parent.parent / "templates" / "layouts"

    def _macode_zone_snapshot_engine(self) -> str:
        return "manim"

    def _macode_camera_dimensions(self) -> tuple[float, float]:
        return (self.camera.frame_width, self.camera.frame_height)

    def _macode_scene_clock(self) -> float:
        return float(self.renderer.time)

    def _macode_scene_fps(self) -> float:
        return float(getattr(self.camera, "fps", 30))

    def place_in_grid(
        self,
        mobjs: list[Any],
        zone_name: str,
        rows: int = 1,
        cols: int = 1,
        buff: float = 0.5,
    ) -> Any:
        group = VGroup(*mobjs)
        group.arrange_in_grid(rows=rows, cols=cols, buff=buff)
        self.place(group, zone_name, align="center")
        return group
