"""Pure geometry utilities for zone-based layout.

No dependency on manimlib/manim — operates on plain numbers and numpy.
"""

from __future__ import annotations

from typing import Any

import numpy as np


def px_per_unit(frame_width: float, canvas_width: float) -> float:
    """Convert pixels to Manim world units."""
    return frame_width / canvas_width


def zone_bounds(
    frame_size: tuple[float, float],
    rect: list[float],
) -> dict[str, float]:
    """Convert a normalised zone rect to Manim world coordinates."""
    nx, ny, nw, nh = rect
    fw, fh = frame_size

    left = -fw / 2 + nx * fw
    right = left + nw * fw
    top = fh / 2 - ny * fh
    bottom = top - nh * fh

    return {"left": left, "right": right, "top": top, "bottom": bottom}


def compute_position(
    frame_size: tuple[float, float],
    canvas: list[float],
    zone: dict[str, Any],
    align: str = "center",
) -> np.ndarray:
    """Calculate a placement point inside *zone* respecting padding."""
    bounds = zone_bounds(frame_size, zone["rect"])
    padding = zone.get("padding", [0, 0, 0, 0])
    if isinstance(padding, (int, float)):
        padding = [padding, padding, padding, padding]

    scale = px_per_unit(frame_size[0], canvas[0])
    pl, pt, pr, pb = [p * scale for p in padding]

    effective_left = bounds["left"] + pl
    effective_right = bounds["right"] - pr
    effective_top = bounds["top"] - pt
    effective_bottom = bounds["bottom"] + pb

    cx = (effective_left + effective_right) / 2
    cy = (effective_top + effective_bottom) / 2

    if align == "center":
        return np.array([cx, cy, 0])
    if align == "top":
        return np.array([cx, effective_top, 0])
    if align == "bottom":
        return np.array([cx, effective_bottom, 0])
    if align == "left":
        return np.array([effective_left, cy, 0])
    if align == "right":
        return np.array([effective_right, cy, 0])
    return np.array([cx, cy, 0])
