#!/usr/bin/env python3
"""pipeline/deliver.py
Deliver final artifact from .agent/tmp/ to output/ with metadata manifest.

Usage:
    deliver.py <scene_name> <tmp_dir> <output_dir>

Behavior:
    1. Copy {tmp_dir}/final.mp4 → {output_dir}/{scene_name}.mp4
    2. Compute SHA-256 of the output MP4
    3. Read {tmp_dir}/state.json for startedAt/endedAt/durationSec
    4. Read scene's manifest.json for engine/fps/duration/resolution
    5. Read engine version from engines/{engine}/engine.conf version_cmd
    6. Count frame_*.png in {tmp_dir}/frames/ (if exists)
    7. Write {output_dir}/{scene_name}_manifest.json
    8. Print summary to stdout

Exit: 0 on success, 1 on error
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys


def sha256_file(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def read_state_json(tmp_dir: str) -> dict:
    path = os.path.join(tmp_dir, "state.json")
    if not os.path.isfile(path):
        return {}
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return {}


def read_manifest(scene_dir: str) -> dict:
    path = os.path.join(scene_dir, "manifest.json")
    if not os.path.isfile(path):
        return {}
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return {}


def get_engine_version(project_root: str, engine: str) -> str:
    conf_path = os.path.join(project_root, "engines", engine, "engine.conf")
    if not os.path.isfile(conf_path):
        return "unknown"
    try:
        with open(conf_path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line.startswith("version_cmd:"):
                    cmd = line.split(":", 1)[1].strip()
                    # Remove surrounding quotes if present
                    if cmd.startswith('"') and cmd.endswith('"'):
                        cmd = cmd[1:-1]
                    # Decode escaped quotes
                    cmd = cmd.replace('\\"', '"')
                    if cmd:
                        result = subprocess.run(
                            cmd,
                            shell=True,
                            capture_output=True,
                            text=True,
                            timeout=10,
                            cwd=project_root,
                        )
                        if result.returncode == 0:
                            return result.stdout.strip()
                    break
    except Exception:
        pass
    return "unknown"


def count_frames(frames_dir: str) -> int:
    if not os.path.isdir(frames_dir):
        return 0
    return sum(1 for name in os.listdir(frames_dir) if name.startswith("frame_") and name.endswith(".png"))


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Deliver final artifact with metadata manifest.",
        usage="%(prog)s <scene_name> <tmp_dir> <output_dir>",
    )
    parser.add_argument("scene_name", help="Scene name (used for output filename)")
    parser.add_argument("tmp_dir", help="Temporary directory containing final.mp4 and state.json")
    parser.add_argument("output_dir", help="Output directory for deliverables")
    args = parser.parse_args()

    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    scene_dir = os.path.join(project_root, "scenes", args.scene_name)

    source_mp4 = os.path.join(args.tmp_dir, "final.mp4")
    if not os.path.isfile(source_mp4):
        print(f"[deliver] Error: source not found: {source_mp4}", file=sys.stderr)
        return 1

    os.makedirs(args.output_dir, exist_ok=True)

    output_mp4 = os.path.join(args.output_dir, f"{args.scene_name}.mp4")
    # Copy file
    try:
        import shutil
        shutil.copy2(source_mp4, output_mp4)
    except OSError as e:
        print(f"[deliver] Error: copy failed: {e}", file=sys.stderr)
        return 1

    # Compute SHA-256
    sha256 = sha256_file(output_mp4)

    # Read state
    state = read_state_json(args.tmp_dir)

    # Read manifest
    manifest = read_manifest(scene_dir)
    engine = manifest.get("engine", "manim")
    fps = manifest.get("fps", 30)
    duration = manifest.get("duration", 0.0)
    resolution = manifest.get("resolution", [1920, 1080])

    # Engine version
    engine_version = get_engine_version(project_root, engine)

    # Frame count
    frames_dir = os.path.join(args.tmp_dir, "frames")
    frames_rendered = count_frames(frames_dir)

    # Build manifest
    delivery_manifest = {
        "scene": args.scene_name,
        "engine": engine,
        "engine_version": engine_version,
        "duration_sec": float(duration),
        "fps": int(fps),
        "resolution": resolution,
        "frames_rendered": frames_rendered,
        "sha256": sha256,
        "rendered_at": state.get("endedAt", state.get("startedAt", "")),
    }

    manifest_path = os.path.join(args.output_dir, f"{args.scene_name}_manifest.json")
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(delivery_manifest, f, indent=2)
        f.write("\n")

    # Print summary
    print(f"[deliver] {source_mp4} → {output_mp4}")
    print(f"[deliver] SHA-256: {sha256}")
    print(f"[deliver] Frames: {frames_rendered}")
    print(f"[deliver] Engine: {engine} v{engine_version}")
    print(f"[deliver] Manifest: {manifest_path}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
