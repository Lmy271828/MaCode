#!/usr/bin/env python3
"""bin/composite-overlay.py
Composite overlay processor — merge foreground videos onto base videos using ffmpeg overlay.

Usage:
    composite-overlay.py output.mp4 --base <base_video> --foreground <fg_video> [opts]

Options:
    --start <sec>       Start time of overlay (default: 0)
    --duration <sec>    Duration of overlay (default: min(base, fg) duration)
    --x <n>             X offset (default: 0, supports ffmpeg expressions like (W-w)/2)
    --y <n>             Y offset (default: 0, supports ffmpeg expressions like (H-h)/2)
    --blend <mode>      Blend mode: overlay, screen, multiply, add (default: overlay)
"""

import argparse
import subprocess
import sys


def get_duration(path: str) -> float:
    result = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "default=noprint_wrappers=1:nokey=1", path],
        capture_output=True, text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(f"ffprobe failed: {result.stderr}")
    return float(result.stdout.strip())


def main():
    parser = argparse.ArgumentParser(description="Overlay foreground video onto base video.")
    parser.add_argument("output", help="Output video path")
    parser.add_argument("--base", "-b", required=True, help="Base video path")
    parser.add_argument("--foreground", "-f", required=True, help="Foreground video path")
    parser.add_argument("--start", type=float, default=0.0, help="Overlay start time (sec)")
    parser.add_argument("--duration", type=float, default=None, help="Overlay duration (sec)")
    parser.add_argument("--x", default="0", help="X offset (ffmpeg expression)")
    parser.add_argument("--y", default="0", help="Y offset (ffmpeg expression)")
    parser.add_argument("--blend", default="overlay",
                        choices=["overlay", "screen", "multiply", "add", "alphamerge"],
                        help="Blend mode")
    args = parser.parse_args()

    base_dur = get_duration(args.base)
    fg_dur = get_duration(args.foreground)
    duration = args.duration or min(base_dur, fg_dur)

    # Build filtergraph
    # Enable overlay between start and start+duration
    end = args.start + duration
    enable_expr = f"between(t,{args.start:.3f},{end:.3f})"

    # If blend mode is overlay (default), use overlay filter
    # For other modes, use blend filter or lutryb
    if args.blend == "overlay" or args.blend == "alphamerge":
        filter_str = (
            f"[0:v][1:v]overlay=x={args.x}:y={args.y}:enable='{enable_expr}'[v]"
        )
    else:
        # Use blend filter for other modes
        filter_str = (
            f"[0:v][1:v]blend=all_mode={args.blend}:enable='{enable_expr}'[v]"
        )

    cmd = [
        "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
        "-i", args.base,
        "-i", args.foreground,
        "-filter_complex", filter_str,
        "-map", "[v]",
        "-c:v", "libx264", "-pix_fmt", "yuv420p", "-movflags", "+faststart",
        args.output,
    ]

    print(f"[overlay] Base: {args.base} ({base_dur:.2f}s)")
    print(f"[overlay] Foreground: {args.foreground} ({fg_dur:.2f}s)")
    print(f"[overlay] Blend: {args.blend}, start={args.start:.2f}, duration={duration:.2f}, x={args.x}, y={args.y}")

    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"[overlay] ffmpeg failed:\n{result.stderr}", file=sys.stderr)
        sys.exit(1)

    print(f"[overlay] Done: {args.output}")


if __name__ == "__main__":
    main()
