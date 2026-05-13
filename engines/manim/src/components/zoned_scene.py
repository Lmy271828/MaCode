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
        self._setup_layout_snapshots()

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
    # ------------------------------------------------------------------
    # Layout snapshot (runtime text-overlap detection)
    # ------------------------------------------------------------------
    def _setup_layout_snapshots(self):
        """Register updater to capture layout at keyframe times.

        Activated via environment variables:
            MACODE_KEYFRAMES  - comma-separated timestamps (e.g. "0,1.5,3")
            MACODE_SNAPSHOT_DIR - output directory for layout_snapshots.jsonl
        """
        import os
        kf_str = os.environ.get('MACODE_KEYFRAMES', '')
        if not kf_str:
            return
        self._snapshot_keyframes = [float(x) for x in kf_str.split(',') if x]
        self._snapshot_dir = os.environ.get('MACODE_SNAPSHOT_DIR', '.agent/tmp/snapshots')
        os.makedirs(self._snapshot_dir, exist_ok=True)
        self.add_updater(self._snapshot_updater)

    def _snapshot_updater(self, dt):
        """Capture layout snapshot when current time crosses a keyframe."""
        if not getattr(self, '_snapshot_keyframes', None):
            return
        t = self.renderer.time
        fps = getattr(self.camera, 'fps', 30)
        for kf in list(self._snapshot_keyframes):
            if abs(t - kf) < 0.5 / fps:
                self._take_snapshot(t)
                self._snapshot_keyframes.remove(kf)

    def _take_snapshot(self, timestamp: float):
        """Write normalized layout snapshot to JSONL (recursively scans submobjects)."""
        snapshot = {
            'timestamp': round(timestamp, 2),
            'engine': 'manim',
            'canvas': list(self._frame_size),
            'objects': [],
        }
        canvas_w, canvas_h = self._frame_size

        def traverse(mobj, depth=0):
            if not mobj or depth > 20:
                return
            if hasattr(mobj, 'get_center'):
                cx, cy, _ = mobj.get_center()
                w = mobj.get_width()
                h = mobj.get_height()

                # Normalize to [0,1] with origin at top-left
                norm_x = (cx - w / 2 + canvas_w / 2) / canvas_w
                norm_y = (canvas_h / 2 - (cy + h / 2)) / canvas_h

                class_name = mobj.__class__.__name__
                obj_type = 'unknown'
                if class_name in ('MathTex', 'Tex', 'TexText', 'ChineseMathTex'):
                    obj_type = 'formula'
                elif class_name == 'Text':
                    obj_type = 'text'

                snapshot['objects'].append({
                    'id': f"{getattr(mobj, 'name', class_name)}_d{depth}",
                    'type': obj_type,
                    'bbox': {
                        'x': max(0.0, min(1.0, norm_x)),
                        'y': max(0.0, min(1.0, norm_y)),
                        'w': min(1.0, w / canvas_w),
                        'h': min(1.0, h / canvas_h),
                    },
                })

            # Recurse into submobjects (VGroup, Axes, etc.)
            for child in getattr(mobj, 'submobjects', []):
                traverse(child, depth + 1)

        for mobj in self.mobjects:
            traverse(mobj)

        path = Path(self._snapshot_dir) / 'layout_snapshots.jsonl'
        with open(path, 'a', encoding='utf-8') as f:
            f.write(json.dumps(snapshot, ensure_ascii=False) + '\n')

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
