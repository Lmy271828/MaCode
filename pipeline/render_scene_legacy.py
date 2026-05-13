#!/usr/bin/env python3
"""pipeline/render-scene.py
Pure orchestrator for single-scene rendering.
Replaces render-single.sh with a strict separation of orchestration vs execution.

CLI (identical to render-single.sh):
    render-scene.py <scene_dir> [--json] [--fps N] [--duration S] [--width W] [--height H]
"""

import argparse
import ast
import datetime
import json
import os
import socket
import subprocess
import sys
from pathlib import Path

_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
_BIN_DIR = os.path.join(os.path.dirname(_SCRIPT_DIR), "bin")
if _BIN_DIR not in sys.path:
    sys.path.insert(0, _BIN_DIR)
from macode_state import write_progress  # noqa: E402


def get_project_root() -> str:
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def get_python() -> str:
    project_root = get_project_root()
    venv_python = os.path.join(project_root, ".venv", "bin", "python")
    if os.path.isfile(venv_python) and os.access(venv_python, os.X_OK):
        return venv_python
    return "python3"


def read_manifest(manifest_path: str) -> dict:
    with open(manifest_path, encoding="utf-8") as f:
        return json.load(f)


def find_free_port(port_min: int, port_max: int) -> int:
    """Find a free TCP port in the given range using atomic bind()."""
    import random
    ports = list(range(port_min, port_max + 1))
    random.shuffle(ports)
    for port in ports:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(0.2)
            try:
                s.bind(("127.0.0.1", port))
                return port
            except OSError:
                continue
    raise RuntimeError(f"No free port in range {port_min}-{port_max}")


def locate_scene_file(scene_dir: str, extensions: list) -> str:
    for ext in extensions:
        candidate = os.path.join(scene_dir, f"scene{ext}")
        if os.path.isfile(candidate):
            return candidate
    return ""


def main():
    parser = argparse.ArgumentParser(
        description="Render a single scene (orchestrator).",
        usage="%(prog)s <scene_dir> [options]",
        epilog="Examples:\n"
               "  %(prog)s scenes/01_test\n"
               "  %(prog)s scenes/01_test --fps 2 --duration 1\n"
               "  %(prog)s scenes/01_test --json",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("scene_dir", help="Scene directory")
    parser.add_argument("--json", action="store_true", help="Output JSON result")
    parser.add_argument("--fps", type=int, default=None, help="Override FPS")
    parser.add_argument("--duration", type=float, default=None, help="Override duration")
    parser.add_argument("--width", type=int, default=None, help="Override width")
    parser.add_argument("--height", type=int, default=None, help="Override height")
    parser.add_argument("--no-review", action="store_true", help="Skip review-needed marking (for batch testing)")
    parser.add_argument("--skip-checks", action="store_true", help="Skip static checks (for manual debugging)")
    args = parser.parse_args()

    scene_dir = args.scene_dir.rstrip("/")
    scene_name = os.path.basename(scene_dir)
    project_root = get_project_root()
    os.environ["PROJECT_ROOT"] = project_root
    python = get_python()

    manifest_path = os.path.join(scene_dir, "manifest.json")
    if not os.path.isfile(manifest_path):
        print(f"Error: manifest.json not found in {scene_dir}", file=sys.stderr)
        sys.exit(1)

    # ── Check for previous round human_override ──
    signals_dir = Path(".agent") / "signals"
    per_scene_dir = signals_dir / "per-scene" / scene_name
    override_path = per_scene_dir / "human_override.json"
    review_path = per_scene_dir / "review_needed"

    if override_path.exists():
        try:
            override = json.loads(override_path.read_text(encoding="utf-8"))
            action = override.get("action")
            if action == "approve":
                review_path.unlink(missing_ok=True)
                override_path.unlink(missing_ok=True)
                print(f"[review] '{scene_name}' approved.")
                sys.exit(0)
            elif action == "reject":
                reason = override.get("reason", "")
                review_path.unlink(missing_ok=True)
                override_path.unlink(missing_ok=True)
                print(f"[review] '{scene_name}' rejected: {reason}", file=sys.stderr)
                sys.exit(1)
            elif action == "retry":
                instruction = override.get("instruction", "")
                review_path.unlink(missing_ok=True)
                override_path.unlink(missing_ok=True)
                print(json.dumps({
                    "status": "override_received",
                    "action": "retry",
                    "instruction": instruction,
                    "scene": scene_name,
                }))
                sys.exit(2)
        except (json.JSONDecodeError, OSError) as e:
            print(f"[review] Warning: corrupt override file: {e}", file=sys.stderr)
            override_path.unlink(missing_ok=True)

    # ── If review is pending and no override yet, skip re-render ──
    if review_path.exists() and not args.no_review:
        print(json.dumps({
            "status": "awaiting_review",
            "scene": scene_name,
            "message": "Scene is awaiting human review. Run 'macode review approve <scene>' or 'macode review reject <scene>' to proceed.",
        }))
        sys.exit(3)

    manifest = read_manifest(manifest_path)
    engine = manifest.get("engine", "manim")
    fps = args.fps if args.fps is not None else manifest.get("fps", 30)
    duration = args.duration if args.duration is not None else manifest.get("duration", 3)
    resolution = manifest.get("resolution", [1920, 1080])
    width = args.width if args.width is not None else resolution[0]
    height = args.height if args.height is not None else resolution[1]

    # ── Engine configuration ──────────────────────────
    engine_conf_path = os.path.join(project_root, "engines", engine, "engine.conf")
    if not os.path.isfile(engine_conf_path):
        print(f"Error: engine.conf not found for '{engine}'", file=sys.stderr)
        print(f"  Expected: {engine_conf_path}", file=sys.stderr)
        sys.exit(1)

    result = subprocess.run(
        [python, os.path.join(project_root, "bin", "inspect-conf.py"), engine_conf_path],
        capture_output=True, text=True,
    )
    if result.returncode != 0:
        print(f"Error: failed to parse engine.conf for '{engine}'", file=sys.stderr)
        sys.exit(1)
    try:
        engine_conf = json.loads(result.stdout)
    except json.JSONDecodeError as e:
        print(f"Error: invalid engine.conf output: {e}", file=sys.stderr)
        sys.exit(1)
    ext_list = engine_conf["scene_extensions"]
    engine_mode = engine_conf["mode"]
    render_script_rel = (engine_conf.get("render_script") or "").replace("\\", "/")
    unified_mc_render = render_script_rel.endswith("render.mjs")

    # ── Locate scene file ─────────────────────────────
    scene_file = locate_scene_file(scene_dir, ext_list)
    if not scene_file:
        print(f"Error: scene file not found in {scene_dir}", file=sys.stderr)
        print(f"  Tried extensions: {ext_list} (looking for scene<ext>)", file=sys.stderr)
        sys.exit(1)

    # ── Output paths ──────────────────────────────────
    output_dir = os.path.join(".agent", "tmp", scene_name)
    frames_dir = os.path.join(output_dir, "frames")
    os.makedirs(frames_dir, exist_ok=True)

    log_dir = os.path.join(".agent", "log")
    os.makedirs(log_dir, exist_ok=True)
    log_file = os.path.join(log_dir, f"{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}_{scene_name}.log")

    # ── Validate manifest ─────────────────────────────
    result = subprocess.run(
        [python, os.path.join(project_root, "pipeline", "validate-manifest.py"), manifest_path],
        capture_output=True, text=True,
    )
    if result.returncode != 0:
        print(result.stdout + result.stderr, file=sys.stderr)
        sys.exit(1)
    print("[validate] OK")

    # ── Discover engine script ────────────────────────
    engine_script = engine_conf.get("render_script")
    if engine_script:
        engine_script = os.path.join(project_root, engine_script)
    else:
        # Backward compat: hardcoded discovery
        engine_script_mjs = os.path.join(project_root, "engines", engine, "scripts", "render-cli.mjs")
        engine_script_sh = os.path.join(project_root, "engines", engine, "scripts", "render.sh")
        if os.path.isfile(engine_script_mjs):
            engine_script = engine_script_mjs
        elif os.path.isfile(engine_script_sh):
            engine_script = engine_script_sh
        else:
            print(f"Error: engine script not found for '{engine}'", file=sys.stderr)
            sys.exit(1)

    write_progress(scene_name, "init", "running", extra={
        "message": f"Config: {fps}fps, {duration}s, {width}x{height}",
    })
    print(f"[{engine}] Rendering {scene_name}...")
    print(f"[{engine}] Scene: {scene_file}")
    print(f"[{engine}] Output: {frames_dir}")
    print(f"[{engine}] Settings: {width}x{height} @ {fps}fps for {duration}s")

    # ── API-Gate ──────────────────────────────────────
    sourcemap_json = os.path.join("engines", engine, "sourcemap.json")
    sourcemap_path = os.path.join(project_root, sourcemap_json)
    api_gate = os.path.join(project_root, "bin", "api-gate.py")
    if os.path.isfile(sourcemap_path) and os.path.isfile(api_gate) and os.access(api_gate, os.X_OK):
        print(f"[api-gate] Checking {scene_file} against sourcemap.json BLACKLIST...")
        with open(log_file, "a", encoding="utf-8") as logf:
            result = subprocess.run(
                [python, api_gate, scene_file, sourcemap_path, "--engine", engine],
                stdout=logf, stderr=subprocess.STDOUT,
            )
        if result.returncode != 0:
            print("[api-gate] BLOCKED. Fix violations before rendering.")
            subprocess.run(["tail", "-n", "5", log_file])
            sys.exit(1)
        print("[api-gate] OK")

    # ── Static checks (layout / narrative / density) ──
    def scene_inherits_from(source_path: str, base_names: list) -> bool:
        try:
            with open(source_path, encoding="utf-8") as f:
                tree = ast.parse(f.read())
        except (SyntaxError, OSError):
            return False
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                for base in node.bases:
                    name = ""
                    if isinstance(base, ast.Name):
                        name = base.id
                    elif isinstance(base, ast.Attribute):
                        name = base.attr
                    if name in base_names:
                        return True
        return False

    check_reports_dir = os.path.join(".agent", "check_reports")
    os.makedirs(check_reports_dir, exist_ok=True)

    if not args.skip_checks and scene_file.endswith(".py"):
        is_zoned = scene_inherits_from(scene_file, ["ZoneScene", "NarrativeScene"])
        if is_zoned:
            layout_profile = manifest.get("layout_profile")
            narrative_profile = manifest.get("narrative_profile")

            if layout_profile:
                print(f"[layout-check] Running with profile '{layout_profile}'...")
                layout_report_path = os.path.join(check_reports_dir, f"{scene_name}_layout.json")
                result = subprocess.run(
                    [python, os.path.join(project_root, "bin", "check-layout.py"),
                     scene_file, "--layout-profile", layout_profile,
                     "--output", layout_report_path],
                    capture_output=True, text=True,
                )
                if result.returncode != 0:
                    print("[layout-check] FAILED. See report for details.")
                    print(result.stdout)
                    sys.exit(1)
                print("[layout-check] OK")

            if narrative_profile:
                print(f"[narrative-check] Running with profile '{narrative_profile}'...")
                narrative_report_path = os.path.join(check_reports_dir, f"{scene_name}_narrative.json")
                result = subprocess.run(
                    [python, os.path.join(project_root, "bin", "check-narrative.py"),
                     scene_file, "--narrative-profile", narrative_profile,
                     "--output", narrative_report_path],
                    capture_output=True, text=True,
                )
                if result.returncode != 0:
                    print("[narrative-check] FAILED. See report for details.")
                    print(result.stdout)
                    sys.exit(1)
                print("[narrative-check] OK")

            # Density check runs for all zoned scenes
            print("[density-check] Running...")
            density_report_path = os.path.join(check_reports_dir, f"{scene_name}_density.json")
            result = subprocess.run(
                [python, os.path.join(project_root, "bin", "check-density.py"),
                 scene_file, "--output", density_report_path],
                capture_output=True, text=True,
            )
            if result.returncode != 0:
                print("[density-check] FAILED. See report for details.")
                print(result.stdout)
                sys.exit(1)
            print("[density-check] OK")
        else:
            print("[checks] Scene does not inherit ZoneScene/NarrativeScene — skipping static checks.")

    # ── Cache check ───────────────────────────────────
    cache_script = os.path.join(project_root, "pipeline", "cache.sh")
    cache_hit = False
    if os.path.isfile(cache_script) and os.access(cache_script, os.X_OK):
        with open(log_file, "a", encoding="utf-8") as logf:
            result = subprocess.run(
                ["bash", cache_script, scene_dir, "check", output_dir],
                stdout=logf, stderr=subprocess.STDOUT,
            )
        if result.returncode == 0:
            cache_hit = True
            print("[cache] Using cached frames, skipping engine render")
        else:
            print("[cache] Cache miss, rendering with engine...")

    # ── Pre-render steps ──────────────────────────────
    pre_render_script = engine_conf.get("pre_render_script")
    if pre_render_script and not cache_hit:
        pre_render_script = os.path.join(project_root, pre_render_script)
        if os.path.isfile(pre_render_script):
            print(f"[pre-render] Running {pre_render_script}...")
            write_progress(scene_name, "shader", "running", extra={"message": "Pre-rendering shader dependencies"})
            subprocess.run(
                ["node", pre_render_script, scene_dir,
                 "--fps", str(fps), "--duration", str(duration),
                 "--width", str(width), "--height", str(height)],
                check=True,
            )

    # ── Background service (e.g. dev server, legacy MC path) ──────────
    service_url = None
    service_state = None
    service_script = engine_conf.get("service_script")
    if service_script and not cache_hit and not unified_mc_render:
        service_script = os.path.join(project_root, service_script)
        port_min = engine_conf.get("service_port_min") or 4567
        port_max = engine_conf.get("service_port_max") or 5999
        port = find_free_port(port_min, port_max)

        # Clean up any stale service state for this scene
        tmp_dir = os.path.join(project_root, ".agent", "tmp", scene_name)
        state_path = os.path.join(tmp_dir, "state.json")
        stop_script = os.path.join(project_root, "engines", engine, "scripts", "render.mjs")
        if os.path.isfile(stop_script) and os.path.isfile(state_path):
            subprocess.run(["node", stop_script, "--stop", scene_dir], check=False)

        print(f"[service] Starting background service on port {port}...")
        write_progress(scene_name, "serve", "running", extra={"port": port, "message": f"Starting dev server on port {port}"})

        # Start service via macode-run for unified lifecycle tracking
        subprocess.run(
            [os.path.join(project_root, "bin", "macode-run"),
             f"{scene_name}-service", "--log", log_file, "--",
             "node", service_script, scene_dir, "--port", str(port)],
            check=True,
        )

        # Wait for service to write its state
        for _ in range(60):  # 30s timeout
            if os.path.isfile(state_path):
                try:
                    with open(state_path, encoding="utf-8") as f:
                        service_state = json.load(f)
                    outputs = service_state.get("outputs", {})
                    if outputs.get("port") == port:
                        service_url = outputs.get("captureUrl")
                        break
                except (json.JSONDecodeError, OSError):
                    pass
            import time
            time.sleep(0.5)

        if not service_url:
            print("[service] ERROR: Service failed to start or did not write state", file=sys.stderr)
            sys.exit(1)

        print(f"[service] Ready at {service_url}")

    # ── Engine runner ─────────────────────────────────
    def run_engine():
        if engine_script.endswith(".mjs"):
            cmd = ["node", engine_script]
            if unified_mc_render:
                cmd.extend(
                    [
                        scene_dir,
                        frames_dir,
                        str(fps),
                        str(duration),
                        str(width),
                        str(height),
                    ]
                )
            elif service_url:
                cmd.extend(
                    [
                        service_url,
                        frames_dir,
                        str(fps),
                        str(duration),
                        str(width),
                        str(height),
                    ]
                )
            else:
                print(
                    "Error: Node render script expects unified render.mjs or a running service URL",
                    file=sys.stderr,
                )
                sys.exit(1)
        else:
            cmd = ["bash", engine_script]
            if engine_mode == "interactive":
                cmd.extend([scene_file, output_dir, str(fps), str(duration), str(width), str(height)])
            else:
                cmd.extend([scene_file, frames_dir, str(fps), str(duration), str(width), str(height)])

        subprocess.run(
            [os.path.join(project_root, "bin", "macode-run"), scene_name, "--log", log_file, "--"] + cmd,
            check=True,
        )

    if not cache_hit:
        write_progress(scene_name, "capture", "running", extra={
            "message": "Starting frame capture",
            "fps": fps,
            "duration": duration,
            "width": width,
            "height": height,
        })
        run_engine()
        write_progress(scene_name, "capture", "completed", extra={"message": "Frame capture completed"})

    # ── Layer 2 checks (runtime layout overlap) ───────
    snapshot_path = os.path.join(output_dir, "layout_snapshots.jsonl")
    if os.path.isfile(snapshot_path):
        print("[layer2] Running runtime layout checks...")
        layer2_report_path = os.path.join(check_reports_dir, f"{scene_name}_layer2.json")
        result = subprocess.run(
            [python, os.path.join(project_root, "bin", "check-runner.py"),
             scene_dir, "--layer", "layer2", "--format", "raw"],
            capture_output=True, text=True,
        )
        try:
            layer2_data = json.loads(result.stdout)
            with open(layer2_report_path, "w", encoding="utf-8") as f:
                json.dump(layer2_data, f, indent=2, ensure_ascii=False)
                f.write("\n")
            severity = layer2_data.get("severity_summary", {})
            if severity.get("error"):
                print("[layer2] ERROR: Blocking issues found. See report.")
                sys.exit(1)
            elif severity.get("warning"):
                print("[layer2] WARNING: Layout issues found. See report.")
            else:
                print("[layer2] OK")
        except json.JSONDecodeError:
            print(f"[layer2] Failed to parse output: {result.stderr}", file=sys.stderr)

    # ── Stop background service ───────────────────────
    if service_state:
        stop_script = os.path.join(project_root, "engines", engine, "scripts", "render.mjs")
        if os.path.isfile(stop_script):
            print("[service] Stopping background service...")
            subprocess.run(["node", stop_script, "--stop", scene_dir], check=False)

    # ── Resource fuse checks ──────────────────────────
    if engine_mode != "interactive":
        frame_count = len([f for f in os.listdir(frames_dir) if f.endswith(".png")])
        if frame_count > 10000:
            print(f"FUSE: frame count {frame_count} exceeds limit 10000", file=sys.stderr)
            sys.exit(1)

    disk_bytes = 0
    tmp_dir = os.path.join(".agent", "tmp")
    if os.path.isdir(tmp_dir):
        result = subprocess.run(["du", "-sb", tmp_dir], capture_output=True, text=True, check=False)
        if result.returncode == 0:
            disk_bytes = int(result.stdout.strip().split()[0])
    if disk_bytes > 53687091200:
        disk_gb = disk_bytes // 1024 // 1024 // 1024
        print(f"FUSE: disk usage {disk_gb}GB exceeds limit 50GB", file=sys.stderr)
        sys.exit(1)

    # ── Encode to MP4 ─────────────────────────────────
    if engine_mode == "interactive":
        print(f"[{engine}] Interactive engine — skipping frame encoding.")
        print(f"[{engine}] Preview complete. Use 'macode migrate' to export to batch engine for final render.")
        raw_mp4 = os.path.join(output_dir, "raw.mp4")
        final_mp4 = os.path.join(output_dir, "final.mp4")
        if os.path.isfile(raw_mp4):
            subprocess.run(["cp", raw_mp4, final_mp4], check=False)
        else:
            open(final_mp4, "a").close()
    else:
        raw_mp4 = os.path.join(output_dir, "raw.mp4")
        final_mp4 = os.path.join(output_dir, "final.mp4")
        with open(log_file, "a", encoding="utf-8") as logf:
            result = subprocess.run(
                ["bash", os.path.join(project_root, "pipeline", "concat.sh"), frames_dir, raw_mp4, str(fps)],
                stdout=logf, stderr=subprocess.STDOUT,
            )
        if result.returncode != 0:
            print("[concat] Frame encoding failed", file=sys.stderr)
            sys.exit(1)
        subprocess.run(["cp", raw_mp4, final_mp4], check=False)

        # ── Cache populate ──────────────────────────────
        if os.path.isfile(cache_script) and os.access(cache_script, os.X_OK):
            with open(log_file, "a", encoding="utf-8") as logf:
                subprocess.run(
                    ["bash", cache_script, scene_dir, "populate", output_dir],
                    stdout=logf, stderr=subprocess.STDOUT, check=False,
                )

    # ── Deliver ───────────────────────────────────────
    subprocess.run(
        [python, os.path.join(project_root, "pipeline", "deliver.py"), scene_name, output_dir, os.path.join(project_root, "output")],
        check=False,
    )

    # ── Mark for review ───────────────────────────────
    if not args.no_review:
        per_scene_dir.mkdir(parents=True, exist_ok=True)
        review_path.touch()
        print(f"[review] '{scene_name}' marked for review.")

    write_progress(scene_name, "cleanup", "completed", extra={"message": "Render finished successfully"})
    write_progress(scene_name, "completed", "completed", extra={"message": "Done"})

    # ── Output ────────────────────────────────────────
    frame_count = len([f for f in os.listdir(frames_dir) if f.endswith(".png")]) if os.path.isdir(frames_dir) else 0
    final_size = os.path.getsize(final_mp4) if os.path.isfile(final_mp4) else 0

    if args.json:
        print(json.dumps({
            "scene": scene_name,
            "engine": engine,
            "output": final_mp4,
            "frames_dir": frames_dir,
            "frame_count": frame_count,
            "duration": duration,
            "fps": fps,
            "resolution": [width, height],
            "final_size_bytes": final_size,
            "log": log_file,
            "review_needed": not args.no_review,
        }, indent=2))
    else:
        print(f"Done: {final_mp4}")


if __name__ == "__main__":
    main()
