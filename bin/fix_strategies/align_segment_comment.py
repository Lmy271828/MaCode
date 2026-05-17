#!/usr/bin/env python3
"""bin/fix-strategies/align_segment_comment.py
Fix strategy for segment consistency issues between manifest and source comments.
"""

from __future__ import annotations

import json
import os
import re
import sys

_SCRIPT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _SCRIPT_DIR not in sys.path:
    sys.path.insert(0, _SCRIPT_DIR)

from checks._utils import find_source_file, load_manifest


def can_fix(issue: dict, scene_dir: str) -> tuple[bool, float]:
    if issue.get("type") not in (
        "manifest_missing",
        "source_missing",
        "comment_manifest_mismatch",
    ):
        return False, 0.0
    fix = issue.get("fix", {})
    if fix.get("strategy") != "align_segment_comment":
        return False, 0.0
    return True, issue.get("fix_confidence", 0.0)


def apply(issue: dict, scene_dir: str) -> dict:
    action = issue.get("fix", {}).get("action", "")
    if action == "add_to_manifest":
        return _add_to_manifest(issue, scene_dir)
    if action == "add_source_comment":
        return _add_source_comment(issue, scene_dir)
    if action == "sync_manifest_to_comment":
        return _sync_manifest_to_comment(issue, scene_dir)
    return {"success": False, "patches": [], "message": f"Unknown action: {action}"}


def _add_to_manifest(issue: dict, scene_dir: str) -> dict:
    manifest = load_manifest(scene_dir)
    if manifest is None:
        return {"success": False, "patches": [], "message": "manifest.json not found"}

    seg_id = issue.get("id", "")
    if not seg_id:
        # Try to extract from message
        m = re.search(r'Segment "([^"]+)"', issue.get("message", ""))
        if m:
            seg_id = m.group(1)

    lines = issue.get("suggested_lines", [0, 0])
    new_seg = {
        "id": seg_id,
        "line_start": lines[0] if lines else 0,
        "line_end": lines[1] if len(lines) > 1 else lines[0] if lines else 0,
    }

    segments = manifest.get("segments", [])
    # Avoid duplicate
    if any(s.get("id") == seg_id for s in segments):
        return {
            "success": False,
            "patches": [],
            "message": f"Segment '{seg_id}' already in manifest",
        }

    segments.append(new_seg)
    manifest["segments"] = segments

    manifest_path = os.path.join(scene_dir, "manifest.json")
    patch = {
        "file": manifest_path,
        "line_start": 1,
        "line_end": 9999,
        "old_text": "",
        "new_text": json.dumps(manifest, indent=2, ensure_ascii=False) + "\n",
    }

    return {
        "success": True,
        "patches": [patch],
        "message": f"Added segment '{seg_id}' to manifest.json",
        "verification_hint": "Re-run check-static to verify segment consistency",
    }


def _add_source_comment(issue: dict, scene_dir: str) -> dict:
    scene_file = find_source_file(scene_dir)
    if not scene_file:
        return {"success": False, "patches": [], "message": "Scene file not found"}

    seg_id = issue.get("id", "")
    if not seg_id:
        m = re.search(r'Segment "([^"]+)"', issue.get("message", ""))
        if m:
            seg_id = m.group(1)

    lines = issue.get("suggested_lines", [0, 0])
    insert_line = lines[0] if lines else 1

    comment = f"# SEGMENT: {seg_id}\n"
    if scene_file.endswith(".tsx"):
        comment = f"// SEGMENT: {seg_id}\n"

    patch = {
        "file": scene_file,
        "line_start": insert_line,
        "line_end": insert_line,
        "old_text": "",
        "new_text": comment,
    }

    return {
        "success": True,
        "patches": [patch],
        "message": f"Added segment comment for '{seg_id}' at line {insert_line}",
        "verification_hint": "Re-run check-static to verify segment consistency",
    }


def _sync_manifest_to_comment(issue: dict, scene_dir: str) -> dict:
    # Simplified: treat as adding the missing comment side.
    # A full implementation would diff both sides and pick the authoritative one.
    return _add_source_comment(issue, scene_dir)
