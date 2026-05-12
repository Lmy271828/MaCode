#!/usr/bin/env python3
"""bin/copilot-feedback.py
Capture Ctrl+F bad-frame feedback during engine rendering.

Waits for the engine process to finish while monitoring stdin for Ctrl+F
keystrokes. When Ctrl+F is pressed, records the current frame count and
user feedback to .agent/signals/frame_feedback.jsonl.

Usage:
    copilot-feedback.py <scene_name> <frames_dir> <engine_pid>

Exit: 0 when engine exits normally, 1 on error
"""

import datetime
import json
import os
import select
import sys
import termios
import tty


def main():
    if len(sys.argv) < 4:
        print("Usage: copilot-feedback.py <scene_name> <frames_dir> <engine_pid>", file=sys.stderr)
        sys.exit(1)

    scene_name = sys.argv[1]
    frames_dir = sys.argv[2]
    engine_pid = int(sys.argv[3])

    old = termios.tcgetattr(sys.stdin)
    tty.setcbreak(sys.stdin.fileno())
    print("[render] Press Ctrl+F to mark bad frame")
    sys.stdout.flush()

    try:
        while True:
            try:
                os.kill(engine_pid, 0)
            except ProcessLookupError:
                break

            ready, _, _ = select.select([sys.stdin], [], [], 0.1)
            if ready:
                ch = sys.stdin.read(1)
                if ch == "\x06":  # Ctrl+F
                    frame = len([f for f in os.listdir(frames_dir) if f.endswith(".png")])
                    print(f"\n[BAD FRAME] Scene: {scene_name} | Frame: ~{frame}")
                    print("Feedback: ", end="", flush=True)
                    termios.tcsetattr(sys.stdin, termios.TCSADRAIN, old)
                    feedback = input().strip()
                    tty.setcbreak(sys.stdin.fileno())

                    os.makedirs(".agent/signals", exist_ok=True)
                    with open(".agent/signals/frame_feedback.jsonl", "a", encoding="utf-8") as f:
                        rec = {
                            "scene": scene_name,
                            "frame": frame,
                            "feedback": feedback,
                            "timestamp": datetime.datetime.now().isoformat(),
                        }
                        json.dump(rec, f)
                        f.write("\n")
    finally:
        termios.tcsetattr(sys.stdin, termios.TCSADRAIN, old)


if __name__ == "__main__":
    main()
