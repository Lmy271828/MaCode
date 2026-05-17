#!/usr/bin/env python3
"""
bin/progress-write.py

追加标准 progress JSONL 记录到 .agent/progress/{scene}.jsonl。

用法:
    progress-write.py <progress_file> <phase> <status> [message]

状态值:
    running | completed | failed | timeout

示例:
    progress-write.py .agent/progress/01_test.jsonl init running "Starting render"
    progress-write.py .agent/progress/01_test.jsonl render completed "90 frames"
"""

from __future__ import annotations

import argparse
import os
import sys

_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
if _SCRIPT_DIR not in sys.path:
    sys.path.insert(0, _SCRIPT_DIR)

from macode_state import write_progress_to_path  # noqa: E402


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Append MaCode progress JSONL record",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument("progress_file", help="Path to JSONL file")
    parser.add_argument("phase", help="Phase name (e.g. init, render, capture)")
    parser.add_argument(
        "status",
        choices=["running", "completed", "failed", "timeout"],
        help="Progress status",
    )
    parser.add_argument(
        "message",
        nargs="?",
        default="",
        help="Optional human-readable message",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        write_progress_to_path(args.progress_file, args.phase, args.status, message=args.message)
    except OSError as exc:
        print(
            f"progress-write: failed to write {args.progress_file}: {exc}",
            file=sys.stderr,
        )
        return 1
    except TypeError as exc:
        print(f"progress-write: {exc}", file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
