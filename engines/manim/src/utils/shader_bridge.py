"""engines/manim/src/utils/shader_bridge.py
MaCode Shader Bridge for ManimCE — embed shader assets as Mobjects.

Consumes Layer 1 (PNG frame sequences) produced by ``bin/shader-render.py``.
If Layer 1 does not exist, optionally triggers headless rendering from Layer 2.

Usage in a ManimCE scene::

    from utils.shader_bridge import ShaderMobject

    class MyScene(MaCodeScene):
        def construct(self):
            # Reference pre-rendered frames
            shader = ShaderMobject("assets/shaders/noise_heatmap/")
            self.play(FadeIn(shader))
            self.wait(3)
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

import numpy as np
from manim import ImageMobject
from PIL import Image


class ShaderMobject(ImageMobject):
    """Embed a shader asset into a ManimCE scene as an ImageMobject.

    The shader animation is driven by an updater that syncs with the
    scene's elapsed time. Frames are loaded lazily (one at a time) to
    keep memory usage bounded.

    Args:
        shader_path: path to the shader asset directory (contains shader.json)
        render: if True, trigger headless rendering when frames/ are missing
        duration: override rendering duration (seconds)
        fps: override rendering fps
        loop: whether the shader animation loops (default True)
    """

    def __init__(
        self,
        shader_path: str,
        render: bool = False,
        duration: float | None = None,
        fps: float | None = None,
        loop: bool = True,
        **kwargs: Any,
    ):
        self._shader_path = Path(shader_path).resolve()
        self._shader_json = self._load_shader_json()
        self._loop = loop
        self._render_triggered = False

        # Auto-render Layer 2 → Layer 1 if frames are missing
        if render or not self._has_prerendered_frames():
            self._prerender(duration=duration, fps=fps)

        first_frame = self._get_frame_path(0)
        if not first_frame.exists():
            raise FileNotFoundError(
                f"No frames found for shader {self._shader_path}. "
                f"Run with render=True or use bin/shader-render.py first."
            )

        super().__init__(str(first_frame), **kwargs)

        # Time-driven frame updater
        self.add_updater(self._frame_updater)

    # ------------------------------------------------------------------
    # Data loading
    # ------------------------------------------------------------------
    def _load_shader_json(self) -> dict:
        json_path = self._shader_path / "shader.json"
        with open(json_path, encoding="utf-8") as f:
            return json.load(f)

    def _frames_dir(self) -> Path:
        return self._shader_path / "frames"

    def _has_prerendered_frames(self) -> bool:
        frames_dir = self._frames_dir()
        if not frames_dir.exists():
            return False
        return any(frames_dir.glob("frame_*.png"))

    def _get_frame_path(self, idx: int) -> Path:
        """Return path to frame N (1-based index in filename)."""
        return self._frames_dir() / f"frame_{idx + 1:04d}.png"

    def _get_total_frames(self) -> int:
        """Count existing frame files."""
        return len(list(self._frames_dir().glob("frame_*.png")))

    # ------------------------------------------------------------------
    # Headless rendering (Layer 2 → Layer 1)
    # ------------------------------------------------------------------
    def _prerender(self, duration: float | None, fps: float | None):
        """Trigger bin/shader-render.py to compile frames."""
        if self._render_triggered:
            return
        self._render_triggered = True

        project_root = self._shader_path.parents[2]  # assets/shaders/name → project root
        render_script = project_root / "bin" / "shader-render.py"

        render_cfg = self._shader_json.get("render", {})
        dur = duration or render_cfg.get("duration", 3.0)
        _fps = fps or render_cfg.get("fps", 30)
        res = render_cfg.get("resolution", [1920, 1080])
        res_str = f"{res[0]}x{res[1]}"

        cmd = [
            sys.executable,
            str(render_script),
            str(self._shader_path),
            "--output", str(self._frames_dir()),
            "--fps", str(_fps),
            "--duration", str(dur),
            "--resolution", res_str,
        ]

        env = os.environ.copy()
        manimgl_src = str(project_root / "engines" / "manimgl" / "src")
        env["PYTHONPATH"] = manimgl_src + os.pathsep + env.get("PYTHONPATH", "")

        try:
            subprocess.run(cmd, env=env, check=True, capture_output=True, text=True)
        except subprocess.CalledProcessError as exc:
            raise RuntimeError(
                f"Shader pre-rendering failed for {self._shader_path}:\n"
                f"stdout: {exc.stdout}\nstderr: {exc.stderr}"
            ) from exc

    # ------------------------------------------------------------------
    # Updater
    # ------------------------------------------------------------------
    def _frame_updater(self, mob, dt: float):
        """Called every frame by Manim. Sync shader animation with elapsed dt."""
        if not hasattr(self, "_elapsed"):
            self._elapsed = 0.0
        self._elapsed += dt
        frame_idx = self._time_to_frame(self._elapsed)

        frame_path = self._get_frame_path(frame_idx)
        if frame_path.exists():
            # Lazy load: read from disk, convert to numpy, assign pixel_array
            img = Image.open(frame_path).convert("RGBA")
            self.pixel_array = np.array(img)

    def _time_to_frame(self, t: float) -> int:
        """Map elapsed time to frame index."""
        render_cfg = self._shader_json.get("render", {})
        _fps = render_cfg.get("fps", 30)
        total = self._get_total_frames()
        if total == 0:
            return 0
        frame = int(t * _fps)
        return frame % total if self._loop else min(frame, total - 1)

    # ------------------------------------------------------------------
    # Public controls
    # ------------------------------------------------------------------
    def set_loop(self, loop: bool) -> ShaderMobject:
        self._loop = loop
        return self

    def seek_to_time(self, t: float) -> ShaderMobject:
        """Jump to a specific time in the shader animation."""
        self._elapsed = t
        frame_idx = self._time_to_frame(t)
        frame_path = self._get_frame_path(frame_idx)
        if frame_path.exists():
            img = Image.open(frame_path).convert("RGBA")
            self.pixel_array = np.array(img)
        return self
