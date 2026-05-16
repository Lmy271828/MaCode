#!/usr/bin/env python3
"""
bin/state-write.py

写入 OrchestrationState v1.1 state.json。
支持原子写入和已有 state 的合并。

用法:
    state-write.py <state_dir> <status> [exit_code]
        [--tool NAME] [--outputs JSON] [--error MSG]
        [--started-at ISO] [--ended-at ISO] [--duration SEC]
        [--task-id ID]

状态值:
    running | completed | failed | timeout

示例:
    state-write.py .agent/tmp/01_test running --tool render.sh
    state-write.py .agent/tmp/01_test completed 0 \
        --outputs '{"framesRendered": 90}'
    state-write.py .agent/tmp/01_test failed 1 \
        --error "ModuleNotFoundError: no module named 'manim'"
"""

from __future__ import annotations

import argparse
import json
import os
import sys

_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
if _SCRIPT_DIR not in sys.path:
    sys.path.insert(0, _SCRIPT_DIR)

from macode_state import write_state_to_path  # noqa: E402


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Write OrchestrationState v1.1 state.json",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument("state_dir", help="Directory to write state.json")
    parser.add_argument(
        "status",
        choices=["running", "completed", "failed", "timeout"],
        help="Task status",
    )
    parser.add_argument(
        "exit_code",
        nargs="?",
        type=int,
        default=None,
        help="Process exit code (optional)",
    )
    parser.add_argument("--tool", default="", help="Tool name (e.g. render.sh)")
    parser.add_argument(
        "--outputs", default="", help='JSON string for outputs object (e.g. \'{"port":80}\')'
    )
    parser.add_argument("--error", default="", help="Human-readable error message")
    parser.add_argument(
        "--started-at", default="", help="ISO 8601 start timestamp"
    )
    parser.add_argument(
        "--ended-at", default="", help="ISO 8601 end timestamp"
    )
    parser.add_argument(
        "--duration", type=float, default=None, help="Wall-clock duration in seconds"
    )
    parser.add_argument("--task-id", default="", help="Task identifier")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)

    outputs = None
    if args.outputs:
        try:
            outputs = json.loads(args.outputs)
        except json.JSONDecodeError as exc:
            print(f"state-write: invalid --outputs JSON: {exc}", file=sys.stderr)
            return 1

    state_path = os.path.join(args.state_dir, "state.json")
    task_id = args.task_id or os.path.basename(os.path.normpath(args.state_dir))

    try:
        write_state_to_path(
            state_path,
            task_id,
            args.status,
            exit_code=args.exit_code if args.exit_code is not None else 0,
            outputs=outputs,
            error=args.error or None,
            started_at=args.started_at or None,
            ended_at=args.ended_at or None,
            duration_sec=args.duration,
            tool=args.tool or None,
        )
    except OSError as exc:
        print(f"state-write: failed to write state: {exc}", file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
