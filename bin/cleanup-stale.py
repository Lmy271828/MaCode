#!/usr/bin/env python3
"""bin/cleanup-stale.py
Scan and clean up stale agent states.

Usage:
    cleanup-stale.py [--dry-run]

Actions:
    - Mark running tasks with dead PIDs as "stalled"
    - Remove expired scene claim files (older than CLAIM_TTL)
    - Remove orphaned claim files without matching state.json
"""

import argparse
import json
import os
import sys
import time


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


def scan_expired_claims(tmp_dir: str, ttl: float = 600, dry_run: bool = False) -> int:
    """Remove expired scene claim files."""
    cleaned = 0
    if not os.path.isdir(tmp_dir):
        return cleaned

    now = time.time()
    for entry in os.listdir(tmp_dir):
        claim_path = os.path.join(tmp_dir, entry, ".claimed_by")
        if not os.path.isfile(claim_path):
            continue
        try:
            with open(claim_path, encoding="utf-8") as f:
                data = json.load(f)
            claimed_at = data.get("claimed_at", 0)
            if now - claimed_at > ttl:
                if not dry_run:
                    os.remove(claim_path)
                cleaned += 1
                print(f"{'[dry-run] ' if dry_run else ''}Expired claim: {entry} ({now - claimed_at:.0f}s old)")
        except (json.JSONDecodeError, OSError):
            # Corrupt claim file, remove it
            if not dry_run:
                try:
                    os.remove(claim_path)
                except OSError:
                    pass
            cleaned += 1
            print(f"{'[dry-run] ' if dry_run else ''}Corrupt claim: {entry}")

    return cleaned


def main():
    parser = argparse.ArgumentParser(description="Clean up stale agent states and expired claims.")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be cleaned without making changes")
    parser.add_argument("--ttl", type=int, default=600, help="Claim TTL in seconds (default: 600)")
    args = parser.parse_args()

    project_root = get_project_root()
    os.chdir(project_root)

    tmp_dir = os.path.join(".agent", "tmp")

    stalled = scan_stale_states(tmp_dir, dry_run=args.dry_run)
    expired = scan_expired_claims(tmp_dir, ttl=args.ttl, dry_run=args.dry_run)

    print(f"\nSummary: {stalled} stalled state(s), {expired} expired claim(s)")
    sys.exit(0)


if __name__ == "__main__":
    main()
