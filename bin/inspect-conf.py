#!/usr/bin/env python3
"""bin/inspect-conf.py
Parse engine.conf and output structured JSON (PyYAML only).

Usage:
    inspect-conf.py <engine.conf>

Output: JSON to stdout
Exit: 0 on success, 1 on error
"""

import json
import sys
from pathlib import Path

import yaml

STRING_KEYS = (
    "render_script",
    "pre_render_script",
    "service_script",
    "inspect_script",
    "validate_script",
    "sourcemap",
)
INT_KEYS = ("service_port_min", "service_port_max")


def _normalize_scene_extensions(data: dict) -> list:
    se = data.get("scene_extensions")
    if se is None:
        return [".py"]
    if isinstance(se, list):
        out = [str(x).strip() for x in se if x is not None and str(x).strip()]
        return out if out else [".py"]
    if isinstance(se, str):
        s = se.strip()
        if not s:
            return [".py"]
        if s.startswith("[") and s.endswith("]") and len(s) >= 2:
            inner = s[1:-1].strip()
            if not inner:
                return [".py"]
            parts = [p.strip().strip('"').strip("'") for p in inner.split(",") if p.strip()]
            return parts if parts else [".py"]
        return [s]
    return [".py"]


def parse_engine_conf(path: str) -> dict:
    if not Path(path).is_file():
        return {
            "scene_extensions": [".py"],
            "mode": "batch",
        }

    with Path(path).open(encoding="utf-8") as f:
        raw = yaml.safe_load(f)

    data = raw if isinstance(raw, dict) else {}

    result = {
        "scene_extensions": _normalize_scene_extensions(data),
        "mode": (str(data.get("mode") or "batch").strip() or "batch"),
    }

    for key in STRING_KEYS:
        val = data.get(key)
        if val is None:
            continue
        s = str(val).strip()
        if s:
            result[key] = s

    for key in INT_KEYS:
        val = data.get(key)
        if val is None:
            continue
        try:
            result[key] = int(val)
        except (TypeError, ValueError):
            pass

    return result


def main():
    if len(sys.argv) < 2 or sys.argv[1] in ("-h", "--help"):
        print("Usage: inspect-conf.py <engine.conf>")
        print("")
        print("Parse engine.conf and output structured JSON.")
        print("")
        print("Arguments:")
        print("  <engine.conf>    Path to engine.conf file")
        print("")
        print("Output: JSON to stdout")
        print("Exit: 0 on success, 1 on error")
        sys.exit(0 if len(sys.argv) >= 2 and sys.argv[1] in ("-h", "--help") else 1)

    try:
        result = parse_engine_conf(sys.argv[1])
    except yaml.YAMLError as e:
        print(f"Error: invalid YAML in engine.conf: {e}", file=sys.stderr)
        sys.exit(1)

    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
