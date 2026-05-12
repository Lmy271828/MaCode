#!/usr/bin/env python3
"""
bin/state-write.py

生成标准 v1.0 state.json（MaCode Task State Schema）。
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
        --error "ModuleNotFoundError: No module named 'manim'"
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
        description="Write MaCode Task State v1.0 state.json",
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


def load_existing_state(state_path: str) -> dict:
    """Load existing state.json if present, else empty dict."""
    if os.path.exists(state_path):
        try:
            with open(state_path) as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError):
            pass
    return {}


def merge_outputs(existing: dict | None, new_outputs: dict | None) -> dict | None:
    """Merge new outputs into existing outputs. New keys win."""
    if existing is None:
        return new_outputs
    if new_outputs is None:
        return existing
    merged = dict(existing)
    merged.update(new_outputs)
    return merged


def compute_duration(started_at: str | None, ended_at: str | None) -> float | None:
    """Compute durationSec from startedAt and endedAt if not explicitly set."""
    if not started_at or not ended_at:
        return None
    try:
        # Parse ISO 8601 with or without Z suffix
        fmt = "%Y-%m-%dT%H:%M:%SZ"
        s = started_at.replace("+00:00", "Z")
        e = ended_at.replace("+00:00", "Z")
        if not s.endswith("Z"):
            s = s[:19] + "Z"
        if not e.endswith("Z"):
            e = e[:19] + "Z"
        ds = datetime.strptime(s, fmt)
        de = datetime.strptime(e, fmt)
        return (de - ds).total_seconds()
    except (ValueError, TypeError):
        return None


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)

    state_dir = args.state_dir
    os.makedirs(state_dir, exist_ok=True)
    state_path = os.path.join(state_dir, "state.json")

    existing = load_existing_state(state_path)

    # Parse outputs JSON if provided
    outputs = None
    if args.outputs:
        try:
            outputs = json.loads(args.outputs)
        except json.JSONDecodeError as exc:
            print(f"state-write: invalid --outputs JSON: {exc}", file=sys.stderr)
            return 1

    # Determine timestamps
    is_terminal = args.status in ("completed", "failed", "timeout")

    started_at = args.started_at or existing.get("startedAt")
    if args.status == "running" and not started_at:
        started_at = iso_now()

    ended_at = args.ended_at or existing.get("endedAt")
    if is_terminal and not ended_at:
        ended_at = iso_now()

    # Determine duration
    duration = args.duration
    if duration is None and is_terminal:
        duration = compute_duration(started_at, ended_at)
        if duration is None:
            duration = existing.get("durationSec")

    # Build state object
    state: dict = {
        "version": "1.0",
        "tool": args.tool or existing.get("tool", "unknown"),
        "status": args.status,
    }

    if args.task_id or existing.get("taskId"):
        state["taskId"] = args.task_id or existing.get("taskId")

    if args.exit_code is not None:
        state["exitCode"] = args.exit_code
    elif "exitCode" in existing:
        state["exitCode"] = existing["exitCode"]

    if started_at:
        state["startedAt"] = started_at
    if ended_at:
        state["endedAt"] = ended_at
    if duration is not None:
        state["durationSec"] = duration

    merged_outputs = merge_outputs(existing.get("outputs"), outputs)
    if merged_outputs:
        state["outputs"] = merged_outputs

    if args.error:
        state["error"] = args.error
    elif existing.get("error") and not is_terminal:
        # Preserve existing error only if not terminal (we may be recovering)
        state["error"] = existing["error"]
    # If terminal and no new error, clear old error on success
    if is_terminal and args.status == "completed":
        state.pop("error", None)

    # Atomic write
    tmp_path = state_path + ".tmp"
    try:
        with open(tmp_path, "w") as f:
            json.dump(state, f, indent=2)
            f.write("\n")
        os.replace(tmp_path, state_path)
    except OSError as exc:
        print(f"state-write: failed to write {state_path}: {exc}", file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
