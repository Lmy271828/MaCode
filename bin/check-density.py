#!/usr/bin/env python3
"""bin/check-density.py
Information density checker — validates cognitive load before rendering.

Usage:
    check-density.py <scene.py>
"""

import argparse
import ast
import json
import os
import sys


def fail(msg: str):
    print(msg, file=sys.stderr)
    sys.exit(1)


def extract_color(node: ast.AST) -> str:
    """Extract a color string from an AST node if it looks like a color."""
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        val = node.value
        if val.startswith("#"):
            return val.lower()
        known_colors = {
            "red",
            "green",
            "blue",
            "yellow",
            "orange",
            "purple",
            "white",
            "black",
            "gray",
            "grey",
            "pink",
            "teal",
            "maroon",
            "gold",
            "indigo",
            "cyan",
            "magenta",
            "lime",
            "navy",
            "coral",
            "salmon",
            "crimson",
        }
        if val.lower() in known_colors:
            return val.lower()
    if isinstance(node, ast.Call):
        func = node.func
        if isinstance(func, ast.Name) and func.id in ("Color", "hex_color", "rgb_to_color"):
            if node.args and isinstance(node.args[0], ast.Constant):
                v = str(node.args[0].value)
                if v.startswith("#"):
                    return v.lower()
    return ""


def check(scene_file: str) -> dict:
    with open(scene_file, encoding="utf-8") as f:
        source = f.read()
    try:
        tree = ast.parse(source)
    except SyntaxError as e:
        return {
            "check": "density",
            "status": "error",
            "issues": [{"type": "syntax_error", "message": str(e)}],
        }

    construct_method = None
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == "construct":
            construct_method = node
            break

    if construct_method is None:
        return {
            "check": "density",
            "status": "error",
            "issues": [{"type": "missing_construct", "message": "No construct() method found"}],
        }

    total_objects = 0
    play_calls = 0

    for node in ast.walk(construct_method):
        if isinstance(node, ast.Call):
            func = node.func
            if isinstance(func, ast.Attribute):
                if func.attr in ("add", "play", "place"):
                    if isinstance(func.value, ast.Name) and func.value.id == "self":
                        if func.attr == "play":
                            play_calls += 1
                            for _arg in node.args:
                                total_objects += 1
                        elif func.attr == "add":
                            for _arg in node.args:
                                total_objects += 1
                        elif func.attr == "place":
                            if node.args:
                                total_objects += 1

    colors_found = set()
    for node in ast.walk(construct_method):
        if isinstance(node, ast.Call):
            func = node.func
            if isinstance(func, ast.Attribute):
                if func.attr in ("set_color", "set_fill", "set_stroke"):
                    if node.args:
                        c = extract_color(node.args[0])
                        if c:
                            colors_found.add(c)
            for kw in node.keywords:
                if kw.arg in ("fill", "color", "stroke_color", "fill_color"):
                    c = extract_color(kw.value)
                    if c:
                        colors_found.add(c)

    max_objects = 10
    max_colors = 6
    max_plays = 15

    issues = []
    if total_objects > max_objects:
        issues.append(
            {
                "type": "too_many_objects",
                "message": f"Total objects added/played/placed: {total_objects} (max {max_objects})",
            }
        )
    if len(colors_found) > max_colors:
        issues.append(
            {
                "type": "too_many_colors",
                "message": (
                    f"Color variety: {len(colors_found)} (max {max_colors}): {sorted(colors_found)}"
                ),
            }
        )
    if play_calls > max_plays:
        issues.append(
            {
                "type": "too_many_animations",
                "message": f"Animation count (self.play): {play_calls} (max {max_plays})",
            }
        )

    status = "pass" if not issues else "fail"
    return {
        "check": "density",
        "status": status,
        "issues": issues,
        "summary": {
            "total_objects": total_objects,
            "color_count": len(colors_found),
            "colors": sorted(colors_found),
            "play_calls": play_calls,
        },
    }


def main():
    parser = argparse.ArgumentParser(
        description="Information density checker for MaCode scenes.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("scene_file", help="Path to scene.py")
    parser.add_argument("--output", default=None, help="Write JSON report to file")
    args = parser.parse_args()

    if not os.path.isfile(args.scene_file):
        fail(f"Scene file not found: {args.scene_file}")

    report = check(args.scene_file)

    if args.output:
        os.makedirs(os.path.dirname(args.output) or ".", exist_ok=True)
        with open(args.output, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2, ensure_ascii=False)
            f.write("\n")

    print(json.dumps(report, indent=2, ensure_ascii=False))
    sys.exit(0 if report["status"] == "pass" else 1)


if __name__ == "__main__":
    main()
