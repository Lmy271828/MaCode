"""engines/manimgl/src/utils/timeline_helper.py
MaCode keyframe / timeline builder — provides interpolation and export for animation parameters.

Usage::

    from utils.timeline_helper import Timeline, Keyframe

    timeline = Timeline()
    timeline.add(Keyframe(t=0.0, value=0, ease="linear"))
    timeline.add(Keyframe(t=1.0, value=1, ease="ease_in_out"))
    timeline.add(Keyframe(t=3.0, value=0.5, ease="ease_out"))

    v = timeline.at(1.5)   # interpolated result

    # Export CSV (for external tools like ffmpeg)
    timeline.to_csv("keyframes.csv", fps=30)

    # Use in Manim updater
    def updater(mobject, dt):
        mobject.set_opacity(timeline.at(scene.time))
"""

import csv
import math
from collections.abc import Callable
from dataclasses import dataclass

# ------------------------------------------------------------------
# 1. Easing functions
# ------------------------------------------------------------------

def _ease_linear(t: float) -> float:
    return t


def _ease_in(t: float) -> float:
    return t * t


def _ease_out(t: float) -> float:
    return 1 - (1 - t) * (1 - t)


def _ease_in_out(t: float) -> float:
    """Smoothstep variant."""
    if t < 0.5:
        return 2 * t * t
    else:
        return 1 - math.pow(-2 * t + 2, 2) / 2


def _ease_step(t: float) -> float:
    """Step function: returns 0 if t < 1, else 1 (for discrete switching)."""
    return 0.0 if t < 1.0 else 1.0


_EASING_MAP: dict[str, Callable[[float], float]] = {
    "linear": _ease_linear,
    "ease_in": _ease_in,
    "ease_out": _ease_out,
    "ease_in_out": _ease_in_out,
    "step": _ease_step,
}


def _interpolate(a: float, b: float, t: float) -> float:
    """Linear interpolation."""
    return a + (b - a) * t


# ------------------------------------------------------------------
# 2. Keyframe
# ------------------------------------------------------------------

@dataclass
class Keyframe:
    """Single keyframe.

    Attributes:
        t: time in seconds
        value: target value (float)
        ease: easing name, see keys of ``_EASING_MAP``
    """
    t: float
    value: float
    ease: str = "linear"

    def __post_init__(self):
        if self.ease not in _EASING_MAP:
            raise ValueError(f"Unknown ease '{self.ease}'. Supported: {list(_EASING_MAP.keys())}")


# ------------------------------------------------------------------
# 3. Timeline
# ------------------------------------------------------------------

class Timeline:
    """Ordered keyframe collection, supports sampling at arbitrary times and CSV export."""

    def __init__(self):
        self._frames: list[Keyframe] = []

    def add(self, keyframe: Keyframe) -> "Timeline":
        """Add keyframe and auto-sort by time.

        Supports chaining::

            timeline.add(Keyframe(...)).add(Keyframe(...))
        """
        self._frames.append(keyframe)
        self._frames.sort(key=lambda k: k.t)
        return self

    def clear(self) -> "Timeline":
        """Clear all keyframes."""
        self._frames.clear()
        return self

    def at(self, t: float) -> float:
        """Sample interpolated value at time *t*.

        - If *t* is before the first frame, returns first frame's value.
        - If *t* is after the last frame, returns last frame's value.
        - Otherwise interpolates between two frames using easing function.

        Args:
            t: sample time in seconds

        Returns:
            float: interpolated result
        """
        if not self._frames:
            return 0.0

        if t <= self._frames[0].t:
            return self._frames[0].value
        if t >= self._frames[-1].t:
            return self._frames[-1].value

        # Find interval
        for i in range(len(self._frames) - 1):
            k0 = self._frames[i]
            k1 = self._frames[i + 1]
            if k0.t <= t <= k1.t:
                if k1.t == k0.t:
                    return k1.value
                local_t = (t - k0.t) / (k1.t - k0.t)
                eased_t = _EASING_MAP[k0.ease](local_t)
                return _interpolate(k0.value, k1.value, eased_t)

        # Fallback
        return self._frames[-1].value

    def to_csv(self, path: str, fps: int = 30, end_t: float | None = None) -> None:
        """Sample timeline into CSV file.

        Args:
            path: output file path
            fps: sample frame rate
            end_t: end time; defaults to last keyframe's time
        """
        if not self._frames:
            return

        duration = end_t if end_t is not None else self._frames[-1].t
        frame_count = max(1, int(math.ceil(duration * fps)) + 1)

        with open(path, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(["frame", "time", "value"])
            for i in range(frame_count):
                t = i / fps
                writer.writerow([i, f"{t:.6f}", f"{self.at(t):.6f}"])

    def __len__(self) -> int:
        return len(self._frames)

    def __repr__(self) -> str:
        frames = ", ".join(f"({k.t}, {k.value}, {k.ease})" for k in self._frames)
        return f"Timeline([{frames}])"
