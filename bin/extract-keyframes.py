#!/usr/bin/env python3
"""bin/extract-keyframes.py
Extract keyframe PNGs from an MP4 using ffmpeg.

Usage:
    extract-keyframes.py <mp4> --output-dir <dir> [--times 0.0 1.5 3.0]
    extract-keyframes.py <mp4> --output-dir <dir> --count 5
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys


def get_duration(mp4_path: str) -> float:
    result = subprocess.run(
        [
            "ffprobe",
            "-v",
            "error",
            "-show_entries",
            "format=duration",
            "-of",
            "default=noprint_wrappers=1:nokey=1",
            mp4_path,
        ],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(f"ffprobe failed: {result.stderr}")
    return float(result.stdout.strip())


def extract_keyframes(mp4_path: str, output_dir: str, times: list[float] | None = None, count: int = 5) -> dict:
    os.makedirs(output_dir, exist_ok=True)

    if times is None:
        duration = get_duration(mp4_path)
        if duration <= 0:
            times = [0.0]
        elif count == 1:
            times = [0.0]
        else:
            times = [duration * i / (count - 1) for i in range(count)]

    manifest = {"source": mp4_path, "count": len(times), "keyframes": []}

    for t in times:
        timestamp = f"{t:.3f}"
        safe_ts = timestamp.replace(".", "_")
        out_file = os.path.join(output_dir, f"keyframe_{safe_ts}.png")
        subprocess.run(
            [
                "ffmpeg",
                "-y",
                "-hide_banner",
                "-loglevel",
                "error",
                "-ss",
                str(t),
                "-i",
                mp4_path,
                "-vframes",
                "1",
                "-q:v",
                "2",
                out_file,
            ],
            capture_output=True,
            check=False,
        )
        if os.path.isfile(out_file):
            manifest["keyframes"].append({"time": t, "file": out_file})

    manifest["extracted"] = len(manifest["keyframes"])
    manifest_path = os.path.join(output_dir, "manifest.json")
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2, ensure_ascii=False)
        f.write("\n")

    return manifest


def main() -> int:
    parser = argparse.ArgumentParser(description="Extract keyframes from MP4")
    parser.add_argument("mp4", help="Input MP4 file")
    parser.add_argument("--output-dir", "-o", required=True, help="Output directory for PNGs")
    parser.add_argument("--times", nargs="+", type=float, help="Explicit timestamps in seconds")
    parser.add_argument("--count", type=int, default=5, help="Number of evenly-spaced keyframes")
    args = parser.parse_args()

    if not os.path.isfile(args.mp4):
        print(f"Error: file not found: {args.mp4}", file=sys.stderr)
        return 2

    manifest = extract_keyframes(args.mp4, args.output_dir, args.times, args.count)
    print(f"Extracted {manifest['extracted']}/{manifest['count']} keyframes to {args.output_dir}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
