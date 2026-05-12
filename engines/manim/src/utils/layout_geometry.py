"""engines/manimgl/src/utils/layout_geometry.py
Pure geometry utilities for zone-based layout.

No dependency on manimlib/manim — operates on plain numbers and numpy.
"""

from __future__ import annotations

from typing import Any

import numpy as np


def px_per_unit(frame_width: float, canvas_width: float) -> float:
    """Convert pixels to Manim world units.

    Args:
        frame_width: Width of the camera frame in Manim units.
        canvas_width: Width of the logical canvas in pixels.

    Returns:
        Scaling factor (pixels → Manim units).
    """
    return frame_width / canvas_width


def zone_bounds(
    frame_size: tuple[float, float],
    rect: list[float],
) -> dict[str, float]:
    """Convert a normalised zone rect to Manim world coordinates.

    Args:
        frame_size: (width, height) of the camera frame in Manim units.
        rect: Normalised rectangle [nx, ny, nw, nh] where origin is
            top-left and y points down.

    Returns:
        Dictionary with keys ``left``, ``right``, ``top``, ``bottom``
        in Manim coordinates (origin centre, y up).
    """
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
    """Calculate a placement point inside *zone* respecting padding.

    Args:
        frame_size: (width, height) of the camera frame.
        canvas: [width, height] of the logical canvas in pixels.
        zone: Zone dictionary containing ``rect`` and optional ``padding``.
        align: One of ``center`` (default), ``top``, ``bottom``,
            ``left``, ``right``.

    Returns:
        3D numpy array representing the position in Manim coordinates.
    """
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
    elif align == "top":
        return np.array([cx, effective_top, 0])
    elif align == "bottom":
        return np.array([cx, effective_bottom, 0])
    elif align == "left":
        return np.array([effective_left, cy, 0])
    elif align == "right":
        return np.array([effective_right, cy, 0])
    else:
        return np.array([cx, cy, 0])
