#!/usr/bin/env python3
"""bin/calc-preview-duration.py
Calculate preview duration from a scene manifest.

Logic:
1. Read manifest's 'duration' field.
2. If empty or 0, compute from segments' time_range.
3. If total > threshold, return max_preview seconds.
4. Otherwise return total duration.

Usage:
    calc-preview-duration.py <manifest.json> [--threshold 10] [--max-preview 3]

Exit codes:
    0 - success, prints duration to stdout
    1 - argument or file error
"""

import argparse
import json
import sys
from pathlib import Path


def get_duration(manifest_path: str) -> float:
    """Read duration from manifest, falling back to segments."""
    with open(manifest_path, encoding="utf-8") as f:
        data = json.load(f)

    # 1. Try explicit duration field
    dur = data.get("duration")
    if dur is not None:
        try:
            dur = float(dur)
            if dur > 0:
                return dur
        except (ValueError, TypeError):
            pass

    # 2. Fallback: compute from segments' time_range
    segments = data.get("segments", [])
    if not segments:
        return 0.0

    max_end = 0.0
    for seg in segments:
        tr = seg.get("time_range", [])
        if len(tr) >= 2:
            try:
                max_end = max(max_end, float(tr[1]))
            except (ValueError, TypeError):
                pass
    return max_end


def calc_preview_duration(manifest_path: str, threshold: float, max_preview: float) -> float:
    """Calculate preview duration based on total length."""
    total = get_duration(manifest_path)
    if total > threshold:
        return max_preview
    return total


def main():
    parser = argparse.ArgumentParser(
        description="Calculate preview duration from manifest.",
        usage="%(prog)s <manifest.json> [options]",
    )
    parser.add_argument("manifest", help="Path to manifest.json")
    parser.add_argument(
        "--threshold",
        type=float,
        default=10.0,
        help="Duration threshold in seconds (default: 10)",
    )
    parser.add_argument(
        "--max-preview",
        type=float,
        default=3.0,
        help="Max preview duration in seconds (default: 3)",
    )
    args = parser.parse_args()

    if not Path(args.manifest).is_file():
        print(f"Error: manifest not found: {args.manifest}", file=sys.stderr)
        sys.exit(1)

    result = calc_preview_duration(args.manifest, args.threshold, args.max_preview)
    print(result)


if __name__ == "__main__":
    main()
