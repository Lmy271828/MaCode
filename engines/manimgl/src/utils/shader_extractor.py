"""engines/manimgl/src/utils/shader_extractor.py
Extract ManimGL built-in shaders as self-contained Layer 2 assets.

Resolves ``#INSERT`` directives so the output GLSL can be consumed by
external renderers (moderngl) that do not understand ManimGL's include
system.

Usage::

    from utils.shader_extractor import extract_builtin_shader, save_shader_asset

    data = extract_builtin_shader("quadratic_bezier/fill")
    save_shader_asset(data, "assets/shaders/extracted/qb_fill/")
"""

from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any


def _find_manimlib_shader_dir() -> Path:
    """Locate manimlib's built-in shader directory."""
    try:
        import manimlib
        base = Path(manimlib.__file__).parent
    except ImportError:
        raise RuntimeError("manimlib not found. Is .venv-manimgl active?") from None

    shader_dir = base / "shaders"
    if shader_dir.exists():
        return shader_dir

    # Fallback: search up the package tree
    for parent in base.parents:
        candidate = parent / "manimlib" / "shaders"
        if candidate.exists():
            return candidate

    raise FileNotFoundError(f"Cannot find manimlib/shaders under {base}")


# Cache the inserts directory once
_INSERTS_DIR: Path | None = None


def _inserts_dir() -> Path:
    global _INSERTS_DIR
    if _INSERTS_DIR is None:
        _INSERTS_DIR = _find_manimlib_shader_dir() / "inserts"
    return _INSERTS_DIR


def _resolve_inserts(source: str, visited: set[str] | None = None) -> tuple[str, list[str]]:
    """Expand ``#INSERT <file>.glsl`` directives recursively.

    Args:
        source: GLSL source string potentially containing #INSERT lines
        visited: set of already-resolved insert paths (cycle detection)

    Returns:
        (expanded_source, list_of_insert_names)
    """
    if visited is None:
        visited = set()

    inserts_used: list[str] = []
    pattern = re.compile(r"^#INSERT\s+(\S+\.glsl)$", re.MULTILINE)

    def replacer(match: re.Match) -> str:
        name = match.group(1)
        # Some inserts reference paths like "inserts/emit_gl_Position.glsl"
        # Strip "inserts/" prefix if present so we look in the inserts dir
        clean_name = name.removeprefix("inserts/")
        insert_path = _inserts_dir() / clean_name

        if not insert_path.exists():
            return f"// MISSING INSERT: {name}\n"

        real_path = str(insert_path.resolve())
        if real_path in visited:
            return f"// CIRCULAR INSERT: {name}\n"

        visited.add(real_path)
        inserts_used.append(clean_name)

        with open(insert_path, encoding="utf-8") as f:
            content = f.read()

        # Recursively resolve nested inserts
        expanded, nested = _resolve_inserts(content, visited)
        inserts_used.extend(nested)
        return expanded

    expanded = pattern.sub(replacer, source)
    return expanded, inserts_used


def extract_builtin_shader(shader_name: str) -> dict[str, Any]:
    """Extract a built-in ManimGL shader as a self-contained asset dict.

    Args:
        shader_name: relative path under ``manimlib/shaders/``,
            e.g. ``"quadratic_bezier/fill"`` or ``"surface"``.

    Returns:
        dict with keys ``vert``, ``frag``, ``geom`` (optional),
        ``inserts``, ``uniforms`` (inferred from code).
    """
    shader_dir = _find_manimlib_shader_dir() / shader_name
    if not shader_dir.exists():
        raise FileNotFoundError(
            f"Built-in shader not found: {shader_name} "
            f"(looked in {shader_dir})"
        )

    result: dict[str, Any] = {"name": shader_name, "inserts": []}

    for stage, fname in [("vert", "vert.glsl"), ("frag", "frag.glsl"), ("geom", "geom.glsl")]:
        fpath = shader_dir / fname
        if fpath.exists():
            with open(fpath, encoding="utf-8") as f:
                raw = f.read()
            expanded, inserts = _resolve_inserts(raw)
            result[stage] = expanded
            result["inserts"].extend(inserts)
        else:
            result[stage] = None

    result["inserts"] = sorted(set(result["inserts"]))

    # Static uniform inference: regex for "uniform <type> <name>;"
    all_code = "\n".join(filter(None, [result.get("vert"), result.get("frag"), result.get("geom")]))
    uniforms = []
    for match in re.finditer(r"\buniform\s+(\w+)\s+(\w+)\s*;", all_code):
        uniforms.append({"name": match.group(2), "type": match.group(1)})
    result["uniforms"] = uniforms

    return result


def save_shader_asset(data: dict[str, Any], output_dir: str) -> str:
    """Save an extracted shader dict as a Layer 2 asset directory.

    Writes ``shader.json``, ``vert.glsl``, ``frag.glsl``, ``geom.glsl``
    (if present).
    """
    os.makedirs(output_dir, exist_ok=True)

    # Write GLSL files
    glsl_files: dict[str, str] = {}
    for stage in ("vert", "frag", "geom"):
        code = data.get(stage)
        if code:
            fname = f"{stage}.glsl"
            with open(os.path.join(output_dir, fname), "w", encoding="utf-8") as f:
                f.write(code)
            glsl_files[stage] = fname

    # Build shader.json
    spec = {
        "schema_version": "1.0",
        "metadata": {
            "name": data["name"].replace("/", "_"),
            "description": f"Extracted from manimlib built-in shader: {data['name']}",
            "author": "manimlib",
            "source": "manimgl_builtin",
            "inserts": data["inserts"],
        },
        "backend": {
            "target": "gpu",
            "glsl_version": "#version 330",
        },
        "glsl": {
            "vertex": glsl_files.get("vert"),
            "fragment": glsl_files.get("frag"),
            "geometry": glsl_files.get("geom"),
        },
        "uniforms": [
            {
                "name": u["name"],
                "type": u["type"],
                "default": 0.0,
                "animation": {"enabled": False},
            }
            for u in data.get("uniforms", [])
        ],
        "render": {
            "fps": 30,
            "duration": 3.0,
            "resolution": [1920, 1080],
            "output_format": "png_sequence",
        },
        "nodegraph": None,
    }

    with open(os.path.join(output_dir, "shader.json"), "w", encoding="utf-8") as f:
        json.dump(spec, f, indent=2, ensure_ascii=False)

    return output_dir


def _test():
    """Quick test: extract the simplest built-in shader."""
    data = extract_builtin_shader("newton_fractal")
    print("Extracted:", data["name"])
    print("Stages: vert=", data["vert"] is not None, "frag=", data["frag"] is not None, "geom=", data["geom"] is not None)
    print("Inserts used:", data["inserts"])
    print("Uniforms inferred:", [u["name"] for u in data["uniforms"]])
    assert "#INSERT" not in data["vert"], "vert still has unresolved inserts"
    assert "#INSERT" not in data["frag"], "frag still has unresolved inserts"
    print("Insert resolution: PASSED")

    out = save_shader_asset(data, ".agent/tmp/test_extracted_newton")
    print("Asset saved to:", out)
    for f in ("shader.json", "vert.glsl", "frag.glsl"):
        assert os.path.exists(os.path.join(out, f)), f"Missing {f}"
    print("Asset files: PASSED")


if __name__ == "__main__":
    _test()
