#!/usr/bin/env python3
"""
bin/signal-check.py
Check human-intervention signals (global + per-scene).

Supports concurrent rendering: each scene can have independent signals.
Global signals (pause, abort) affect all scenes.
Per-scene signals (pause, abort, human_override, reject, feedback)
affect only that scene.

Usage:
    signal-check.py [--scene <scene_name>] [--global] [--help]

Exit codes:
    0 - signals checked successfully

Examples:
    signal-check.py                    # Check all signals
    signal-check.py --scene 01_test    # Check signals for specific scene
    signal-check.py --global           # Check only global signals
"""

import argparse
import json
from pathlib import Path


def get_project_root() -> Path:
    return Path(__file__).parent.parent


def check_global_signals(signals_dir: Path) -> dict:
    """Check global-level signals (pause, abort)."""
    return {
        "pause": (signals_dir / "global" / "pause").exists(),
        "abort": (signals_dir / "global" / "abort").exists(),
    }


def check_scene_signals(scene_dir: Path) -> dict:
    """Check per-scene signals (pause, abort, human_override, reject, feedback)."""
    result = {
        "pause": (scene_dir / "pause").exists(),
        "abort": (scene_dir / "abort").exists(),
        "reject": (scene_dir / "reject").exists(),
        "human_override": None,
        "frame_feedback": [],
    }

    override_path = scene_dir / "human_override.json"
    if override_path.exists():
        try:
            result["human_override"] = json.loads(override_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            pass

    feedback_path = scene_dir / "frame_feedback.jsonl"
    if feedback_path.exists():
        try:
            with open(feedback_path, encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line:
                        result["frame_feedback"].append(json.loads(line))
        except (json.JSONDecodeError, OSError):
            pass

    return result


def main():
    parser = argparse.ArgumentParser(
        description="Check human-intervention signals.",
        usage="%(prog)s [--scene <name>] [--global]",
        epilog="Examples:\n"
        "  %(prog)s                    # Check all signals\n"
        "  %(prog)s --scene 01_test    # Check specific scene\n"
        "  %(prog)s --global           # Check only global signals",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--scene", help="Check signals for a specific scene")
    parser.add_argument("--global-only", action="store_true", help="Check only global signals")
    args = parser.parse_args()

    project_root = get_project_root()
    signals_dir = project_root / ".agent" / "signals"
    signals_dir.mkdir(parents=True, exist_ok=True)

    result = {}

    # ── Global signals ──
    if args.scene is None or args.global_only:
        result["global"] = check_global_signals(signals_dir)

    # ── Per-scene signals ──
    if not args.global_only:
        per_scene_dir = signals_dir / "per-scene"
        per_scene_dir.mkdir(parents=True, exist_ok=True)

        if args.scene:
            # Check specific scene
            scene_dir = per_scene_dir / args.scene
            result["scenes"] = {args.scene: check_scene_signals(scene_dir)}
        else:
            # Check all scenes
            result["scenes"] = {}
            if per_scene_dir.exists():
                for scene_dir in sorted(per_scene_dir.iterdir()):
                    if scene_dir.is_dir():
                        result["scenes"][scene_dir.name] = check_scene_signals(scene_dir)

    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
