#!/usr/bin/env python3
"""bin/shader-render.py
MaCode Shader Renderer — compile Layer 2 (shader asset) to Layer 1 (PNG frames).

Pure moderngl, zero window dependency. Direct OpenGL offscreen framebuffer.

Usage:
    shader-render.py <shader_dir> [--output <dir>] [--fps <n>] [--duration <sec>] [--resolution <WxH>]

Examples:
    shader-render.py assets/shaders/noise_heatmap/
    shader-render.py assets/shaders/noise_heatmap/ --output .agent/tmp/shader_frames/ --fps 30 --duration 3
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path


def _ensure_shader_utils_in_path():
    """Add engines/manimgl/src to PYTHONPATH so shader_runner can be imported."""
    project_root = Path(__file__).parent.parent.resolve()
    manimgl_src = project_root / "engines" / "manimgl" / "src"
    if str(manimgl_src) not in sys.path:
        sys.path.insert(0, str(manimgl_src))


def _import_runner():
    _ensure_shader_utils_in_path()
    try:
        from utils.shader_backend import Backend
        from utils.shader_runner import HeadlessShaderRunner
        return HeadlessShaderRunner, Backend
    except ImportError as exc:
        print(f"[error] Cannot import shader_runner: {exc}", file=sys.stderr)
        print("[hint] Ensure moderngl is installed in the active Python environment.", file=sys.stderr)
        sys.exit(1)


def main():
    parser = argparse.ArgumentParser(
        description="Render a MaCode shader asset (Layer 2) to PNG frame sequence (Layer 1).",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""Examples:
  shader-render.py assets/shaders/noise_heatmap/
  shader-render.py assets/shaders/noise_heatmap/ --output frames/ --fps 60 --duration 5 --resolution 1920x1080
""",
    )
    parser.add_argument("shader_dir", help="Path to shader asset directory containing shader.json")
    parser.add_argument("--output", "-o", default=None, help="Output directory for frames (default: shader_dir/frames/)")
    parser.add_argument("--fps", type=float, default=None, help="Frames per second (override shader.json)")
    parser.add_argument("--duration", type=float, default=None, help="Duration in seconds (override shader.json)")
    parser.add_argument("--resolution", type=str, default=None, help="Resolution as WxH, e.g. 1920x1080 (override shader.json)")
    parser.add_argument("--prefix", default="frame", help="Frame filename prefix (default: frame)")
    parser.add_argument("--backend", choices=["gpu", "d3d12", "cpu", "headless"], default=None, help="Force rendering backend")
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose output")

    args = parser.parse_args()

    shader_dir = Path(args.shader_dir)
    json_path = shader_dir / "shader.json"
    if not json_path.exists():
        print(f"[error] shader.json not found in {shader_dir}", file=sys.stderr)
        sys.exit(1)

    with open(json_path, encoding="utf-8") as f:
        spec = json.load(f)

    # Resolve overrides
    render_cfg = spec.get("render", {})
    fps = args.fps or render_cfg.get("fps", 30)
    duration = args.duration or render_cfg.get("duration", 3.0)
    res = args.resolution
    if res:
        w, h = map(int, res.split("x"))
    else:
        w, h = render_cfg.get("resolution", [1920, 1080])
        w, h = int(w), int(h)

    output_dir = args.output or str(shader_dir / "frames")
    os.makedirs(output_dir, exist_ok=True)

    # Resolve backend
    HeadlessShaderRunner, Backend = _import_runner()
    if args.backend:
        backend = Backend[args.backend.upper()]
    else:
        backend = Backend.from_hardware_profile()

    if args.verbose:
        print(f"[info] Shader:       {spec['metadata']['name']}")
        print(f"[info] Backend:      {backend.name}")
        print(f"[info] Resolution:   {w}x{h}")
        print(f"[info] FPS:          {fps}")
        print(f"[info] Duration:     {duration}s")
        print(f"[info] Total frames: {int(round(fps * duration))}")
        print(f"[info] Output:       {output_dir}")
        print("[info] Rendering...")

    t0 = time.time()

    # Read GLSL
    glsl_cfg = spec["glsl"]
    vert_path = shader_dir / glsl_cfg["vertex"]
    frag_path = shader_dir / glsl_cfg["fragment"]

    with open(vert_path, encoding="utf-8") as f:
        vert = f.read()
    with open(frag_path, encoding="utf-8") as f:
        frag = f.read()

    # Build static uniforms
    uniforms: dict[str, object] = {}
    for u in spec.get("uniforms", []):
        name = u["name"]
        default = u.get("default")
        if default is not None and not u.get("animation", {}).get("enabled", False):
            uniforms[name] = default
    uniforms["resolution"] = (float(w), float(h))

    # Render
    runner = HeadlessShaderRunner(w, h, backend=backend)
    frame_paths = runner.render_sequence(
        vert=vert,
        frag=frag,
        uniforms_base=uniforms,
        fps=fps,
        duration=duration,
        output_dir=output_dir,
        prefix=args.prefix,
    )

    elapsed = time.time() - t0
    fps_actual = len(frame_paths) / elapsed if elapsed > 0 else 0

    if args.verbose:
        print(f"[info] Done: {len(frame_paths)} frames in {elapsed:.1f}s ({fps_actual:.1f} fps)")
    else:
        print(f"Rendered {len(frame_paths)} frames → {output_dir} ({elapsed:.1f}s)")

    # Write manifest for Layer 1 consumers
    manifest = {
        "source": str(shader_dir),
        "fps": fps,
        "duration": duration,
        "resolution": [w, h],
        "frame_count": len(frame_paths),
        "frame_pattern": f"{args.prefix}_%04d.png",
    }
    with open(os.path.join(output_dir, "manifest.json"), "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)

    return 0


if __name__ == "__main__":
    sys.exit(main())
