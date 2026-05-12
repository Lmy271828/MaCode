#!/usr/bin/env python3
"""pipeline/validate-manifest.py

Validate a scene manifest.json using proper JSON parsing.
Replaces the fragile sed/grep-based validation in render.sh.

Usage:
    validate-manifest.py <manifest.json>

Exit codes:
    0 - manifest is valid
    1 - validation failed
"""

import argparse
import json
import os
import sys


def get_project_root() -> str:
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def validate(manifest_path: str) -> list:
    errors = []
    project_root = get_project_root()

    with open(manifest_path, encoding="utf-8") as f:
        try:
            data = json.load(f)
        except json.JSONDecodeError as e:
            return [f"Invalid JSON: {e}"]

    manifest_type = data.get("type", "single")

    if manifest_type == "composite":
        # Composite manifest validation
        if "segments" not in data:
            errors.append("Missing required field: segments (for composite manifest)")
        elif not isinstance(data["segments"], list):
            errors.append("segments must be an array")
        elif len(data["segments"]) == 0:
            errors.append("segments array must not be empty")
        else:
            segment_ids = set()
            for i, seg in enumerate(data["segments"]):
                if not isinstance(seg, dict):
                    errors.append(f"segments[{i}] must be an object")
                    continue
                seg_id = seg.get("id")
                if not seg_id:
                    errors.append(f"segments[{i}] missing required field: id")
                elif seg_id in segment_ids:
                    errors.append(f"Duplicate segment id: '{seg_id}'")
                else:
                    segment_ids.add(seg_id)

                scene_dir = seg.get("scene_dir")
                if not scene_dir:
                    errors.append(f"segments[{i}] missing required field: scene_dir")

            # Overlays validation
            overlays = data.get("overlays")
            if overlays is not None:
                if not isinstance(overlays, list):
                    errors.append("overlays must be an array")
                else:
                    valid_blends = {"overlay", "screen", "multiply", "add", "alphamerge"}
                    for i, ov in enumerate(overlays):
                        if not isinstance(ov, dict):
                            errors.append(f"overlays[{i}] must be an object")
                            continue
                        base = ov.get("base_segment")
                        fg = ov.get("foreground_segment")
                        if not base:
                            errors.append(f"overlays[{i}] missing required field: base_segment")
                        elif base not in segment_ids:
                            errors.append(f"overlays[{i}] base_segment '{base}' not found in segments")
                        if not fg:
                            errors.append(f"overlays[{i}] missing required field: foreground_segment")
                        elif fg not in segment_ids:
                            errors.append(f"overlays[{i}] foreground_segment '{fg}' not found in segments")
                        blend = ov.get("blend", "overlay")
                        if blend not in valid_blends:
                            errors.append(
                                f"overlays[{i}] invalid blend '{blend}'. "
                                f"Must be one of: {', '.join(sorted(valid_blends))}"
                            )

    else:
        # Single-scene manifest validation
        required = ["engine", "duration", "fps"]
        for field in required:
            if field not in data:
                errors.append(f"Missing required field: {field}")

        # Resolution is optional; render-scene.py defaults to [1920, 1080]
        resolution = data.get("resolution")
        if resolution is not None and (not isinstance(resolution, list) or len(resolution) != 2):
            errors.append("resolution must be an array of two integers: [width, height]")

        # Engine validation
        engine = data.get("engine")
        if engine:
            engine_conf = os.path.join(project_root, "engines", engine, "engine.conf")
            if not os.path.isfile(engine_conf):
                errors.append(f"Unsupported engine: '{engine}'")
                available = []
                engines_dir = os.path.join(project_root, "engines")
                if os.path.isdir(engines_dir):
                    for d in sorted(os.listdir(engines_dir)):
                        if os.path.isdir(os.path.join(engines_dir, d)):
                            available.append(d)
                if available:
                    errors.append(f"  Available engines: {', '.join(available)}")

        # Duration validation
        duration = data.get("duration")
        if duration is None:
            errors.append("duration is required")
        elif not isinstance(duration, (int, float)):
            errors.append(f"duration must be a number, got: {type(duration).__name__}")
        elif duration <= 0:
            errors.append(f"duration must be > 0, got: {duration}")

        # FPS validation
        fps = data.get("fps")
        if fps is None:
            errors.append("fps is required")
        elif not isinstance(fps, int) or fps <= 0:
            errors.append(f"fps must be a positive integer, got: {fps}")

        # Resolution validation (optional; render-scene.py defaults to [1920, 1080])
        resolution = data.get("resolution")
        if resolution is not None:
            if not isinstance(resolution, list) or len(resolution) != 2:
                errors.append(f"resolution must be [width, height], got: {resolution}")
            else:
                w, h = resolution
                if not isinstance(w, int) or not isinstance(h, int) or w <= 0 or h <= 0:
                    errors.append(f"resolution dimensions must be positive integers, got: {resolution}")

    return errors


def main():
    parser = argparse.ArgumentParser(
        description="Validate a scene manifest.json",
        usage="%(prog)s <manifest.json>",
        epilog="Examples:\n  %(prog)s scenes/01_test/manifest.json",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("manifest", help="Path to manifest.json")
    args = parser.parse_args()

    if not os.path.isfile(args.manifest):
        print(f"Error: manifest not found: {args.manifest}", file=sys.stderr)
        sys.exit(1)

    print("[validate] Checking manifest...")
    errors = validate(args.manifest)

    if errors:
        for err in errors:
            print(f"  ✗ {err}", file=sys.stderr)
        print("[validate] FAILED. Fix manifest.json before rendering.", file=sys.stderr)
        sys.exit(1)
    else:
        print("[validate] OK")
        sys.exit(0)


if __name__ == "__main__":
    main()
