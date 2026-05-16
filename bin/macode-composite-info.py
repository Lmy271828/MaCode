#!/usr/bin/env python3
"""Print composite scene info from manifest.json.

Usage: macode-composite-info.py <scene_dir>
"""

import json
import os
import sys


def main() -> int:
    if len(sys.argv) < 2:
        print("Usage: macode-composite-info.py <scene_dir>", file=sys.stderr)
        return 1

    scene_dir = sys.argv[1]
    manifest_path = os.path.join(scene_dir, "manifest.json")
    if not os.path.isfile(manifest_path):
        print(f"Error: manifest.json not found in {scene_dir}", file=sys.stderr)
        return 1

    with open(manifest_path, encoding="utf-8") as f:
        manifest = json.load(f)

    print(f"Scene: {os.path.basename(os.path.normpath(scene_dir))}")
    print(f"Type: {manifest.get('type', 'scene')}")
    print("")
    print("Segments:")

    total = 0.0
    for seg in manifest.get("segments", []):
        seg_path = seg.get("scene_dir") or seg.get("shot") or "N/A"
        trans = seg.get("transition")
        trans_str = f" [transition: {trans['type']} {trans['duration']}s]" if trans else ""
        print(f"  - {seg['id']}: {seg_path}{trans_str}")

        dmanifest = os.path.join(scene_dir, seg_path, "manifest.json")
        if os.path.isfile(dmanifest):
            with open(dmanifest, encoding="utf-8") as f:
                data = json.load(f)
            dur = float(data.get("duration", 0))
            print(f"    duration: {dur}s")
            total += dur

    print("")
    print(f"Total (raw): {total:.2f}s")
    return 0


if __name__ == "__main__":
    sys.exit(main())
