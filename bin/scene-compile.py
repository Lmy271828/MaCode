#!/usr/bin/env python3
"""bin/scene-compile.py
Scene Compiler — Phase 2 of two-stage compilation.

Layout config → Engine-specific scene source (template filling).

Usage:
    bin/scene-compile.py <layout_config.yaml> \
        --engine {manim,manimgl,motion_canvas} \
        [--output scene.py]
"""

from __future__ import annotations

import argparse
import json
import string
import sys
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

SCRIPT_DIR = Path(__file__).parent.resolve()
PROJECT_ROOT = SCRIPT_DIR.parent

PRIMITIVES_PATH = (
    PROJECT_ROOT / "engines" / "manimgl" / "src" / "templates" / "visual-primitives.json"
)


# ---------------------------------------------------------------------------
# Templates
# ---------------------------------------------------------------------------

MANIMGL_IMPORTS = """from manimlib import *
from components.narrative_scene import NarrativeScene"""

MANIM_IMPORTS = """from manim import *
from templates.scene_base import MaCodeScene
from components.narrative_scene import NarrativeScene"""

MANIM_TEMPLATE = string.Template(
    '''"""Auto-generated scene from layout_config.yaml.
Layout: $layout_profile | Narrative: $narrative_profile
"""

$imports


class AutoScene(NarrativeScene):
    LAYOUT_PROFILE = "$layout_profile"
    NARRATIVE_PROFILE = "$narrative_profile"

    def construct(self):
$stage_code
'''
)

MC_TEMPLATE = string.Template(
    """/**
 * Auto-generated scene from layout_config.yaml.
 * Layout: $layout_profile | Narrative: $narrative_profile
 */

import {makeScene2D} from '@motion-canvas/2d';
import {Txt, Circle, Rect, Line, Latex} from '@motion-canvas/2d';
import {createRef, waitFor} from '@motion-canvas/core';

export default makeScene2D(function* (view) {
$stage_code
});
"""
)


# ---------------------------------------------------------------------------
# Primitive / param loading
# ---------------------------------------------------------------------------

def load_primitives() -> dict[str, Any]:
    with open(PRIMITIVES_PATH, encoding="utf-8") as f:
        return json.load(f)


# ---------------------------------------------------------------------------
# Python value formatting
# ---------------------------------------------------------------------------

def _py_val(value: Any) -> str:
    if isinstance(value, str):
        escaped = value.replace('"', '\\"')
        return f'"{escaped}"'
    return repr(value)


def build_manim_kwargs(primitive: str, params: dict[str, Any], primitives: dict[str, Any]) -> str:
    if not params:
        return ""
    mapping = primitives.get("params_mapping", {}).get(primitive, {})
    kwargs: list[str] = []
    for k, v in params.items():
        param_name = mapping.get(k, k)
        kwargs.append(f"{param_name}={_py_val(v)}")
    return ", ".join(kwargs)


# ---------------------------------------------------------------------------
# Mobject code generation (ManimGL / ManimCE)
# ---------------------------------------------------------------------------

def build_mobject_code(item: dict[str, Any], engine: str, primitives: dict[str, Any]) -> str:
    item_type = item.get("type", "")
    if item_type == "text":
        text = item.get("text", "")
        # Escape backslashes and quotes for Python string literal
        text = text.replace("\\", "\\\\").replace('"', '\\"')
        return f'Text("{text}")'
    elif item_type == "formula":
        latex = item.get("latex", "")
        if engine == "manimgl":
            return f'Tex(R"{latex}")'
        else:  # manim
            return f'MathTex(r"{latex}")'
    elif item_type == "visual":
        primitive = item.get("primitive", "Circle")
        mapping = primitives.get("primitives", {}).get(primitive, {})
        engine_name = mapping.get(engine)
        if engine_name is None:
            return f'# TODO: Primitive "{primitive}" is not mapped for engine "{engine}"'
        params = item.get("params", {})
        kwargs = build_manim_kwargs(primitive, params, primitives)
        if kwargs:
            return f"{engine_name}({kwargs})"
        return f"{engine_name}()"
    return f'# TODO: Unknown content type "{item_type}"'


# ---------------------------------------------------------------------------
# Stage code generation (ManimGL / ManimCE)
# ---------------------------------------------------------------------------

def build_stage_code_manim(stage: dict[str, Any], engine: str, primitives: dict[str, Any]) -> str:
    stage_id = stage["id"]
    zone = stage["zone"]
    stage_type = stage["type"]
    content = stage.get("content", [])

    lines: list[str] = []
    lines.append(f"        # Stage: {stage_id} (zone: {zone}, type: {stage_type})")

    if not content:
        lines.append(f"        # TODO: No content allocated for stage '{stage_id}'")
        lines.append("        pass")
        return "\n".join(lines)

    mobject_lines = []
    for item in content:
        code = build_mobject_code(item, engine, primitives)
        mobject_lines.append(f"            {code},")

    lines.append(f'        self.stage("{stage_id}",')
    lines.extend(mobject_lines)
    lines.append("        )")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Motion Canvas helpers
# ---------------------------------------------------------------------------

def get_mc_type_name(item: dict[str, Any], primitives: dict[str, Any]) -> str:
    item_type = item.get("type", "")
    if item_type == "text":
        return "Txt"
    elif item_type == "formula":
        return "Latex"
    elif item_type == "visual":
        primitive = item.get("primitive", "")
        mapping = primitives.get("primitives", {}).get(primitive, {})
        return mapping.get("motion_canvas") or "Unknown"
    return "Unknown"


def build_mc_props(item: dict[str, Any], primitives: dict[str, Any]) -> str:
    item_type = item.get("type", "")
    if item_type == "text":
        text = item.get("text", "")
        # Escape backslashes for JSX string literal
        text = text.replace("\\", "\\\\").replace('"', '\\"')
        return f'text="{text}" fontSize={{48}} fill="white"'
    elif item_type == "formula":
        latex = item.get("latex", "")
        return f'tex="{latex}" fontSize={{36}} fill="white"'
    elif item_type == "visual":
        mc_name = get_mc_type_name(item, primitives)
        params = item.get("params", {})

        if mc_name == "Circle":
            radius = params.get("radius", 0.5)
            color = params.get("color", "white")
            return (
                f'width={{{radius * 100}}} height={{{radius * 100}}} '
                f'fill="{color}" lineWidth={{2}}'
            )
        elif mc_name == "Rect":
            w = params.get("width", 100)
            h = params.get("height", 100)
            return f'width={{{w}}} height={{{h}}} fill="white" lineWidth={{2}}'
        elif mc_name == "Line":
            if "x_range" in params:
                xr = params["x_range"]
                scale = 80
                return (
                    f'points={{[[{xr[0] * scale}, 0], [{xr[1] * scale}, 0]]}} '
                    f'stroke="white" lineWidth={{4}}'
                )
            return 'points={[[-100, 0], [100, 0]]} stroke="white" lineWidth={{4}}'
        return 'fill="white"'
    return ""


def build_stage_code_mc(stage: dict[str, Any], primitives: dict[str, Any]) -> str:
    stage_id = stage["id"]
    zone = stage["zone"]
    stage_type = stage["type"]
    duration = stage.get("duration_hint", 1.0)
    content = stage.get("content", [])

    lines: list[str] = []
    lines.append(f"  // Stage: {stage_id} (zone: {zone}, type: {stage_type})")

    if not content:
        lines.append(f"  // TODO: No content allocated for stage '{stage_id}'")
        lines.append(f"  yield* waitFor({duration});")
        return "\n".join(lines)

    # Generate refs
    refs: list[str] = []
    for i in range(len(content)):
        ref_name = f"{stage_id}_{i}_ref" if len(content) > 1 else f"{stage_id}_ref"
        refs.append(ref_name)
        type_name = get_mc_type_name(content[i], primitives)
        lines.append(f"  const {ref_name} = createRef<{type_name}>();")

    # Generate view.add() calls
    for i, item in enumerate(content):
        ref_name = refs[i]
        type_name = get_mc_type_name(item, primitives)
        if type_name == "Unknown":
            primitive = item.get("primitive", "")
            lines.append(
                f'  // TODO: Primitive "{primitive}" is not mapped for Motion Canvas'
            )
            continue
        props = build_mc_props(item, primitives)
        lines.append(f"  view.add(<{type_name} ref={{{ref_name}}} {props} />);")

    lines.append(f"  yield* waitFor({duration});")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Minimal YAML parser (no external dependencies)
# Handles the restricted subset produced by layout-compile.py.
# ---------------------------------------------------------------------------

def _parse_scalar(text: str) -> Any:
    text = text.strip()
    if not text:
        return None
    if text == "true":
        return True
    if text == "false":
        return False
    if text == "null":
        return None
    if text == "[]":
        return []
    if text == "{}":
        return {}
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    try:
        if "." in text or "e" in text.lower():
            return float(text)
        return int(text)
    except ValueError:
        pass
    return text


def _parse_yaml_value(lines: list[str], idx: int, expected_indent: int) -> tuple[Any, int]:
    """Parse a value (scalar, list, or dict) starting at *idx*."""
    if idx >= len(lines):
        return None, idx

    line = lines[idx]
    if not line.strip():
        return None, idx

    indent = len(line) - len(line.lstrip())
    if indent < expected_indent:
        return None, idx

    stripped = line.lstrip()

    if stripped.startswith("- "):
        # List
        result: list[Any] = []
        while idx < len(lines):
            line = lines[idx]
            if not line.strip():
                idx += 1
                continue
            item_indent = len(line) - len(line.lstrip())
            if item_indent < expected_indent:
                break

            stripped = line.lstrip()
            if not stripped.startswith("- "):
                break

            item_text = stripped[2:]

            if ": " in item_text or item_text.endswith(":"):
                # Dict item in list
                key, rest = item_text.split(":", 1)
                key = key.strip()
                rest = rest.strip()

                item_dict: dict[str, Any] = {}
                if rest:
                    item_dict[key] = _parse_scalar(rest)
                    idx += 1
                else:
                    idx += 1
                    val, idx = _parse_yaml_value(lines, idx, item_indent + 2)
                    item_dict[key] = val

                # Continue reading more keys at item_indent + 2
                while idx < len(lines):
                    line = lines[idx]
                    if not line.strip():
                        idx += 1
                        continue
                    next_indent = len(line) - len(line.lstrip())
                    if next_indent < item_indent + 2:
                        break
                    next_stripped = line.lstrip()
                    if next_stripped.startswith("- "):
                        break
                    if ": " in next_stripped or next_stripped.endswith(":"):
                        k, r = next_stripped.split(":", 1)
                        k = k.strip()
                        r = r.strip()
                        if r:
                            item_dict[k] = _parse_scalar(r)
                            idx += 1
                        else:
                            idx += 1
                            val, idx = _parse_yaml_value(lines, idx, next_indent + 2)
                            item_dict[k] = val
                    else:
                        idx += 1

                result.append(item_dict)
            else:
                # Scalar item
                result.append(_parse_scalar(item_text))
                idx += 1
        return result, idx

    elif ": " in stripped or stripped.endswith(":"):
        # Dict
        result: dict[str, Any] = {}
        while idx < len(lines):
            line = lines[idx]
            if not line.strip():
                idx += 1
                continue
            indent = len(line) - len(line.lstrip())
            if indent < expected_indent:
                break

            stripped = line.lstrip()
            if ": " in stripped or stripped.endswith(":"):
                k, r = stripped.split(":", 1)
                k = k.strip()
                r = r.strip()
                if r:
                    result[k] = _parse_scalar(r)
                    idx += 1
                else:
                    idx += 1
                    val, idx = _parse_yaml_value(lines, idx, indent + 2)
                    result[k] = val
            else:
                break
        return result, idx

    else:
        # Scalar
        return _parse_scalar(stripped), idx + 1


def _parse_yaml_simple(text: str) -> Any:
    """Parse a restricted subset of YAML (no comments, 2-space indent)."""
    lines = text.split("\n")
    result, _ = _parse_yaml_value(lines, 0, 0)
    return result


# ---------------------------------------------------------------------------
# Main rendering
# ---------------------------------------------------------------------------

def render_scene(layout: dict[str, Any], engine: str, primitives: dict[str, Any]) -> str:
    layout_profile = layout.get("layout_profile", "lecture_3zones")
    narrative_profile = layout.get("narrative_profile", "definition_reveal")
    stages = layout.get("stages", [])

    if engine in ("manim", "manimgl"):
        imports = MANIMGL_IMPORTS if engine == "manimgl" else MANIM_IMPORTS
        stage_code = "\n\n".join(
            build_stage_code_manim(stage, engine, primitives) for stage in stages
        )
        return MANIM_TEMPLATE.substitute(
            layout_profile=layout_profile,
            narrative_profile=narrative_profile,
            imports=imports,
            stage_code=stage_code,
        )
    elif engine == "motion_canvas":
        stage_code = "\n\n".join(
            build_stage_code_mc(stage, primitives) for stage in stages
        )
        return MC_TEMPLATE.substitute(
            layout_profile=layout_profile,
            narrative_profile=narrative_profile,
            stage_code=stage_code,
        )
    else:
        raise ValueError(f"Unsupported engine: {engine}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Compile layout config to engine scene source."
    )
    parser.add_argument("layout", help="Path to layout_config.yaml")
    parser.add_argument(
        "--engine",
        required=True,
        choices=["manim", "manimgl", "motion_canvas"],
        help="Target engine",
    )
    parser.add_argument("--output", default="scene.py", help="Output file path")
    args = parser.parse_args(argv)

    layout_path = Path(args.layout)
    if not layout_path.exists():
        print(f"[scene-compile] ERROR: Layout config not found: {layout_path}", file=sys.stderr)
        return 1

    # Parse YAML (custom minimal parser for our restricted subset)
    with open(layout_path, encoding="utf-8") as f:
        text = f.read()
    layout = _parse_yaml_simple(text)
    if layout is None:
        print(
            "[scene-compile] ERROR: Cannot parse layout config.",
            file=sys.stderr,
        )
        return 1

    primitives = load_primitives()

    try:
        source = render_scene(layout, args.engine, primitives)
    except ValueError as exc:
        print(f"[scene-compile] ERROR: {exc}", file=sys.stderr)
        return 1

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(source)

    print(f"[scene-compile] OK: {output_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
