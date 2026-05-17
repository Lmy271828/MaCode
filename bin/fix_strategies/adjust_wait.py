#!/usr/bin/env python3
"""bin/fix-strategies/adjust_wait.py
Fix strategy for duration_mismatch issues.

Adjusts self.wait() duration or yield* wait times to match declared duration.
"""

from __future__ import annotations

import os
import re
import sys

_SCRIPT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _SCRIPT_DIR not in sys.path:
    sys.path.insert(0, _SCRIPT_DIR)

from checks._utils import find_source_file


def can_fix(issue: dict, scene_dir: str) -> tuple[bool, float]:
    """Check if this issue can be fixed by adjusting wait/play durations."""
    if issue.get("type") != "duration_mismatch":
        return False, 0.0
    fix = issue.get("fix", {})
    if fix.get("strategy") != "adjust_wait":
        return False, 0.0
    return True, issue.get("fix_confidence", 0.0)


def apply(issue: dict, scene_dir: str) -> dict:
    """Generate patch(es) to fix the duration mismatch.

    Returns a dict with keys:
        success: bool
        patches: list[dict] — each patch has file, line_start, line_end, old_text, new_text
        message: str
        verification_hint: str
    """
    scene_file = find_source_file(scene_dir)
    if not scene_file:
        return {"success": False, "patches": [], "message": "Scene file not found"}

    with open(scene_file, encoding="utf-8") as f:
        lines = f.readlines()

    suggested = issue.get("suggested_lines", [1, len(lines)])
    start = max(1, suggested[0]) if suggested else 1
    end = min(len(lines), suggested[1]) if len(suggested) > 1 else len(lines)

    target = issue.get("fix", {}).get("params", {}).get("target_duration")
    if target is None:
        target = issue.get("declared", 0.0)
    computed = issue.get("computed", 0.0)
    delta = computed - target  # positive = need to reduce total time

    is_mc = scene_file.endswith(".tsx")

    if is_mc:
        return _fix_mc(lines, start, end, delta, scene_file)
    else:
        return _fix_python(lines, start, end, delta, scene_file)


def _fix_python(lines: list[str], start: int, end: int, delta: float, scene_file: str) -> dict:
    """Adjust self.wait() or self.play(..., run_time=...) in Python scenes."""
    # Pattern: self.wait(<number>)
    wait_re = re.compile(r"self\.wait\(([^)]+)\)")
    # Pattern: run_time=<number>
    runtime_re = re.compile(r"run_time\s*=\s*([0-9.]+)")

    waits = []
    runtimes = []
    for i in range(start - 1, end):
        line = lines[i]
        for m in wait_re.finditer(line):
            try:
                val = float(m.group(1))
                waits.append((i, m.start(), m.end(), val, line))
            except ValueError:
                continue
        for m in runtime_re.finditer(line):
            try:
                val = float(m.group(1))
                runtimes.append((i, m.start(), m.end(), val, line))
            except ValueError:
                continue

    patches = []
    message = ""

    if waits and delta > 0:
        # Reduce the last wait (safest — usually at segment end)
        line_idx, m_start, m_end, old_val, old_line = waits[-1]
        new_val = max(0.1, old_val - delta)
        new_val = round(new_val, 2)
        # Preserve formatting (e.g. self.wait( 2.0 ) -> self.wait( 1.5 ))
        new_line = old_line[:m_start] + f"self.wait({new_val})" + old_line[m_end:]
        patches.append(
            {
                "file": scene_file,
                "line_start": line_idx + 1,
                "line_end": line_idx + 1,
                "old_text": old_line,
                "new_text": new_line,
            }
        )
        message = f"Adjusted self.wait({old_val}) -> self.wait({new_val}) at line {line_idx + 1}"
    elif waits and delta < 0:
        # Increase the last wait
        line_idx, m_start, m_end, old_val, old_line = waits[-1]
        new_val = old_val + abs(delta)
        new_val = round(new_val, 2)
        new_line = old_line[:m_start] + f"self.wait({new_val})" + old_line[m_end:]
        patches.append(
            {
                "file": scene_file,
                "line_start": line_idx + 1,
                "line_end": line_idx + 1,
                "old_text": old_line,
                "new_text": new_line,
            }
        )
        message = f"Adjusted self.wait({old_val}) -> self.wait({new_val}) at line {line_idx + 1}"
    elif runtimes and delta > 0:
        # Reduce the longest run_time
        runtimes.sort(key=lambda x: x[3], reverse=True)
        line_idx, m_start, m_end, old_val, old_line = runtimes[0]
        reducible = min(old_val - 0.1, delta)
        if reducible > 0.05:
            new_val = max(0.1, old_val - reducible)
            new_val = round(new_val, 2)
            new_line = old_line[:m_start] + f"run_time={new_val}" + old_line[m_end:]
            patches.append(
                {
                    "file": scene_file,
                    "line_start": line_idx + 1,
                    "line_end": line_idx + 1,
                    "old_text": old_line,
                    "new_text": new_line,
                }
            )
            message = f"Adjusted run_time={old_val} -> run_time={new_val} at line {line_idx + 1}"
        else:
            return {
                "success": False,
                "patches": [],
                "message": "Run_time too short to reduce further",
            }
    else:
        return {
            "success": False,
            "patches": [],
            "message": "No adjustable wait() or run_time found",
        }

    return {
        "success": True,
        "patches": patches,
        "message": message,
        "verification_hint": "Re-run check-static to verify duration",
    }


def _fix_mc(lines: list[str], start: int, end: int, delta: float, scene_file: str) -> dict:
    """Adjust yield* wait times in Motion Canvas .tsx scenes."""
    # Pattern: yield* wait(<number>)
    wait_re = re.compile(r"yield\*\s*wait\(([^)]+)\)")
    waits = []
    for i in range(start - 1, end):
        line = lines[i]
        for m in wait_re.finditer(line):
            try:
                val = float(m.group(1))
                waits.append((i, m.start(), m.end(), val, line))
            except ValueError:
                continue

    if not waits:
        return {"success": False, "patches": [], "message": "No yield* wait() found in segment"}

    line_idx, m_start, m_end, old_val, old_line = waits[-1]
    if delta > 0:
        new_val = max(0.1, old_val - delta)
    else:
        new_val = old_val + abs(delta)
    new_val = round(new_val, 2)

    new_line = old_line[:m_start] + f"yield* wait({new_val})" + old_line[m_end:]
    patch = {
        "file": scene_file,
        "line_start": line_idx + 1,
        "line_end": line_idx + 1,
        "old_text": old_line,
        "new_text": new_line,
    }

    return {
        "success": True,
        "patches": [patch],
        "message": f"Adjusted yield* wait({old_val}) -> yield* wait({new_val}) at line {line_idx + 1}",
        "verification_hint": "Re-run check-static to verify duration",
    }
