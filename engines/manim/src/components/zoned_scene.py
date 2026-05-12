"""engines/manim/src/components/zoned_scene.py
ZoneScene — Declarative spatial constraint system for ManimCE.

Mirrors the ManimGL version with ManimCE-compatible imports.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

from manim import *
from utils.layout_geometry import compute_position
from utils.layout_validator import (
    ZoneNotFoundError,
    validate_primary_zone,
    validate_zone,
)


class ZoneScene(Scene):
    """Scene base class with declarative zone-based placement.

    Subclasses override :attr:`LAYOUT_PROFILE` to select a layout template
    from ``engines/manim/src/templates/layouts/``.
    """

    LAYOUT_PROFILE: str = "lecture_3zones"

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._layout: dict[str, Any] = {}
        self._zones: dict[str, dict[str, Any]] = {}
        self._zone_objects: dict[str, list[Mobject]] = {}
        self._frame_size: tuple[float, float] = (0.0, 0.0)

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------
    def setup(self):
        """Load layout profile and initialise zone registries."""
        super().setup()
        self._inject_component_path()
        self._load_layout(self.LAYOUT_PROFILE)
        self._frame_size = (
            self.camera.frame_width,
            self.camera.frame_height,
        )

    def _inject_component_path(self):
        """Ensure engines/manim/src/ is on *sys.path*."""
        adapter_src = Path(__file__).parent.parent
        path_str = str(adapter_src)
        if path_str not in sys.path:
            sys.path.insert(0, path_str)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def place(
        self,
        mobj: Mobject,
        zone_name: str,
        align: str = "center",
        offset: np.ndarray | None = None,
    ) -> Mobject:
        """Place *mobj* into *zone_name* according to the loaded layout."""
        if zone_name not in self._zones:
            raise ZoneNotFoundError(
                f"Zone '{zone_name}' not found in layout '{self.LAYOUT_PROFILE}'. "
                f"Available: {list(self._zones.keys())}"
            )

        zone = self._zones[zone_name]
        validate_zone(zone_name, mobj, zone, self._zone_objects)

        pos = compute_position(
            self._frame_size,
            self._layout.get("canvas", [1920, 1080]),
            zone,
            align,
        )
        if offset is not None:
            pos += offset

        mobj.move_to(pos)
        self._zone_objects[zone_name].append(mobj)
        return mobj

    def place_in_grid(
        self,
        mobjs: list[Mobject],
        zone_name: str,
        rows: int = 1,
        cols: int = 1,
        buff: float = 0.5,
    ) -> VGroup:
        """Arrange multiple mobjects in a grid inside *zone_name*."""
        group = VGroup(*mobjs)
        group.arrange_in_grid(rows=rows, cols=cols, buff=buff)
        self.place(group, zone_name, align="center")
        return group

    def zone_center(self, zone_name: str) -> np.ndarray:
        """Return the centre point of *zone_name* in Manim coordinates."""
        if zone_name not in self._zones:
            raise ZoneNotFoundError(zone_name)
        return compute_position(
            self._frame_size,
            self._layout.get("canvas", [1920, 1080]),
            self._zones[zone_name],
            "center",
        )

    def zone_bounds(self, zone_name: str) -> dict[str, float]:
        """Return pixel-like bounds of *zone_name*."""
        if zone_name not in self._zones:
            raise ZoneNotFoundError(zone_name)
        from utils.layout_geometry import zone_bounds

        return zone_bounds(self._frame_size, self._zones[zone_name]["rect"])

    def validate_primary_zone(self) -> None:
        """Check that the primary zone contains at least one non-text visual."""
        validate_primary_zone(self._zones, self._zone_objects)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    def _load_layout(self, profile: str) -> None:
        """Load a JSON layout profile from *templates/layouts/*."""
        layouts_dir = Path(__file__).parent.parent / "templates" / "layouts"
        path = layouts_dir / f"{profile}.json"
        if not path.exists():
            raise ZoneNotFoundError(
                f"Layout profile '{profile}.json' not found in {layouts_dir}"
            )

        with open(path, encoding="utf-8") as f:
            data = json.load(f)

        self._layout = data
        self._zones = data.get("zones", {})
        self._zone_objects = {name: [] for name in self._zones}
