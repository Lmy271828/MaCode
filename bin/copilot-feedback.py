#!/usr/bin/env python3
"""Optional human feedback: mark bad frames while a scene renders.

Decoupled from the render pipeline. Run in a second terminal:

    python3 bin/copilot-feedback.py watch <scene_name> [--pid ENGINE_PID]

``--pid`` is optional; when set, this process exits once that PID no longer exists
(useful to mirror the old render-integrated behaviour). Without ``--pid``, press
Ctrl+C to stop.

Ctrl+F records the current PNG count under ``.agent/tmp/<scene>/frames/`` and
appends a line to ``.agent/signals/frame_feedback.jsonl``.
"""

from __future__ import annotations

import argparse
import datetime
import json
import os
import select
import sys
import termios
import tty


def _record_feedback(scene_name: str, frame: int, feedback: str) -> None:
    os.makedirs(".agent/signals", exist_ok=True)
    path = ".agent/signals/frame_feedback.jsonl"
    with open(path, "a", encoding="utf-8") as f:
        rec = {
            "scene": scene_name,
            "frame": frame,
            "feedback": feedback,
            "timestamp": datetime.datetime.now().isoformat(),
        }
        json.dump(rec, f)
        f.write("\n")


def _count_png(frames_dir: str) -> int:
    if not os.path.isdir(frames_dir):
        return 0
    return len([name for name in os.listdir(frames_dir) if name.endswith(".png")])


def cmd_watch(args: argparse.Namespace) -> int:
    scene_name = args.scene
    frames_dir = os.path.join(".agent", "tmp", scene_name, "frames")
    os.makedirs(frames_dir, exist_ok=True)
    engine_pid = args.pid

    old = termios.tcgetattr(sys.stdin)
    tty.setcbreak(sys.stdin.fileno())
    print(f"[copilot-feedback] Watching {frames_dir}; Ctrl+F marks bad frame")
    if engine_pid is not None:
        print(f"[copilot-feedback] Exits when pid={engine_pid} is gone.")
    sys.stdout.flush()

    try:
        while True:
            if engine_pid is not None:
                try:
                    os.kill(engine_pid, 0)
                except ProcessLookupError:
                    break
                except PermissionError:
                    break

            ready, _, _ = select.select([sys.stdin], [], [], 0.2)
            if ready:
                ch = sys.stdin.read(1)
                if ch == "\x06":  # Ctrl+F
                    frame = _count_png(frames_dir)
                    print(f"\n[BAD FRAME] Scene: {scene_name} | Frame: ~{frame}")
                    print("Feedback: ", end="", flush=True)
                    termios.tcsetattr(sys.stdin, termios.TCSADRAIN, old)
                    feedback = input().strip()
                    tty.setcbreak(sys.stdin.fileno())
                    _record_feedback(scene_name, frame, feedback)
    finally:
        termios.tcsetattr(sys.stdin, termios.TCSADRAIN, old)
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Optional frame-quality feedback (not used by pipeline/render-scene.py).",
    )
    sub = parser.add_subparsers(dest="command", required=True)
    w = sub.add_parser("watch", help="Poll frames dir; Ctrl+F appends feedback JSONL")
    w.add_argument("scene", help="Scene basename (e.g. 01_test)")
    w.add_argument(
        "--pid",
        type=int,
        default=None,
        help="When set, exit once this process no longer exists",
    )
    w.set_defaults(func=cmd_watch)
    ns = parser.parse_args(argv)
    return int(ns.func(ns))


if __name__ == "__main__":
    raise SystemExit(main())
