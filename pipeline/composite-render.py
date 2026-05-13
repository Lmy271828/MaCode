#!/usr/bin/env python3
"""pipeline/composite-render.py — DEPRECATED.

Per PRD D2, this split-render composite path is deprecated in favor of
``composite-unified-render.py`` (single Scene instance preserves narrative
state continuity across segments).

Direct invocation is preserved only as an escape hatch when the user sets
``MACODE_USE_LEGACY_COMPOSITE=1``. The canonical dispatcher
``pipeline/render.sh`` auto-routes ``type: composite`` manifests to
``composite-unified-render.py`` and emits a deprecation warning.

This file may be removed in a future Sprint once all manifests migrate to
``type: composite-unified``.
"""

import argparse
import json
import os
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed

_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_BIN_DIR = os.path.join(_PROJECT_ROOT, "bin")
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)
if _BIN_DIR not in sys.path:
    sys.path.insert(0, _BIN_DIR)
from macode_state import write_progress, write_state  # noqa: E402
from pipeline._render._paths import (  # noqa: E402
    get_project_root,
    get_python,
    read_manifest,
)


def get_max_concurrent(project_root: str, python: str) -> int:
    project_yaml = os.path.join(project_root, "project.yaml")
    if not os.path.isfile(project_yaml):
        return 4
    try:
        result = subprocess.run(
            [python, "-c", f"""
import yaml
with open('{project_yaml}') as f:
    d = yaml.safe_load(f)
print(d.get('agent', {{}}).get('resource_limits', {{}}).get('max_concurrent_scenes', 4))
"""],
            capture_output=True, text=True, check=False,
        )
        return int(result.stdout.strip())
    except Exception:
        return 4


def render_segment(project_root: str, full_dir: str, seg_name: str) -> tuple:
    """Render a single segment by invoking render.sh.

    Returns (success: bool, log: str).
    """
    try:
        result = subprocess.run(
            [
                python,
                os.path.join(project_root, "pipeline", "render-scene.py"),
                full_dir,
            ],
            capture_output=True,
            text=True,
            check=False,
            timeout=660,
        )
        log = result.stdout + result.stderr
        return result.returncode == 0, log
    except subprocess.TimeoutExpired as e:
        log = (e.stdout or "") + (e.stderr or "") + f"\n[composite] Segment '{seg_name}' timeout after 660s"
        return False, log
    except Exception as e:
        return False, str(e)


def main():
    parser = argparse.ArgumentParser(
        description="Render a composite scene (orchestrator).",
        usage="%(prog)s <scene_dir> [--json]",
        epilog="Examples:\n  %(prog)s scenes/04_composite_demo\n  %(prog)s scenes/04_composite_demo --json",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("scene_dir", help="Scene directory")
    parser.add_argument("--json", action="store_true", help="Output JSON result")
    args = parser.parse_args()

    scene_dir = args.scene_dir.rstrip("/")
    scene_name = os.path.basename(scene_dir)
    manifest_path = os.path.join(scene_dir, "manifest.json")
    project_root = get_project_root()
    python = get_python()

    if not os.path.isfile(manifest_path):
        print(f"Error: manifest.json not found in {scene_dir}", file=sys.stderr)
        sys.exit(1)

    manifest = read_manifest(manifest_path)
    segments = manifest.get("segments", [])
    count = len(segments)

    if count == 0:
        print("Error: composite manifest has no segments", file=sys.stderr)
        write_state(scene_name, "failed", exit_code=1)
        sys.exit(1)

    write_state(scene_name, "running")
    write_progress(scene_name, "composite_init", "running", message=f"{count} segments")

    max_concurrent = get_max_concurrent(project_root, python)
    print(
        f"[composite] Rendering {count} segments for '{scene_name}' "
        f"(max_concurrent={max_concurrent})..."
    )

    # ── Dependency-graph cache check ────────────────────
    cache_script = os.path.join(project_root, "bin", "composite-cache.py")
    cache_check = None
    if os.path.isfile(cache_script) and os.access(cache_script, os.X_OK):
        try:
            result = subprocess.run(
                [python, cache_script, "check", scene_dir, f".agent/tmp/{scene_name}"],
                capture_output=True, text=True, check=False,
            )
            if result.stdout.strip():
                cache_check = json.loads(result.stdout.strip())
        except Exception:
            pass

    # ── Collect segment metadata ────────────────────────
    seg_meta = []
    need_render_indices = []

    for idx, seg in enumerate(segments):
        seg_id = seg.get("id", "")
        seg_dir_rel = seg.get("scene_dir", "")
        trans = seg.get("transition")

        full_dir = os.path.join(scene_dir, seg_dir_rel)
        seg_name_basename = os.path.basename(full_dir)

        seg_cached = False
        seg_cached_video = ""
        if cache_check:
            for s in cache_check.get("segments", []):
                if s.get("id") == seg_id:
                    seg_cached = s.get("cached", False)
                    seg_cached_video = s.get("video", "")
                    break

        seg_output = f".agent/tmp/{seg_name_basename}/final.mp4"

        meta = {
            "idx": idx,
            "id": seg_id,
            "dir_rel": seg_dir_rel,
            "name": seg_name_basename,
            "full_dir": full_dir,
            "transition": trans,
            "cached_video": seg_cached_video,
            "output": seg_output,
        }
        seg_meta.append(meta)

        if seg_cached and seg_cached_video and os.path.isfile(seg_cached_video):
            print(f"[composite] [{idx + 1}/{count}] Segment '{seg_id}' cache HIT — skipping render")
        else:
            need_render_indices.append(idx)

    # ── Cross-segment parameter injection ───────────────
    params = manifest.get("params")
    if params:
        params_file = f".agent/tmp/.composite_params_{scene_name}.json"
        os.makedirs(".agent/tmp", exist_ok=True)
        with open(params_file, "w", encoding="utf-8") as f:
            json.dump(params, f, ensure_ascii=False)
        os.environ["MACODE_PARAMS_JSON"] = os.path.abspath(params_file)
        print(f"[composite] Params injected: {os.environ['MACODE_PARAMS_JSON']}")

    # ── Parallel render uncached segments ───────────────
    render_total = len(need_render_indices)
    if render_total > 0:
        print(
            f"[composite] Parallel rendering {render_total} segment(s) "
            f"(concurrency={max_concurrent})..."
        )

        def render_one(idx: int):
            meta = seg_meta[idx]
            seg_id = meta["id"]
            full_dir = meta["full_dir"]
            if not os.path.isfile(os.path.join(full_dir, "manifest.json")):
                return idx, False, f"Error: Segment '{seg_id}' manifest not found"
            print(f"[composite] [job] Starting segment '{seg_id}' ({full_dir})...")
            ok, log = render_segment(project_root, full_dir, seg_id)
            return idx, ok, log

        with ThreadPoolExecutor(max_workers=max_concurrent) as executor:
            futures = {executor.submit(render_one, idx): idx for idx in need_render_indices}
            for future in as_completed(futures):
                idx, ok, log = future.result()
                meta = seg_meta[idx]
                seg_id = meta["id"]
                if not ok:
                    print(f"[composite] Segment '{seg_id}' render FAILED. Log:", file=sys.stderr)
                    print(log, file=sys.stderr)
                    write_state(scene_name, "failed", exit_code=1)
                    sys.exit(1)
                seg_output = meta["output"]
                if not os.path.isfile(seg_output):
                    print(
                        f"[composite] Segment '{seg_id}' output not found: {seg_output}",
                        file=sys.stderr,
                    )
                    write_state(scene_name, "failed", exit_code=1)
                    sys.exit(1)
                print(f"[composite] [job] Segment '{seg_id}' OK")

    # ── Prepare output dir ──────────────────────────────
    output_dir = f".agent/tmp/{scene_name}"
    os.makedirs(output_dir, exist_ok=True)

    write_progress(
        scene_name,
        "composite_init",
        "running",
        message=f"Rendering {count} segments (max_concurrent={max_concurrent})",
    )

    # ── Build segments JSON for composite-assemble.py ───
    video_map = {}
    for meta in seg_meta:
        vid = meta["cached_video"]
        if vid and os.path.isfile(vid):
            video_map[meta["id"]] = vid
        else:
            video_map[meta["id"]] = meta["output"]

    # Build segments array with video paths and transitions
    segments_for_assemble = []
    for meta in seg_meta:
        seg_item = {
            "id": meta["id"],
            "video": video_map[meta["id"]],
        }
        if meta["transition"]:
            seg_item["transition"] = meta["transition"]
        segments_for_assemble.append(seg_item)

    overlays = manifest.get("overlays", [])

    # ── Delegate to composite-assemble.py (pure execution) ──
    print("[composite] Delegating assembly to composite-assemble.py...")
    write_progress(scene_name, "assemble", "running", message="Delegating to composite-assemble.py")

    assemble_cmd = [
        python,
        os.path.join(project_root, "bin", "composite-assemble.py"),
        "--scene-dir", scene_dir,
        "--segments", json.dumps(segments_for_assemble),
        "--overlays", json.dumps(overlays),
        "--manifest", manifest_path,
        "--output", f"{output_dir}/final.mp4",
    ]

    result = subprocess.run(assemble_cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"[composite] Assembly failed:\n{result.stderr}", file=sys.stderr)
        write_state(scene_name, "failed", exit_code=1)
        sys.exit(1)

    # Print assemble stdout (progress messages only, no JSON)
    print(result.stdout.strip())

    write_progress(scene_name, "composite_done", "completed", message=f"Output: {output_dir}/final.mp4")
    write_state(scene_name, "completed", exit_code=0)

    if args.json:
        final_size = (
            os.path.getsize(f"{output_dir}/final.mp4")
            if os.path.isfile(f"{output_dir}/final.mp4")
            else 0
        )
        print(
            json.dumps(
                {
                    "scene": scene_name,
                    "type": "composite",
                    "segments": count,
                    "output": f"{output_dir}/final.mp4",
                    "final_size_bytes": final_size,
                },
                indent=2,
            )
        )
    else:
        print(f"Done: {output_dir}/final.mp4")


if __name__ == "__main__":
    main()
