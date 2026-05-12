#!/usr/bin/env python3
"""bin/check-narrative.py
Narrative pattern compliance checker — validates stage order and pacing.

Usage:
    check-narrative.py <scene.py> --narrative-profile definition_reveal
"""

import argparse
import ast
import json
import os
import sys

_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
_PROJECT_ROOT = os.path.dirname(_SCRIPT_DIR)


def fail(msg: str):
    print(msg, file=sys.stderr)
    sys.exit(1)


def load_narrative_profile(profile_name: str) -> dict:
    path = os.path.join(
        _PROJECT_ROOT,
        "engines",
        "manimgl",
        "src",
        "templates",
        "narratives",
        f"{profile_name}.json",
    )
    if not os.path.exists(path):
        fail(f"Narrative profile not found: {path}")
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def infer_type(node: ast.AST) -> str:
    """Infer whether an AST node represents text or visual content."""
    if isinstance(node, ast.Call):
        func = node.func
        name = ""
        if isinstance(func, ast.Name):
            name = func.id
        elif isinstance(func, ast.Attribute):
            name = func.attr
        if name in ("Text", "MathTex", "Tex", "TexText", "Paragraph", "MarkupText"):
            return "text"
        if name in (
            "Circle",
            "Axes",
            "NumberLine",
            "Square",
            "Rectangle",
            "Arrow",
            "Line",
            "Dot",
            "ImageMobject",
        ):
            return "visual"
        if name == "VGroup":
            for child in node.args:
                child_type = infer_type(child)
                if child_type == "visual":
                    return "visual"
            return "text" if node.args else "visual"
    return "unknown"


def count_text_chars(node: ast.AST) -> int:
    """Count text characters in a text node."""
    if isinstance(node, ast.Call):
        func = node.func
        name = ""
        if isinstance(func, ast.Name):
            name = func.id
        elif isinstance(func, ast.Attribute):
            name = func.attr
        if name in ("Text", "MathTex", "Tex", "TexText"):
            if node.args and isinstance(node.args[0], ast.Constant):
                return len(str(node.args[0].value))
            for kw in node.keywords:
                if kw.arg == "text" and isinstance(kw.value, ast.Constant):
                    return len(str(kw.value.value))
        if name == "VGroup":
            return sum(count_text_chars(child) for child in node.args)
    return 0


def extract_stage_calls(tree: ast.AST) -> list:
    """Extract self.stage(stage_id, *mobjects, run_time=...) calls."""
    stages = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        if not isinstance(func, ast.Attribute):
            continue
        if func.attr != "stage":
            continue
        if isinstance(func.value, ast.Name) and func.value.id == "self":
            if not node.args:
                continue
            stage_id_node = node.args[0]
            stage_id = ""
            if isinstance(stage_id_node, ast.Constant) and isinstance(
                stage_id_node.value, str
            ):
                stage_id = stage_id_node.value
            mobjects = node.args[1:]
            run_time = None
            for kw in node.keywords:
                if kw.arg == "run_time" and isinstance(kw.value, ast.Constant):
                    run_time = float(kw.value.value)
            stages.append(
                {
                    "id": stage_id,
                    "mobjects": mobjects,
                    "run_time": run_time,
                    "line": getattr(node, "lineno", 0),
                }
            )
    return stages


def _is_primary_zone(zone_name: str) -> bool:
    """Heuristic: zones with 'main' in the name are primary."""
    return "main" in zone_name or zone_name == "primary"


def check(scene_file: str, profile: dict) -> dict:
    profile_name = profile.get("name", "unknown")
    stages_def = profile.get("stages", [])
    rules = profile.get("rules", {})

    with open(scene_file, encoding="utf-8") as f:
        source = f.read()
    try:
        tree = ast.parse(source)
    except SyntaxError as e:
        return {
            "check": "narrative",
            "profile": profile_name,
            "status": "error",
            "issues": [{"type": "syntax_error", "message": str(e)}],
        }

    stages = extract_stage_calls(tree)
    stage_ids = [s["id"] for s in stages]
    issues = []

    stage_def_by_id = {s["id"]: s for s in stages_def}

    # 1. Stage order compliance
    played = set()
    for st in stages:
        sid = st["id"]
        if sid not in stage_def_by_id:
            issues.append(
                {
                    "type": "unknown_stage",
                    "stage": sid,
                    "message": f"Stage '{sid}' not defined in narrative profile '{profile_name}'",
                    "line": st["line"],
                }
            )
            continue
        sdef = stage_def_by_id[sid]
        if sdef.get("must_be_first") and played:
            issues.append(
                {
                    "type": "stage_order_error",
                    "stage": sid,
                    "message": (
                        f"Stage '{sid}' must be first, but stages {sorted(played)} already played"
                    ),
                    "line": st["line"],
                }
            )
        requires = sdef.get("requires", [])
        for req in requires:
            if req not in played:
                issues.append(
                    {
                        "type": "stage_order_error",
                        "stage": sid,
                        "message": (
                            f"Stage '{sid}' requires '{req}' which has not been played yet"
                        ),
                        "line": st["line"],
                    }
                )
                break
        played.add(sid)

    # 2. Primary zone first visual within timeout
    timeout = rules.get("primary_zone_first_visual_within")
    if timeout is not None:
        elapsed = 0.0
        found_visual = False
        for st in stages:
            sid = st["id"]
            sdef = stage_def_by_id.get(sid, {})
            zone_name = sdef.get("zone", "")
            stype = sdef.get("type", "visual")
            is_primary = _is_primary_zone(zone_name)
            if is_primary and stype == "visual" and not found_visual:
                found_visual = True
                if elapsed > timeout:
                    issues.append(
                        {
                            "type": "primary_zone_visual_timeout",
                            "stage": sid,
                            "message": (
                                f"First primary zone visual '{sid}' appears at "
                                f"{elapsed:.1f}s (limit {timeout}s)"
                            ),
                            "line": st["line"],
                        }
                    )
                break
            duration = st.get("run_time")
            if duration is None:
                duration = sdef.get("duration_hint", 1.0)
            elapsed += duration

    # 3. Text/visual ratio and char count
    total_text_chars = 0
    visual_count = 0
    for st in stages:
        sid = st["id"]
        sdef = stage_def_by_id.get(sid, {})
        stype = sdef.get("type", "visual")
        if stype == "text":
            for mobj in st["mobjects"]:
                total_text_chars += count_text_chars(mobj)
        elif stype == "visual":
            visual_count += len(st["mobjects"])

    max_chars = rules.get("max_text_chars_per_scene", 80)
    if total_text_chars > max_chars:
        issues.append(
            {
                "type": "text_too_long",
                "message": f"Total text chars {total_text_chars} exceeds limit {max_chars}",
            }
        )

    ratio_rule = rules.get("text_to_visual_ratio", "<= 0.4")
    if visual_count > 0 and ratio_rule.startswith("<="):
        ratio_limit = float(ratio_rule.replace("<=", "").strip())
        ratio = total_text_chars / visual_count
        if ratio > ratio_limit:
            issues.append(
                {
                    "type": "text_visual_ratio_exceeded",
                    "message": f"Text/visual ratio {ratio:.2f} exceeds limit {ratio_limit}",
                }
            )

    status = "pass" if not issues else "fail"
    return {
        "check": "narrative",
        "profile": profile_name,
        "status": status,
        "issues": issues,
        "summary": {
            "stage_count": len(stages),
            "stage_ids": stage_ids,
            "total_text_chars": total_text_chars,
            "visual_count": visual_count,
        },
    }


def main():
    parser = argparse.ArgumentParser(
        description="Narrative pattern compliance checker for MaCode scenes.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("scene_file", help="Path to scene.py")
    parser.add_argument(
        "--narrative-profile",
        default="definition_reveal",
        help="Narrative profile name",
    )
    parser.add_argument("--output", default=None, help="Write JSON report to file")
    args = parser.parse_args()

    if not os.path.isfile(args.scene_file):
        fail(f"Scene file not found: {args.scene_file}")

    profile = load_narrative_profile(args.narrative_profile)
    report = check(args.scene_file, profile)

    if args.output:
        os.makedirs(os.path.dirname(args.output) or ".", exist_ok=True)
        with open(args.output, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2, ensure_ascii=False)
            f.write("\n")

    print(json.dumps(report, indent=2, ensure_ascii=False))
    sys.exit(0 if report["status"] == "pass" else 1)


if __name__ == "__main__":
    main()
