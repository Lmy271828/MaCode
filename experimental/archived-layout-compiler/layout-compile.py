#!/usr/bin/env python3
"""bin/layout-compile.py
Layout Compiler — Phase 1 of two-stage compilation.

.. deprecated::
    Layout Compiler is archived. Use ZoneScene + self.place() for new scenes.
    See .agents/skills/macode-host-agent/SKILL.md for the current recommended path.

Content manifest → Layout config (deterministic allocation + constraint validation).

Usage:
    bin/layout-compile.py <content_manifest.json> \
        [--layout PROFILE] [--narrative PROFILE] \
        [--output layout_config.yaml]
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, TextIO

# ---------------------------------------------------------------------------
# Resolve paths relative to project root
# ---------------------------------------------------------------------------

SCRIPT_DIR = Path(__file__).parent.resolve()
PROJECT_ROOT = SCRIPT_DIR.parent

LAYOUTS_DIR = PROJECT_ROOT / "engines" / "manimgl" / "src" / "templates" / "layouts"
NARRATIVES_DIR = PROJECT_ROOT / "engines" / "manimgl" / "src" / "templates" / "narratives"


# ---------------------------------------------------------------------------
# YAML dumper (no external dependencies)
# ---------------------------------------------------------------------------

def _yaml_scalar(value: Any) -> str:
    """Return a YAML-safe scalar representation."""
    if isinstance(value, str):
        if not value or any(ch in value for ch in ':{}[]#|>-\n\r"\''):
            # JSON-style double-quoted string (valid YAML)
            return json.dumps(value, ensure_ascii=False)
        return value
    elif isinstance(value, bool):
        return "true" if value else "false"
    elif value is None:
        return "null"
    elif isinstance(value, (list, tuple, dict)):
        return json.dumps(value, ensure_ascii=False)
    return str(value)


def _is_inline_list(value: list) -> bool:
    """Check if a list should be rendered inline."""
    if not value:
        return True
    # Short lists of scalars can be inline
    if len(value) <= 4 and all(not isinstance(x, (dict, list)) for x in value):
        return True
    return False


def _dump_yaml_obj(obj: Any, indent: int, file: TextIO) -> None:
    """Recursively dump a Python object as YAML."""
    prefix = "  " * indent
    if isinstance(obj, dict):
        for k, v in obj.items():
            if isinstance(v, dict):
                file.write(f"{prefix}{k}:\n")
                _dump_yaml_obj(v, indent + 1, file)
            elif isinstance(v, list):
                if _is_inline_list(v):
                    file.write(f"{prefix}{k}: {_yaml_scalar(v)}\n")
                else:
                    file.write(f"{prefix}{k}:\n")
                    _dump_yaml_obj(v, indent + 1, file)
            else:
                file.write(f"{prefix}{k}: {_yaml_scalar(v)}\n")
    elif isinstance(obj, list):
        if not obj:
            # Empty list at this level: caller already handled or it's a root list
            return
        for item in obj:
            if isinstance(item, dict) and item:
                keys = list(item.keys())
                first_k = keys[0]
                first_v = item[first_k]
                if isinstance(first_v, (dict, list)) and not _is_inline_list(first_v):
                    file.write(f"{prefix}- {first_k}:\n")
                    _dump_yaml_obj(first_v, indent + 1, file)
                else:
                    file.write(f"{prefix}- {first_k}: {_yaml_scalar(first_v)}\n")
                for k in keys[1:]:
                    v = item[k]
                    if isinstance(v, (dict, list)):
                        if _is_inline_list(v):
                            file.write(f"{prefix}  {k}: {_yaml_scalar(v)}\n")
                        else:
                            file.write(f"{prefix}  {k}:\n")
                            _dump_yaml_obj(v, indent + 2, file)
                    else:
                        file.write(f"{prefix}  {k}: {_yaml_scalar(v)}\n")
            elif isinstance(item, dict) and not item:
                file.write(f"{prefix}- {{}}\n")
            else:
                file.write(f"{prefix}- {_yaml_scalar(item)}\n")


def dump_yaml(obj: Any, file: TextIO | None = None) -> str | None:
    """Dump object as YAML. Returns string if *file* is None."""
    if file is None:
        import io

        buf = io.StringIO()
        _dump_yaml_obj(obj, 0, buf)
        return buf.getvalue()
    _dump_yaml_obj(obj, 0, file)
    return None


# ---------------------------------------------------------------------------
# Profile loading
# ---------------------------------------------------------------------------

def load_layout_profile(name: str) -> dict[str, Any]:
    path = LAYOUTS_DIR / f"{name}.json"
    if not path.exists():
        raise FileNotFoundError(f"Layout profile not found: {path}")
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def load_narrative_profile(name: str) -> dict[str, Any]:
    path = NARRATIVES_DIR / f"{name}.json"
    if not path.exists():
        raise FileNotFoundError(f"Narrative profile not found: {path}")
    with open(path, encoding="utf-8") as f:
        return json.load(f)


# ---------------------------------------------------------------------------
# Allocation algorithm
# ---------------------------------------------------------------------------

IMPORTANCE_ORDER = {"high": 0, "medium": 1, "low": 2}


def matches_stage_type(stage_type: str, content_type: str) -> bool:
    """Check if content type matches stage type."""
    if stage_type == "text" and content_type in ("text", "formula"):
        return True
    if stage_type == "visual" and content_type == "visual":
        return True
    return False


def allocate_content(
    content_pool: list[dict[str, Any]],
    narrative: dict[str, Any],
    layout: dict[str, Any],
) -> tuple[list[dict[str, Any]], list[str]]:
    """Allocate content items to narrative stages.

    Returns:
        (stages_output, list of error messages)
    """
    pool = list(content_pool)  # shallow copy
    zones = layout.get("zones", {})
    stages_out: list[dict[str, Any]] = []
    zone_counts: dict[str, int] = dict.fromkeys(zones, 0)
    total_text_chars = 0

    for stage_def in narrative.get("stages", []):
        stage_type = stage_def.get("type", "visual")
        zone_name = stage_def["zone"]
        zone = zones.get(zone_name, {})
        max_objects = zone.get("max_objects", 999)

        # Filter candidates from pool
        candidates = [
            item for item in pool
            if matches_stage_type(stage_type, item.get("type", ""))
        ]

        # Sort by importance (high > medium > low)
        candidates.sort(
            key=lambda x: IMPORTANCE_ORDER.get(x.get("importance", "medium"), 1)
        )

        # Take up to max_objects
        allocated = candidates[:max_objects]

        # Remove allocated from pool
        for item in allocated:
            pool.remove(item)

        # Count text characters
        for item in allocated:
            if item.get("type") in ("text", "formula"):
                text = item.get("text", "") or item.get("latex", "")
                total_text_chars += len(text)

        # Update zone counts
        zone_counts[zone_name] = zone_counts.get(zone_name, 0) + len(allocated)

        # Build output stage
        stage_out = {
            "id": stage_def["id"],
            "zone": zone_name,
            "type": stage_type,
            "duration_hint": stage_def.get("duration_hint", 1.0),
            "content": [dict(item) for item in allocated],
        }
        stages_out.append(stage_out)

    # Validate constraints
    errors: list[str] = []

    for zone_name, count in zone_counts.items():
        max_obj = zones.get(zone_name, {}).get("max_objects")
        if max_obj is not None and count > max_obj:
            errors.append(
                f"Zone '{zone_name}': max_objects={max_obj}, allocated={count}"
            )

    constraints = layout.get("constraints", {})
    max_chars = constraints.get("max_total_text_chars")
    if max_chars is not None and total_text_chars > max_chars:
        errors.append(
            f"Total text characters ({total_text_chars}) exceeds limit ({max_chars})"
        )

    if constraints.get("primary_zone_must_have_visual"):
        primary_zone = None
        for name, meta in zones.items():
            if meta.get("importance") == "primary":
                primary_zone = name
                break

        if primary_zone:
            has_visual = False
            for stage in stages_out:
                if stage["zone"] == primary_zone and stage["type"] == "visual":
                    for item in stage["content"]:
                        if item.get("type") == "visual":
                            has_visual = True
                            break
                if has_visual:
                    break

            if not has_visual:
                errors.append(
                    f"Primary zone '{primary_zone}' must have at least one visual"
                )

    return stages_out, errors


# ---------------------------------------------------------------------------
# Suggestion generator
# ---------------------------------------------------------------------------

def generate_suggestions(errors: list[str], layout: dict[str, Any]) -> list[str]:
    """Generate human-readable fix suggestions for constraint violations."""
    suggestions = []
    zones = layout.get("zones", {})
    for err in errors:
        if err.startswith("Zone '"):
            # Extract zone name
            zone_name = err.split("'")[1]
            suggestion = (
                f"Suggestion: Move excess objects from '{zone_name}' to another zone "
                f"or reduce content count. Allowed types: "
                f"{zones.get(zone_name, {}).get('allowed_types', ['any'])}"
            )
            suggestions.append(suggestion)
        elif "text characters" in err.lower():
            suggestions.append(
                "Suggestion: Reduce text length, split into multiple scenes, "
                "or lower importance on non-essential text items."
            )
        elif "primary zone" in err.lower():
            suggestions.append(
                "Suggestion: Add a visual primitive (e.g. Circle, Axes, NumberLine) "
                "with importance='high' to the content manifest."
            )
    return suggestions


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Compile content manifest to layout config."
    )
    parser.add_argument("manifest", help="Path to content_manifest.json")
    parser.add_argument("--layout", default=None, help="Layout profile name")
    parser.add_argument("--narrative", default=None, help="Narrative profile name")
    parser.add_argument("--output", default="layout_config.yaml", help="Output YAML path")
    args = parser.parse_args(argv)

    print("[layout-compile] WARNING: Layout Compiler is archived. "
          "ZoneScene + self.place() is the recommended layout path.", file=sys.stderr)

    # Load manifest
    manifest_path = Path(args.manifest)
    if not manifest_path.exists():
        print(f"[layout-compile] ERROR: Manifest not found: {manifest_path}", file=sys.stderr)
        return 1

    with open(manifest_path, encoding="utf-8") as f:
        manifest = json.load(f)

    layout_profile = args.layout or manifest.get("layout_profile", "lecture_3zones")
    narrative_profile = args.narrative or manifest.get("narrative_profile", "definition_reveal")

    # Load profiles
    try:
        layout = load_layout_profile(layout_profile)
    except FileNotFoundError as exc:
        print(f"[layout-compile] ERROR: {exc}", file=sys.stderr)
        return 1

    try:
        narrative = load_narrative_profile(narrative_profile)
    except FileNotFoundError as exc:
        print(f"[layout-compile] ERROR: {exc}", file=sys.stderr)
        return 1

    # Allocate content
    stages_out, errors = allocate_content(
        manifest.get("content", []), narrative, layout
    )

    if errors:
        print("[layout-compile] ERROR: Constraint violation", file=sys.stderr)
        for err in errors:
            print(f"  {err}", file=sys.stderr)
        for suggestion in generate_suggestions(errors, layout):
            print(f"  {suggestion}", file=sys.stderr)
        return 1

    # Build output
    output = {
        "layout_profile": layout_profile,
        "narrative_profile": narrative_profile,
        "canvas": layout.get("canvas", [1920, 1080]),
        "stages": stages_out,
    }

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        dump_yaml(output, f)

    print(f"[layout-compile] OK: {output_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
