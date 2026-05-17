#!/usr/bin/env python3
"""bin/auto-fix.py
Auto-fix orchestrator for MaCode scenes.

Reads check-static reports, applies fix strategies, verifies, and rolls back on failure.

Usage:
    auto-fix.py <scene_dir> [--max-rounds 3] [--dry-run]
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys

_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
if _SCRIPT_DIR not in sys.path:
    sys.path.insert(0, _SCRIPT_DIR)

STRATEGIES = {
    "adjust_wait": "fix_strategies.adjust_wait",
    "align_segment_comment": "fix_strategies.align_segment_comment",
}


def load_strategy(strategy_name: str):
    """Dynamically import a strategy module from bin/fix-strategies/."""
    module_path = STRATEGIES.get(strategy_name)
    if not module_path:
        return None
    try:
        mod = __import__(module_path, fromlist=["can_fix", "apply"])
        return mod
    except Exception as exc:
        print(f"[auto-fix] Failed to load strategy '{strategy_name}': {exc}", file=sys.stderr)
        return None


def run_checks(scene_dir: str) -> dict | None:
    """Run layer1 checks and return the JSON report."""
    result = subprocess.run(
        [
            sys.executable,
            os.path.join(_SCRIPT_DIR, "check-static.py"),
            scene_dir,
            "--layer",
            "layer1",
        ],
        capture_output=True,
        text=True,
    )
    if result.returncode not in (0, 1):
        print(f"[auto-fix] check-static failed: {result.stderr}", file=sys.stderr)
        return None
    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        print(f"[auto-fix] Failed to parse check output: {exc}", file=sys.stderr)
        return None


def collect_fixable_issues(report: dict) -> list[dict]:
    """Extract fixable issues with confidence >= 0.8 from a report."""
    issues = []
    for seg in report.get("segments", []):
        for issue in seg.get("issues", []):
            if issue.get("fixable") and issue.get("fix_confidence", 0) >= 0.8:
                issues.append(issue)
    for issue in report.get("issues", []):
        if issue.get("fixable") and issue.get("fix_confidence", 0) >= 0.8:
            issues.append(issue)
    # Sort by confidence descending
    issues.sort(key=lambda x: x.get("fix_confidence", 0), reverse=True)
    return issues


def apply_patches(patches: list[dict], dry_run: bool = False) -> None:
    """Apply patches to source files. Creates .autofix.bak backups."""
    for p in patches:
        file_path = p["file"]
        if not os.path.isfile(file_path):
            raise FileNotFoundError(f"Patch target not found: {file_path}")

        with open(file_path, encoding="utf-8") as f:
            lines = f.readlines()

        start = p["line_start"] - 1
        end = p["line_end"]
        old_text = p["old_text"]
        new_text = p["new_text"]

        # Verify old text matches
        current = "".join(lines[start:end])
        if current != old_text:
            raise ValueError(
                f"Patch mismatch at {file_path}:{start + 1}\n"
                f"Expected: {old_text!r}\nGot: {current!r}"
            )

        if dry_run:
            print(f"[dry-run] Would patch {file_path}:{start + 1}-{end}")
            print(f"  - {old_text!r}")
            print(f"  + {new_text!r}")
            continue

        # Only create backup when actually applying
        backup = file_path + ".autofix.bak"
        if not os.path.exists(backup):
            shutil.copy2(file_path, backup)

        lines[start:end] = [new_text]
        with open(file_path, "w", encoding="utf-8") as f:
            f.writelines(lines)


def rollback_patches(patches: list[dict]) -> None:
    """Restore files from .autofix.bak backups."""
    restored = set()
    for p in patches:
        file_path = p["file"]
        if file_path in restored:
            continue
        backup = file_path + ".autofix.bak"
        if os.path.isfile(backup):
            shutil.copy2(backup, file_path)
            restored.add(file_path)
            print(f"[auto-fix] Rolled back {file_path}")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Auto-fix scene issues based on check-static reports.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("scene_dir", help="Path to scene directory")
    parser.add_argument(
        "--max-rounds",
        type=int,
        default=3,
        help="Maximum auto-fix rounds (default: 3)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show patches without applying them",
    )
    args = parser.parse_args()

    scene_dir = args.scene_dir
    if not os.path.isdir(scene_dir):
        print(f"Error: directory not found: {scene_dir}", file=sys.stderr)
        return 2

    all_patches = []

    for round_num in range(1, args.max_rounds + 1):
        report = run_checks(scene_dir)
        if report is None:
            print("[auto-fix] Cannot run checks — aborting.")
            return 2

        fixable = collect_fixable_issues(report)
        if not fixable:
            print(f"[auto-fix] Round {round_num}: No fixable issues remain.")
            break

        issue = fixable[0]
        strategy_name = issue.get("fix", {}).get("strategy")
        strategy = load_strategy(strategy_name)
        if strategy is None:
            print(f"[auto-fix] Round {round_num}: Unknown strategy '{strategy_name}'.")
            break

        can_fix, confidence = strategy.can_fix(issue, scene_dir)
        if not can_fix:
            print(f"[auto-fix] Round {round_num}: Strategy says it cannot fix this issue.")
            break

        result = strategy.apply(issue, scene_dir)
        if not result.get("success"):
            print(f"[auto-fix] Round {round_num}: Fix failed — {result.get('message')}")
            break

        try:
            apply_patches(result["patches"], dry_run=args.dry_run)
        except Exception as exc:
            print(f"[auto-fix] Round {round_num}: Patch application failed — {exc}")
            rollback_patches(all_patches)
            return 1

        all_patches.extend(result["patches"])
        print(f"[auto-fix] Round {round_num}: {result['message']}")
        if result.get("verification_hint"):
            print(f"[auto-fix]   Hint: {result['verification_hint']}")

    # Final verification
    report = run_checks(scene_dir)
    if report is None:
        print("[auto-fix] Final check failed.")
        return 2

    # Derive status from report format (check-runner has top-level status,
    # check-static derives from segments)
    status = report.get("status")
    if status is None:
        status = "pass"
        for seg in report.get("segments", []):
            if seg.get("status") != "pass":
                status = seg.get("status", "warning")
                break

    if status == "pass":
        print("[auto-fix] All checks pass.")
        return 0
    else:
        remaining = collect_fixable_issues(report)
        if remaining:
            print(f"[auto-fix] {len(remaining)} fixable issue(s) remain after max rounds.")
        else:
            print("[auto-fix] Some issues remain but are not auto-fixable.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
