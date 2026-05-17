#!/usr/bin/env python3
"""pipeline/composite-unified-render.py
Pure orchestrator for composite-unified scenes.
Extracted from render.sh to keep render.sh as a thin dispatcher only.

Usage:
    composite-unified-render.py <scene_dir> [--json] [--fps N] [--duration S]
        [--width W] [--height H]
"""

import argparse
import json
import os
import subprocess
import sys

_BIN_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "bin")
if _BIN_DIR not in sys.path:
    sys.path.insert(0, _BIN_DIR)
from macode_state import write_progress, write_state  # noqa: E402


def get_project_root() -> str:
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def get_python() -> str:
    project_root = get_project_root()
    venv_python = os.path.join(project_root, ".venv", "bin", "python")
    if os.path.isfile(venv_python) and os.access(venv_python, os.X_OK):
        return venv_python
    return "python3"


def main():
    parser = argparse.ArgumentParser(
        description="Render a composite-unified scene (orchestrator).",
        usage="%(prog)s <scene_dir> [options]",
        epilog="Examples:\n"
        "  %(prog)s scenes/04_composite_unified_demo\n"
        "  %(prog)s scenes/04_composite_unified_demo --fps 2 --duration 1\n"
        "  %(prog)s scenes/04_composite_unified_demo --json",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("scene_dir", help="Scene directory")
    parser.add_argument("--json", action="store_true", help="Output JSON result")
    parser.add_argument("--fps", type=int, default=None, help="Override FPS")
    parser.add_argument("--duration", type=float, default=None, help="Override duration")
    parser.add_argument("--width", type=int, default=None, help="Override width")
    parser.add_argument("--height", type=int, default=None, help="Override height")
    args = parser.parse_args()

    scene_dir = args.scene_dir.rstrip("/")
    scene_name = os.path.basename(scene_dir)
    project_root = get_project_root()
    python = get_python()

    unified_dir = f".agent/tmp/{scene_name}/.unified_src"
    output_mp4 = f".agent/tmp/{scene_name}/final.mp4"

    write_state(scene_name, "running")
    write_progress(scene_name, "composite_init", "running", message="generating orchestrator")

    # ── Generate orchestrator ─────────────────────────
    print(f"[composite-unified] Generating orchestrator for '{scene_name}'...")
    result = subprocess.run(
        [python, os.path.join(project_root, "bin", "composite-unified.py"), scene_dir, unified_dir],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        print("[composite-unified] Orchestrator generation failed", file=sys.stderr)
        print(result.stderr, file=sys.stderr)
        write_state(scene_name, "failed", exit_code=1)
        write_progress(
            scene_name, "composite_init", "failed", message="orchestrator generation failed"
        )
        sys.exit(1)
    print(result.stdout.strip())

    # ── Prepare params injection ──────────────────────
    env = os.environ.copy()
    manifest_path = os.path.join(scene_dir, "manifest.json")
    if os.path.isfile(manifest_path):
        with open(manifest_path, encoding="utf-8") as f:
            manifest_data = json.load(f)
        if manifest_data.get("params") is not None:
            params_file = os.path.abspath(os.path.join(unified_dir, "composite_params.json"))
            os.makedirs(os.path.dirname(params_file), exist_ok=True)
            with open(params_file, "w", encoding="utf-8") as f:
                json.dump(manifest_data["params"], f, indent=2)
                f.write("\n")
            env["MACODE_PARAMS_JSON"] = params_file
            print(f"[composite-unified] Params injected: {params_file}")

    # ── Render unified scene ──────────────────────────
    print("[composite-unified] Rendering unified scene...")
    render_cmd = ["bash", os.path.join(project_root, "pipeline", "render.sh"), unified_dir]
    if args.fps is not None:
        render_cmd.extend(["--fps", str(args.fps)])
    if args.duration is not None:
        render_cmd.extend(["--duration", str(args.duration)])
    if args.width is not None:
        render_cmd.extend(["--width", str(args.width)])
    if args.height is not None:
        render_cmd.extend(["--height", str(args.height)])

    write_progress(scene_name, "composite_render", "running", message="unified scene render")
    result = subprocess.run(render_cmd, capture_output=True, text=True, env=env)
    if result.returncode != 0:
        print("[composite-unified] Unified render failed", file=sys.stderr)
        print(result.stderr, file=sys.stderr)
        write_state(scene_name, "failed", exit_code=1)
        write_progress(scene_name, "composite_render", "failed", message="unified render failed")
        sys.exit(1)
    print(result.stdout.strip())

    # ── Copy output ───────────────────────────────────
    # render-scene.py uses basename(scene_dir) as scene_name.
    # unified_dir = .agent/tmp/{scene}/.unified_src  →  scene_name = .unified_src
    # output_dir  = .agent/tmp/.unified_src
    unified_output = ".agent/tmp/.unified_src/final.mp4"
    if os.path.isfile(unified_output):
        os.makedirs(os.path.dirname(output_mp4), exist_ok=True)
        subprocess.run(["cp", unified_output, output_mp4], check=True)
    else:
        print(f"[composite-unified] Expected output not found: {unified_output}", file=sys.stderr)
        write_state(scene_name, "failed", exit_code=1)
        write_progress(scene_name, "composite_assemble", "failed", message="output not found")
        sys.exit(1)

    # ── Deliver ───────────────────────────────────────
    subprocess.run(
        [
            python,
            os.path.join(project_root, "pipeline", "deliver.py"),
            scene_name,
            os.path.join(".agent", "tmp", scene_name),
            os.path.join(project_root, "output"),
        ],
        capture_output=True,
        text=True,
        check=False,
    )

    # ── Output ────────────────────────────────────────
    write_state(scene_name, "completed", exit_code=0)
    write_progress(scene_name, "composite_done", "completed", message=f"Output: {output_mp4}")

    if args.json:
        final_size = os.path.getsize(output_mp4) if os.path.isfile(output_mp4) else 0
        print(
            json.dumps(
                {
                    "scene": scene_name,
                    "type": "composite-unified",
                    "output": output_mp4,
                    "final_size_bytes": final_size,
                },
                indent=2,
            )
        )
    else:
        print(f"Done: {output_mp4}")


if __name__ == "__main__":
    main()
