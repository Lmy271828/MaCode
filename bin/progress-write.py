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
import json
import os
import sys
from datetime import UTC, datetime


def iso_now() -> str:
    """Return ISO 8601 UTC timestamp with Z suffix."""
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


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

    progress_dir = os.path.dirname(args.progress_file)
    if progress_dir:
        os.makedirs(progress_dir, exist_ok=True)

    record: dict = {
        "timestamp": iso_now(),
        "phase": args.phase,
        "status": args.status,
    }
    if args.message:
        record["message"] = args.message

    try:
        with open(args.progress_file, "a") as f:
            f.write(json.dumps(record) + "\n")
    except OSError as exc:
        print(
            f"progress-write: failed to write {args.progress_file}: {exc}",
            file=sys.stderr,
        )
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
