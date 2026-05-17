#!/usr/bin/env python3
"""bin/checks/duration_consistency.py
Layer 1 check: A1/A2 time consistency.

Detects:
  A1 — Duration mismatch between declared @time and computed animation time.
  A2 — Animation overlap (segments whose time ranges overlap without transition).

Usage:
    duration_consistency.py --scene-dir scenes/04_base_demo/
"""

import argparse
import json
import os
import sys

_SCRIPT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _SCRIPT_DIR not in sys.path:
    sys.path.insert(0, _SCRIPT_DIR)

from project_engine import find_project_root, resolve_engine_from_manifest

from checks._utils import (
    calc_animation_time,
    calc_animation_time_mc,
    extract_animation_calls,
    extract_segments_from_source,
    find_function_blocks,
    find_source_file,
    get_code_block,
    load_manifest,
)


def fail(msg: str):
    print(msg, file=sys.stderr)
    sys.exit(1)


def check(scene_dir: str) -> dict:
    """Run duration consistency checks and return a report dict."""
    manifest = load_manifest(scene_dir)
    project_root = find_project_root(scene_dir)
    engine = resolve_engine_from_manifest(manifest, scene_dir, project_root)
    is_mc = engine == "motion_canvas"
    source_path = find_source_file(scene_dir)
    if not source_path:
        return {
            "check": "duration_consistency",
            "layer": "layer1",
            "scene": os.path.basename(os.path.normpath(scene_dir)),
            "status": "error",
            "segments": [],
            "issues": [
                {"type": "source_missing", "severity": "error", "message": "scene source not found"}
            ],
        }

    manifest_segments = manifest.get("segments", [])
    extracted_segments = extract_segments_from_source(source_path)
    manifest_by_id = {s["id"]: s for s in manifest_segments}
    extracted_by_id = {s["id"]: s for s in extracted_segments}
    all_ids = sorted(set(manifest_by_id) | set(extracted_by_id))

    func_blocks = find_function_blocks(source_path) if source_path.endswith(".py") else {}
    sorted_funcs = sorted(func_blocks.values(), key=lambda x: x[0])

    segment_results = []
    global_status = "pass"

    for seg_id in all_ids:
        m_seg = manifest_by_id.get(seg_id)
        e_seg = extracted_by_id.get(seg_id)
        seg_status = "pass"
        issues = []
        suggested_lines = []

        if m_seg is None or e_seg is None:
            seg_status = "warning"
            issues.append(
                {
                    "type": "segment_missing",
                    "severity": "warning",
                    "message": f'Segment "{seg_id}" missing in manifest or source',
                    "suggested_lines": [e_seg.get("line_start", 0), e_seg.get("line_end", 0)]
                    if e_seg
                    else [0, 0],
                }
            )
            segment_results.append({"id": seg_id, "status": seg_status, "issues": issues})
            if global_status == "pass":
                global_status = "warning"
            continue

        block_start = m_seg["line_start"]
        block_end = m_seg["line_end"]
        if is_mc:
            # For MC .tsx, use from segment start to end of file (single scene per file)
            with open(source_path, encoding="utf-8") as f:
                lines = f.readlines()
                block_end = len(lines)
        else:
            # Always extend to the actual function body that follows the segment comment
            for fs, fe, _fname in sorted_funcs:
                if fs > m_seg["line_start"]:
                    block_start = fs
                    block_end = fe
                    break

        code_block = get_code_block(source_path, block_start, block_end)
        suggested_lines = [block_start, block_end]

        declared_start, declared_end = m_seg.get("time_range", [0.0, 0.0])
        declared_duration = declared_end - declared_start
        if is_mc:
            computed_duration = calc_animation_time_mc(code_block)
        else:
            computed_duration = calc_animation_time(code_block)

        if abs(computed_duration - declared_duration) > 0.5:
            seg_status = "warning"
            excess = computed_duration - declared_duration
            calls = extract_animation_calls(code_block, is_mc=is_mc)
            # Map relative line numbers to absolute
            for c in calls:
                c["line"] += block_start - 1
            hint = _build_duration_hint(calls, excess, is_mc, declared_duration)
            issues.append(
                {
                    "type": "duration_mismatch",
                    "severity": "warning",
                    "message": (
                        f"声明时长 {declared_duration:.2f}s "
                        f"与计算动画时间 {computed_duration:.2f}s 偏差超过 0.5s"
                    ),
                    "declared": declared_duration,
                    "computed": computed_duration,
                    "suggested_lines": suggested_lines,
                    "details": {
                        "animation_calls": calls,
                        "excess": round(excess, 2),
                    },
                    "fixable": True,
                    "fix_confidence": 0.9,
                    "fix": {
                        "strategy": "adjust_wait",
                        "action": "adjust_animation_duration" if is_mc else "modify_wait_duration",
                        "params": {"target_duration": declared_duration},
                        "hint": hint,
                    },
                }
            )

        segment_results.append({"id": seg_id, "status": seg_status, "issues": issues})
        if seg_status != "pass" and global_status == "pass":
            global_status = seg_status

    # A2 — detect time-range overlaps between consecutive segments without transition
    overlap_issues = _detect_overlap(manifest_segments)
    if overlap_issues:
        if global_status == "pass":
            global_status = "warning"
        for ov in overlap_issues:
            # Find which segment(s) to attach the issue to
            for sr in segment_results:
                if sr["id"] in (ov["seg_a"], ov["seg_b"]):
                    sr.setdefault("issues", []).append(
                        {
                            "type": "animation_overlap",
                            "severity": "warning",
                            "message": ov["message"],
                            "overlap_duration": ov["overlap"],
                            "fixable": True,
                            "fix_confidence": 0.8,
                            "fix": {
                                "strategy": "adjust_wait",
                                "action": "reduce_overlap",
                                "params": {"overlap": ov["overlap"]},
                                "hint": (
                                    f'缩短 "{ov["seg_a"]}" 的结束时间或推迟 "{ov["seg_b"]}" 的开始时间，'
                                    f"消除 {ov['overlap']:.2f}s 重叠"
                                ),
                            },
                        }
                    )
                    if sr["status"] == "pass":
                        sr["status"] = "warning"

    return {
        "check": "duration_consistency",
        "layer": "layer1",
        "scene": os.path.basename(os.path.normpath(scene_dir)),
        "status": global_status,
        "segments": segment_results,
    }


def _detect_overlap(segments: list) -> list:
    """Detect overlapping time ranges between consecutive segments."""
    issues = []
    for i in range(len(segments) - 1):
        a = segments[i]
        b = segments[i + 1]
        a_start, a_end = a.get("time_range", [0.0, 0.0])
        b_start, b_end = b.get("time_range", [0.0, 0.0])
        if b_start < a_end:
            overlap = a_end - b_start
            issues.append(
                {
                    "seg_a": a["id"],
                    "seg_b": b["id"],
                    "overlap": overlap,
                    "message": (
                        f'Segments "{a["id"]}" ({a_start:.1f}-{a_end:.1f}s) and '
                        f'"{b["id"]}" ({b_start:.1f}-{b_end:.1f}s) overlap by {overlap:.2f}s'
                    ),
                }
            )
    return issues


def _build_duration_hint(calls: list[dict], excess: float, is_mc: bool, target: float) -> str:
    """Generate a human-readable hint for fixing duration mismatch."""
    if not calls or excess <= 0:
        return f"调整动画时长使总时长等于 {target:.2f}s"
    # Sort by duration descending
    sorted_calls = sorted(calls, key=lambda x: x["duration"], reverse=True)
    biggest = sorted_calls[0]
    if len(calls) == 1:
        new_dur = max(0.0, biggest["duration"] - excess)
        return (
            f"第 {biggest['line']} 行的 `{biggest['expr']}` 是唯一的动画调用，"
            f"将其 duration 从 {biggest['duration']:.2f}s 改为 {new_dur:.2f}s"
        )
    # Multiple calls: suggest trimming the biggest one
    hints = []
    remaining = excess
    for c in sorted_calls:
        if remaining <= 0:
            break
        reducible = min(c["duration"] - 0.1, remaining)  # keep at least 0.1s
        if reducible > 0.05:
            new_dur = c["duration"] - reducible
            hints.append(
                f"第 {c['line']} 行的 `{c['expr']}` 从 {c['duration']:.2f}s 改为 {new_dur:.2f}s"
            )
            remaining -= reducible
    if hints:
        return "建议调整以下动画调用：" + "；".join(hints)
    return f"调整动画时长使总时长等于 {target:.2f}s"


def main():
    parser = argparse.ArgumentParser(
        description="Layer 1: duration and animation overlap checks (A1/A2).",
    )
    parser.add_argument("--scene-dir", required=True, help="Path to scene directory")
    args = parser.parse_args()

    if not os.path.isdir(args.scene_dir):
        fail(f"Error: directory not found: {args.scene_dir}")

    report = check(args.scene_dir)
    print(json.dumps(report, indent=2, ensure_ascii=False))
    sys.exit(0 if report["status"] == "pass" else 1)


if __name__ == "__main__":
    main()
