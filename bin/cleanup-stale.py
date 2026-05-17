#!/usr/bin/env python3
"""bin/cleanup-stale.py
Scan and clean up stale task states under .agent/tmp.

Usage:
    cleanup-stale.py [--dry-run] [--logs]

Actions:
    - Mark running tasks with dead PIDs as "stalled" in state.json
    - Optional (--logs): prune .agent/log/*.log by retention policy
"""

import argparse
import json
import os
import sys
import time

LOG_KEEP_MOST_RECENT = 200
LOG_MAX_AGE_DAYS = 30
LOG_MAX_AGE_SECS = LOG_MAX_AGE_DAYS * 24 * 60 * 60


def get_project_root() -> str:
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def scan_stale_states(tmp_dir: str, dry_run: bool = False) -> int:
    """Mark running state.json entries with dead PIDs as stalled."""
    cleaned = 0
    if not os.path.isdir(tmp_dir):
        return cleaned

    for entry in os.listdir(tmp_dir):
        state_path = os.path.join(tmp_dir, entry, "state.json")
        if not os.path.isfile(state_path):
            continue
        try:
            with open(state_path, encoding="utf-8") as f:
                state = json.load(f)
        except (json.JSONDecodeError, OSError):
            continue

        if state.get("status") != "running":
            continue

        pid = state.get("pid")
        if pid is None:
            continue

        # Check if process is alive
        try:
            os.kill(pid, 0)
            continue  # process still alive
        except ProcessLookupError:
            pass  # dead process
        except PermissionError:
            continue  # alive but not our process

        # Mark as stalled
        if not dry_run:
            state["status"] = "stalled"
            state["stalled_at"] = time.time()
            tmp = state_path + ".tmp"
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(state, f, indent=2, ensure_ascii=False)
                f.write("\n")
            os.replace(tmp, state_path)
        cleaned += 1
        print(f"{'[dry-run] ' if dry_run else ''}Stalled: {entry} (pid={pid} dead)")

    return cleaned


def prune_agent_logs(log_dir: str, dry_run: bool = False) -> int:
    """Prune *.log under log_dir.

    Sorted by mtime descending: always keep the 200 newest files.
    Among the remainder, delete any file with mtime older than LOG_MAX_AGE_DAYS (30).
    Equivalent to deleting only logs that are both not in the top-200-most-recent AND
    older than 30 days (newer outliers beyond position 200 are kept).
    """
    deleted = 0
    if not os.path.isdir(log_dir):
        return deleted

    entries: list[tuple[float, str]] = []
    for name in os.listdir(log_dir):
        if not name.endswith(".log"):
            continue
        path = os.path.join(log_dir, name)
        if not os.path.isfile(path):
            continue
        try:
            mtime = os.path.getmtime(path)
        except OSError:
            continue
        entries.append((mtime, path))

    entries.sort(key=lambda x: x[0], reverse=True)
    now = time.time()
    cutoff = now - LOG_MAX_AGE_SECS
    remainder = entries[LOG_KEEP_MOST_RECENT:]

    for mtime, path in remainder:
        if mtime >= cutoff:
            continue
        rel = os.path.relpath(path, start=os.getcwd()) if os.path.isabs(path) else path
        print(f"{'[dry-run] ' if dry_run else ''}Delete log: {rel}")
        if not dry_run:
            try:
                os.remove(path)
            except OSError as e:
                print(f"  (skip: {e})", file=sys.stderr)
                continue
        deleted += 1

    return deleted


def main():
    parser = argparse.ArgumentParser(
        description="Clean up stalled task states (dead PIDs) under .agent/tmp."
    )
    parser.add_argument(
        "--dry-run", action="store_true", help="Show what would be cleaned without making changes"
    )
    parser.add_argument(
        "--logs",
        action="store_true",
        help=(
            "Prune .agent/log/*.log: sort by mtime (newest first), always keep the 200 newest; "
            f"among the rest, delete files older than {LOG_MAX_AGE_DAYS} days. "
            "With --dry-run, only print targets, no unlink."
        ),
    )
    args = parser.parse_args()

    project_root = get_project_root()
    os.chdir(project_root)

    tmp_dir = os.path.join(".agent", "tmp")

    stalled = scan_stale_states(tmp_dir, dry_run=args.dry_run)
    log_deleted = 0
    if args.logs:
        log_dir = os.path.join(".agent", "log")
        log_deleted = prune_agent_logs(log_dir, dry_run=args.dry_run)

    summary_parts = [f"{stalled} stalled state(s)"]
    if args.logs:
        summary_parts.append(f"log_deleted={log_deleted}")
    print("\nSummary: " + ", ".join(summary_parts))
    sys.exit(0)


if __name__ == "__main__":
    main()
