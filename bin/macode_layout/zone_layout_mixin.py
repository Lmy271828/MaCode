"""Shared ZoneScene orchestration (engine-agnostic hooks + layout load/snapshots)."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from macode_layout.layout_geometry import compute_position, zone_bounds
from macode_layout.layout_validator import (
    ZoneNotFoundError,
    validate_primary_zone,
    validate_zone,
)


class ZoneLayoutMixin:
    """Mixin for zone layout behaviour. Subclasses provide camera/time hooks."""

    _layout: dict[str, Any]
    _zones: dict[str, dict[str, Any]]
    _zone_objects: dict[str, list[Any]]
    _frame_size: tuple[float, float]
    LAYOUT_PROFILE: str

    # Concrete ZoneScene implements __init__ and sets *_layout/_zones/_zone_objects/_frame_size*.

    # --- hooks (implement on concrete ZoneScene) ---
    def _macode_layouts_dir(self) -> Path:
        raise NotImplementedError

    def _macode_zone_snapshot_engine(self) -> str:
        raise NotImplementedError

    def _macode_camera_dimensions(self) -> tuple[float, float]:
        raise NotImplementedError

    def _macode_scene_clock(self) -> float:
        raise NotImplementedError

    def _macode_scene_fps(self) -> float:
        return 30.0

    # --- layout ---
    def _zone_load_layout(self, profile: str) -> None:
        layouts_dir = self._macode_layouts_dir()
        path = layouts_dir / f"{profile}.json"
        if not path.exists():
            raise ZoneNotFoundError(f"Layout profile '{profile}.json' not found in {layouts_dir}")
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        self._layout = data
        self._zones = data.get("zones", {})
        self._zone_objects = {name: [] for name in self._zones}

    # --- placement API ---
    def place(
        self,
        mobj: Any,
        zone_name: str,
        align: str = "center",
        offset: Any | None = None,
    ) -> Any:
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

    def zone_center(self, zone_name: str) -> Any:
        if zone_name not in self._zones:
            raise ZoneNotFoundError(zone_name)
        return compute_position(
            self._frame_size,
            self._layout.get("canvas", [1920, 1080]),
            self._zones[zone_name],
            "center",
        )

    def zone_bounds(self, zone_name: str) -> dict[str, float]:
        if zone_name not in self._zones:
            raise ZoneNotFoundError(zone_name)
        return zone_bounds(self._frame_size, self._zones[zone_name]["rect"])

    def validate_primary_zone(self) -> None:
        validate_primary_zone(self._zones, self._zone_objects)

    # --- snapshots ---
    def _zone_setup_snapshots(self) -> None:
        kf_str = os.environ.get("MACODE_KEYFRAMES", "")
        if not kf_str:
            return
        self._snapshot_keyframes = [float(x) for x in kf_str.split(",") if x]
        self._snapshot_dir = os.environ.get("MACODE_SNAPSHOT_DIR", ".agent/tmp/snapshots")
        os.makedirs(self._snapshot_dir, exist_ok=True)
        self.add_updater(self._snapshot_updater)

    def _snapshot_updater(self, dt):  # type: ignore[no-untyped-def]
        if not getattr(self, "_snapshot_keyframes", None):
            return
        t = self._macode_scene_clock()
        fps = self._macode_scene_fps()
        for kf in list(self._snapshot_keyframes):
            if abs(t - kf) < 0.5 / fps:
                self._take_snapshot(t)
                self._snapshot_keyframes.remove(kf)

    def _take_snapshot(self, timestamp: float) -> None:
        snapshot = {
            "timestamp": round(timestamp, 2),
            "engine": self._macode_zone_snapshot_engine(),
            "canvas": list(self._frame_size),
            "objects": [],
        }
        canvas_w, canvas_h = self._frame_size

        def traverse(mobj, depth: int = 0) -> None:
            if not mobj or depth > 20:
                return
            if hasattr(mobj, "get_center"):
                cx, cy, _ = mobj.get_center()
                w = mobj.get_width()
                h = mobj.get_height()
                norm_x = (cx - w / 2 + canvas_w / 2) / canvas_w
                norm_y = (canvas_h / 2 - (cy + h / 2)) / canvas_h

                class_name = mobj.__class__.__name__
                obj_type = "unknown"
                if class_name in ("MathTex", "Tex", "TexText", "ChineseMathTex"):
                    obj_type = "formula"
                elif class_name == "Text":
                    obj_type = "text"

                snapshot["objects"].append(
                    {
                        "id": f"{getattr(mobj, 'name', class_name)}_d{depth}",
                        "type": obj_type,
                        "bbox": {
                            "x": max(0.0, min(1.0, norm_x)),
                            "y": max(0.0, min(1.0, norm_y)),
                            "w": min(1.0, w / canvas_w),
                            "h": min(1.0, h / canvas_h),
                        },
                    }
                )
            for child in getattr(mobj, "submobjects", []):
                traverse(child, depth + 1)

        for mobj in self.mobjects:
            traverse(mobj)

        path = Path(self._snapshot_dir) / "layout_snapshots.jsonl"
        with open(path, "a", encoding="utf-8") as f:
            f.write(json.dumps(snapshot, ensure_ascii=False) + "\n")
