#!/usr/bin/env python3
"""bin/check-layout.py
Zone compliance checker — validates spatial constraints before rendering.

Usage:
    check-layout.py <scene.py> --layout-profile lecture_3zones
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


def load_layout_profile(profile_name: str) -> dict:
    path = os.path.join(
        _PROJECT_ROOT,
        "engines",
        "manimgl",
        "src",
        "templates",
        "layouts",
        f"{profile_name}.json",
    )
    if not os.path.exists(path):
        fail(f"Layout profile not found: {path}")
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def get_num_value(node: ast.AST) -> float:
    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
        return float(node.value)
    return 0.0


def estimate_bbox(node: ast.AST) -> dict:
    """Estimate bounding box of a mobject AST node.

    Returns {"width": float, "height": float, "text_chars": int, "type": str}
    """
    width = 0.0
    height = 0.0
    text_chars = 0
    obj_type = "unknown"

    if isinstance(node, ast.Call):
        func = node.func
        name = ""
        if isinstance(func, ast.Name):
            name = func.id
        elif isinstance(func, ast.Attribute):
            name = func.attr

        if name in ("Text", "TexText"):
            obj_type = "text"
            text = ""
            font_size = 24.0
            for kw in node.keywords:
                if kw.arg == "text" and isinstance(kw.value, ast.Constant):
                    text = str(kw.value.value)
                elif kw.arg == "font_size" and isinstance(kw.value, ast.Constant):
                    font_size = float(kw.value.value)
            if not text and node.args and isinstance(node.args[0], ast.Constant):
                text = str(node.args[0].value)
            text_chars = len(text)
            width = len(text) * font_size * 0.6
            height = font_size * 1.2
        elif name in ("MathTex", "Tex"):
            obj_type = "text"
            text = ""
            font_size = 24.0
            for kw in node.keywords:
                if kw.arg == "font_size" and isinstance(kw.value, ast.Constant):
                    font_size = float(kw.value.value)
            if node.args and isinstance(node.args[0], ast.Constant):
                text = str(node.args[0].value)
            text_chars = len(text)
            width = len(text) * font_size * 0.4
            height = font_size * 1.2
        elif name == "Circle":
            obj_type = "visual"
            radius = 1.0
            for kw in node.keywords:
                if kw.arg == "radius" and isinstance(kw.value, ast.Constant):
                    radius = float(kw.value.value)
            if node.args and isinstance(node.args[0], ast.Constant):
                radius = float(node.args[0].value)
            width = 2 * radius
            height = 2 * radius
        elif name == "Axes":
            obj_type = "visual"
            x_range = [-3, 3]
            for kw in node.keywords:
                if kw.arg == "x_range" and isinstance(kw.value, (ast.List, ast.Tuple)):
                    elems = kw.value.elts
                    if len(elems) >= 2:
                        x_range = [get_num_value(elems[0]), get_num_value(elems[1])]
            if node.args and isinstance(node.args[0], (ast.List, ast.Tuple)):
                elems = node.args[0].elts
                if len(elems) >= 2:
                    x_range = [get_num_value(elems[0]), get_num_value(elems[1])]
            span = abs(x_range[1] - x_range[0])
            width = span
            height = span * 0.6
        elif name == "NumberLine":
            obj_type = "visual"
            width = 6.0
            height = 1.0
            for kw in node.keywords:
                if kw.arg == "x_range" and isinstance(kw.value, (ast.List, ast.Tuple)):
                    elems = kw.value.elts
                    if len(elems) >= 2:
                        span = abs(get_num_value(elems[1]) - get_num_value(elems[0]))
                        width = span
            if node.args and isinstance(node.args[0], (ast.List, ast.Tuple)):
                elems = node.args[0].elts
                if len(elems) >= 2:
                    span = abs(get_num_value(elems[1]) - get_num_value(elems[0]))
                    width = span
        elif name == "VGroup":
            obj_type = "group"
            total_w = 0.0
            total_h = 0.0
            total_chars = 0
            for child in node.args:
                cb = estimate_bbox(child)
                total_w = max(total_w, cb["width"])
                total_h += cb["height"]
                total_chars += cb.get("text_chars", 0)
            width = total_w
            height = total_h
            text_chars = total_chars
        elif name in ("Arrow", "Line"):
            obj_type = "visual"
            width = 2.0
            height = 0.5
        elif name == "Square":
            obj_type = "visual"
            side = 2.0
            for kw in node.keywords:
                if kw.arg == "side_length" and isinstance(kw.value, ast.Constant):
                    side = float(kw.value.value)
            width = side
            height = side
        elif name == "Rectangle":
            obj_type = "visual"
            width = 4.0
            height = 2.0
            for kw in node.keywords:
                if kw.arg == "width" and isinstance(kw.value, ast.Constant):
                    width = float(kw.value.value)
                if kw.arg == "height" and isinstance(kw.value, ast.Constant):
                    height = float(kw.value.value)
        elif name in ("Dot", "SmallDot"):
            obj_type = "visual"
            width = 0.2
            height = 0.2
        else:
            obj_type = "unknown"
            width = 2.0
            height = 1.0

    return {"width": width, "height": height, "text_chars": text_chars, "type": obj_type}


def extract_place_calls(tree: ast.AST) -> list:
    """Extract self.place(mobj, zone_name) calls from AST."""
    places = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        if not isinstance(func, ast.Attribute):
            continue
        if func.attr != "place":
            continue
        if isinstance(func.value, ast.Name) and func.value.id == "self":
            if len(node.args) >= 2:
                mobj = node.args[0]
                zone_node = node.args[1]
                zone_name = ""
                if isinstance(zone_node, ast.Constant) and isinstance(zone_node.value, str):
                    zone_name = zone_node.value
                places.append(
                    {
                        "mobj": mobj,
                        "zone": zone_name,
                        "line": getattr(node, "lineno", 0),
                    }
                )
    return places


def check(scene_file: str, layout_profile: dict) -> dict:
    profile_name = layout_profile.get("name", "unknown")
    zones_config = layout_profile.get("zones", {})
    canvas = layout_profile.get("canvas", [1920, 1080])

    with open(scene_file, encoding="utf-8") as f:
        source = f.read()
    try:
        tree = ast.parse(source)
    except SyntaxError as e:
        return {
            "check": "layout",
            "profile": profile_name,
            "status": "error",
            "issues": [{"type": "syntax_error", "message": str(e)}],
        }

    places = extract_place_calls(tree)

    zone_objects = {name: [] for name in zones_config}
    for p in places:
        zn = p["zone"]
        if zn in zone_objects:
            zone_objects[zn].append(p)

    issues = []

    for zone_name, zone_cfg in zones_config.items():
        objects = zone_objects.get(zone_name, [])
        rect = zone_cfg.get("rect", [0, 0, 1, 1])
        padding = zone_cfg.get("padding", [0, 0, 0, 0])
        max_objects = zone_cfg.get("max_objects")
        canvas_w, canvas_h = canvas

        zone_x, zone_y, zone_w_norm, zone_h_norm = rect
        zone_width = zone_w_norm * canvas_w
        zone_height = zone_h_norm * canvas_h
        if isinstance(padding, (int, float)):
            pad_l = pad_t = pad_r = pad_b = padding
        else:
            pad_l, pad_t, pad_r, pad_b = padding
        effective_width = max(0, zone_width - pad_l - pad_r)
        effective_height = max(0, zone_height - pad_t - pad_b)
        zone_area = effective_width * effective_height

        # 1. Zone overflow
        if max_objects is not None and len(objects) > max_objects:
            issues.append(
                {
                    "type": "zone_overflow",
                    "zone": zone_name,
                    "message": (
                        f"Zone '{zone_name}' has {len(objects)} objects (max {max_objects})"
                    ),
                    "line": objects[max_objects]["line"] if max_objects < len(objects) else None,
                }
            )

        # Estimate bboxes
        bboxes = []
        total_obj_area = 0.0
        for obj in objects:
            bbox = estimate_bbox(obj["mobj"])
            bboxes.append(bbox)
            total_obj_area += bbox["width"] * bbox["height"]

        # 2. Object overlap (heuristic: if combined area > 50% zone and >=2 objects)
        if len(bboxes) >= 2 and zone_area > 0:
            occupancy = total_obj_area / zone_area
            if occupancy > 0.5:
                issues.append(
                    {
                        "type": "object_overlap",
                        "zone": zone_name,
                        "message": (
                            f"Zone '{zone_name}' objects likely overlap (occupancy {occupancy:.1%})"
                        ),
                    }
                )

        # 3. Whitespace check
        if zone_area > 0:
            occupancy = total_obj_area / zone_area
            min_whitespace = 0.15
            if occupancy > (1 - min_whitespace):
                issues.append(
                    {
                        "type": "insufficient_whitespace",
                        "zone": zone_name,
                        "message": (
                            f"Zone '{zone_name}' occupancy {occupancy:.1%} exceeds limit "
                            f"(whitespace < {min_whitespace:.0%})"
                        ),
                    }
                )

        # 4. Font size minimums
        is_title_zone = zone_name == "title"
        min_size = 48 if is_title_zone else 24
        for obj in objects:
            mobj = obj["mobj"]
            if isinstance(mobj, ast.Call):
                func = mobj.func
                name = ""
                if isinstance(func, ast.Name):
                    name = func.id
                elif isinstance(func, ast.Attribute):
                    name = func.attr
                if name in ("Text", "MathTex", "Tex", "TexText"):
                    font_size = 24.0
                    for kw in mobj.keywords:
                        if kw.arg == "font_size" and isinstance(kw.value, ast.Constant):
                            font_size = float(kw.value.value)
                    if font_size < min_size:
                        issues.append(
                            {
                                "type": "font_size_too_small",
                                "zone": zone_name,
                                "message": (
                                    f"Font size {font_size} in zone '{zone_name}' "
                                    f"is below minimum {min_size}"
                                ),
                                "line": obj["line"],
                            }
                        )

    status = "pass" if not issues else "fail"
    return {
        "check": "layout",
        "profile": profile_name,
        "status": status,
        "issues": issues,
        "summary": {
            "total_places": len(places),
            "zones_used": [z for z, objs in zone_objects.items() if objs],
        },
    }


def main():
    parser = argparse.ArgumentParser(
        description="Zone compliance checker for MaCode scenes.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("scene_file", help="Path to scene.py")
    parser.add_argument("--layout-profile", default="lecture_3zones", help="Layout profile name")
    parser.add_argument("--output", default=None, help="Write JSON report to file")
    args = parser.parse_args()

    if not os.path.isfile(args.scene_file):
        fail(f"Scene file not found: {args.scene_file}")

    profile = load_layout_profile(args.layout_profile)
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
