#!/usr/bin/env python3
"""pipeline/_render/orchestrator.py — thin orchestrator for single-scene render.

Stage order (all stages live in sibling modules):

    1. lifecycle.handle_override_or_exit / check_review_pending_or_exit  (exit 0/1/2/3)
    2. validate.validate_scene                                            → RenderContext
    3. engine.run                                                         → EngineResult
    4. encode.run                                                         → EncodeResult
    5. lifecycle.mark_review_if_needed                                    → review_needed
    6. emit JSON / text summary

Rollback: ``MACODE_USE_LEGACY_RENDER=1`` reverts to ``pipeline/render_scene_legacy.py``.
"""

from __future__ import annotations

import argparse
import json
import os
import sys

_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
_PIPELINE_DIR = os.path.dirname(_SCRIPT_DIR)
_ROOT = os.path.dirname(_PIPELINE_DIR)
_BIN_DIR = os.path.join(_ROOT, "bin")
if _BIN_DIR not in sys.path:
    sys.path.insert(0, _BIN_DIR)

# Imports must follow sys.path insertion above
from pipeline._render import encode, engine, lifecycle, validate  # noqa: E402


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Render a single scene (orchestrator).",
        usage="%(prog)s <scene_dir> [options]",
        epilog="Examples:\n"
               "  %(prog)s scenes/01_test\n"
               "  %(prog)s scenes/01_test --fps 2 --duration 1\n"
               "  %(prog)s scenes/01_test --json",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("scene_dir", help="Scene directory")
    parser.add_argument("--json", action="store_true", help="Output JSON result")
    parser.add_argument("--fps", type=int, default=None, help="Override FPS")
    parser.add_argument("--duration", type=float, default=None, help="Override duration")
    parser.add_argument("--width", type=int, default=None, help="Override width")
    parser.add_argument("--height", type=int, default=None, help="Override height")
    parser.add_argument(
        "--no-review",
        action="store_true",
        help="Skip review-needed marking (for batch testing)",
    )
    parser.add_argument(
        "--skip-checks",
        action="store_true",
        help="Skip static checks (for manual debugging)",
    )
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    scene_dir = args.scene_dir.rstrip("/")
    scene_name = os.path.basename(scene_dir)

    ctx_lc = lifecycle.prepare_lifecycle(scene_name, no_review=args.no_review)
    lifecycle.handle_override_or_exit(ctx_lc)
    lifecycle.check_review_pending_or_exit(ctx_lc)

    rctx = validate.validate_scene(
        scene_dir=scene_dir,
        scene_name=scene_name,
        args_fps=args.fps,
        args_duration=args.duration,
        args_width=args.width,
        args_height=args.height,
        skip_checks=args.skip_checks,
    )

    eresult = engine.run(rctx)
    encresult = encode.run(rctx, cache_hit=eresult.cache_hit)

    lifecycle.progress(
        scene_name, "cleanup", "completed", message="Render finished successfully"
    )
    lifecycle.progress(scene_name, "completed", "completed", message="Done")
    lifecycle.mark_review_if_needed(ctx_lc)

    final_size = (
        os.path.getsize(encresult.final_mp4) if os.path.isfile(encresult.final_mp4) else 0
    )
    if args.json:
        print(
            json.dumps(
                {
                    "scene": scene_name,
                    "engine": rctx.engine,
                    "output": encresult.final_mp4,
                    "frames_dir": rctx.frames_dir,
                    "frame_count": encresult.frame_count,
                    "duration": rctx.duration,
                    "fps": rctx.fps,
                    "resolution": [rctx.width, rctx.height],
                    "final_size_bytes": final_size,
                    "log": rctx.log_file,
                    "review_needed": not args.no_review,
                },
                indent=2,
            )
        )
    else:
        print(f"Done: {encresult.final_mp4}")


if __name__ == "__main__":
    main()
