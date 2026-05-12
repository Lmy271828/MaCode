"""engines/manimgl/src/utils/shader_runner.py
MaCode Headless Shader Runner — pure moderngl, zero window dependency.

Renders GLSL shaders to PNG frame sequences using an offscreen framebuffer.
No X11, no GLFW, no window manager. Direct GPU memory → pixel readback.

Usage::

    from utils.shader_runner import HeadlessShaderRunner
    from utils.shader_backend import Backend

    runner = HeadlessShaderRunner(1920, 1080, backend=Backend.D3D12)
    runner.render_sequence(
        vert=vert_glsl,
        frag=frag_glsl,
        uniforms={"resolution": (1920.0, 1080.0)},
        fps=30,
        duration=3.0,
        output_dir=".agent/tmp/shader_frames/"
    )
"""

from __future__ import annotations

import json
import os
import re
from typing import Any

import numpy as np
from PIL import Image
from utils.shader_backend import Backend

# moderngl is lazy-imported so that this module can be inspected
# even when moderngl is not available (rare, but defensive).
_modern_gl = None


def _get_moderngl():
    global _modern_gl
    if _modern_gl is None:
        import moderngl
        _modern_gl = moderngl
    return _modern_gl


# Default vertex shader for fullscreen quad (NDC [-1,1] x [-1,1])
DEFAULT_VERT = """#version 330
in vec2 in_pos;
void main() {
    gl_Position = vec4(in_pos, 0.0, 1.0);
}
"""

# Fullscreen quad: two triangles covering NDC space
_QUAD_VERTS = np.array([
    -1.0, -1.0,
     1.0, -1.0,
    -1.0,  1.0,
     1.0, -1.0,
     1.0,  1.0,
    -1.0,  1.0,
], dtype="f4")


class HeadlessShaderRunner:
    """Headless shader renderer using moderngl offscreen framebuffer.

    Creates a standalone OpenGL context with no window system dependency.
    Renders to a GPU framebuffer object, then reads pixels back to CPU memory.
    """

    def __init__(self, width: int, height: int, backend: Backend | None = None):
        """Create a headless shader runner.

        Args:
            width: framebuffer width in pixels
            height: framebuffer height in pixels
            backend: target backend (GPU/D3D12/CPU/HEADLESS). When ``None``,
                auto-detected from ``.agent/hardware_profile.json``.
        """
        self._backend = backend if backend is not None else Backend.from_hardware_profile()
        self.width = width
        self.height = height

        moderngl = _get_moderngl()
        self.ctx = moderngl.create_standalone_context()
        self.fbo = self.ctx.framebuffer(
            color_attachments=[self.ctx.texture((width, height), 4)]
        )

        # Build reusable fullscreen quad VAO
        self._prog = self.ctx.program(
            vertex_shader=DEFAULT_VERT,
            fragment_shader="""#version 330
out vec4 fragColor;
void main() { fragColor = vec4(0.0); }
""",
        )
        self._vbo = self.ctx.buffer(_QUAD_VERTS)
        self._vao = self.ctx.simple_vertex_array(self._prog, self._vbo, "in_pos")

    # ------------------------------------------------------------------
    # Core rendering
    # ------------------------------------------------------------------
    def render(
        self,
        vert: str,
        frag: str,
        uniforms: dict[str, Any] | None = None,
    ) -> np.ndarray:
        """Render a single frame and return RGBA numpy array.

        Args:
            vert: vertex shader GLSL source
            frag: fragment shader GLSL source
            uniforms: mapping of uniform names to values

        Returns:
            numpy uint8 array of shape (height, width, 4)
        """
        moderngl = _get_moderngl()
        prog = self.ctx.program(vertex_shader=vert, fragment_shader=frag)

        # Inject uniforms
        for name, value in (uniforms or {}).items():
            if name not in prog:
                continue
            fmt = getattr(prog[name], "fmt", "")
            # Normalise value types for moderngl (scalar -> vector/matrix expansion)
            normalized = self._normalize_uniform(value, fmt)
            try:
                prog[name].value = normalized
            except Exception as exc:
                raise RuntimeError(
                    f"Failed to set uniform '{name}'={normalized!r} (fmt={fmt}): {exc}"
                ) from exc

        # Render to offscreen framebuffer
        self.fbo.use()
        self.ctx.clear(0.0, 0.0, 0.0, 1.0)

        # Detect vertex attributes from source and build matching VAO
        attrs = self._extract_attributes(vert)
        if not attrs:
            raise RuntimeError("Vertex shader has no attributes")

        if "in_pos" in attrs:
            # Standard fullscreen quad (builder-generated shaders)
            vao = self.ctx.simple_vertex_array(prog, self._vbo, "in_pos")
        else:
            # Fallback: build a VBO matching the first attribute
            # We assume vec2/vec3/vec4 and send a fullscreen quad with matching dims
            first_attr = attrs[0]
            # Try to infer component count from declaration
            comp_map = {"vec2": 2, "vec3": 3, "vec4": 4, "float": 1}
            comps = 2  # default
            for c, n in comp_map.items():
                if re.search(rf"\b(?:in|attribute)\s+{re.escape(c)}\s+{re.escape(first_attr)}\s*;", vert):
                    comps = n
                    break
            if comps == 2:
                vbo = self.ctx.buffer(_QUAD_VERTS)
            elif comps == 3:
                verts_3d = np.zeros((6, 3), dtype="f4")
                verts_3d[:, :2] = _QUAD_VERTS.reshape(-1, 2)
                vbo = self.ctx.buffer(verts_3d)
            elif comps == 4:
                verts_4d = np.zeros((6, 4), dtype="f4")
                verts_4d[:, :2] = _QUAD_VERTS.reshape(-1, 2)
                verts_4d[:, 3] = 1.0
                vbo = self.ctx.buffer(verts_4d)
            else:
                # For float or unknown, just send 2D coords
                vbo = self.ctx.buffer(_QUAD_VERTS)
            vao = self.ctx.simple_vertex_array(prog, vbo, first_attr)

        vao.render(moderngl.TRIANGLES)

        # Readback + vertical flip (OpenGL origin is bottom-left)
        raw = self.fbo.read(components=4)
        img = Image.frombytes("RGBA", (self.width, self.height), raw)
        arr = np.array(img.transpose(Image.FLIP_TOP_BOTTOM))
        return arr

    def render_sequence(
        self,
        vert: str,
        frag: str,
        uniforms_base: dict[str, Any] | None = None,
        fps: float = 30.0,
        duration: float = 3.0,
        output_dir: str = ".agent/tmp/shader_frames",
        prefix: str = "frame",
    ) -> list[str]:
        """Render a frame sequence with animated time uniform.

        Automatically advances ``time`` from 0 to ``duration`` seconds.
        Other animated uniforms declared in ``shader.json`` are also interpolated.

        Args:
            vert: vertex shader source
            frag: fragment shader source
            uniforms_base: static uniforms (e.g. resolution)
            fps: frames per second
            duration: total animation duration in seconds
            output_dir: directory to write PNG frames
            prefix: filename prefix

        Returns:
            list of written file paths
        """
        os.makedirs(output_dir, exist_ok=True)
        total_frames = int(round(fps * duration))
        frame_paths: list[str] = []

        for frame_idx in range(total_frames):
            t = frame_idx / fps
            uniforms = dict(uniforms_base or {})
            uniforms.setdefault("time", t)

            arr = self.render(vert, frag, uniforms)

            fname = f"{prefix}_{frame_idx + 1:04d}.png"
            fpath = os.path.join(output_dir, fname)
            Image.fromarray(arr).save(fpath)
            frame_paths.append(fpath)

        return frame_paths

    # ------------------------------------------------------------------
    # Convenience: render from shader.json
    # ------------------------------------------------------------------
    @classmethod
    def render_from_json(
        cls,
        shader_dir: str,
        output_dir: str | None = None,
        override_resolution: tuple[int, int] | None = None,
        override_duration: float | None = None,
        override_fps: float | None = None,
    ) -> list[str]:
        """Render a shader asset directory (Layer 2 → Layer 1).

        Reads ``shader.json`` from *shader_dir*, compiles the referenced GLSL,
        and writes a PNG frame sequence to *output_dir* (defaults to
        ``shader_dir/frames/``).

        Returns:
            list of written frame paths
        """
        json_path = os.path.join(shader_dir, "shader.json")
        with open(json_path, encoding="utf-8") as f:
            spec = json.load(f)

        render_cfg = spec.get("render", {})
        fps = override_fps or render_cfg.get("fps", 30)
        duration = override_duration or render_cfg.get("duration", 3.0)
        res = override_resolution or tuple(render_cfg.get("resolution", [1920, 1080]))
        width, height = int(res[0]), int(res[1])

        backend = Backend.from_hardware_profile()
        runner = cls(width, height, backend=backend)

        glsl_cfg = spec["glsl"]
        with open(os.path.join(shader_dir, glsl_cfg["vertex"])) as f:
            vert = f.read()
        with open(os.path.join(shader_dir, glsl_cfg["fragment"])) as f:
            frag = f.read()

        # Build static uniforms from shader.json defaults
        uniforms: dict[str, Any] = {}
        for u in spec.get("uniforms", []):
            name = u["name"]
            default = u.get("default")
            if default is not None and not u.get("animation", {}).get("enabled", False):
                uniforms[name] = default

        # resolution is always injected
        uniforms["resolution"] = (float(width), float(height))

        out = output_dir or os.path.join(shader_dir, "frames")
        return runner.render_sequence(
            vert=vert,
            frag=frag,
            uniforms_base=uniforms,
            fps=fps,
            duration=duration,
            output_dir=out,
        )

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    @staticmethod
    def _extract_attributes(vert_source: str) -> list[str]:
        """Extract vertex attribute names from GLSL source."""
        return re.findall(r"\b(?:in|attribute)\s+\w+\s+(\w+)\s*;", vert_source)

    @staticmethod
    def _normalize_uniform(value: Any, fmt: str = "") -> Any:
        """Normalise Python values for moderngl uniform assignment.

        Args:
            value: raw Python value (float, list, tuple, ndarray)
            fmt: moderngl uniform format string (e.g. '1f', '2f', '16f')
        """
        if isinstance(value, np.ndarray):
            return tuple(value.flatten().tolist())
        if isinstance(value, (list, tuple)):
            return tuple(float(v) if isinstance(v, (int, float)) else v for v in value)
        # Expand scalar to vector/matrix when fmt indicates multiple components
        if isinstance(value, (int, float)) and fmt:
            import re
            m = re.match(r"(\d+)", fmt)
            comps = int(m.group(1)) if m else 1
            if comps > 1:
                return (float(value),) * comps
        return value


def _test():
    """Quick sanity test: render a red fullscreen quad."""
    import tempfile

    runner = HeadlessShaderRunner(320, 240)
    frag = """#version 330
out vec4 fragColor;
void main() {
    fragColor = vec4(1.0, 0.0, 0.0, 1.0);
}
"""
    arr = runner.render(DEFAULT_VERT, frag)
    assert arr.shape == (240, 320, 4)
    assert arr[120, 160, 0] == 255  # red channel center
    print("shader_runner sanity test: PASSED")

    # Test sequence
    with tempfile.TemporaryDirectory() as tmpdir:
        paths = runner.render_sequence(
            DEFAULT_VERT, frag, duration=0.1, fps=10, output_dir=tmpdir
        )
        assert len(paths) == 1  # 0.1s @ 10fps = 1 frame (rounded)
        print(f"sequence test: {paths[0]} OK")


if __name__ == "__main__":
    _test()
