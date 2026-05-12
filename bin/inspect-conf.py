#!/usr/bin/env python3
"""bin/inspect-conf.py
Parse engine.conf and output structured JSON.

Falls back to grep/awk parsing if yq is unavailable.
Only handles flat string/integer fields and simple list fields.

Usage:
    inspect-conf.py <engine.conf>

Output: JSON to stdout
Exit: 0 on success, 1 on error
"""

import json
import os
import subprocess
import sys


def parse_with_yq(path: str) -> dict:
    """Try yq first for robust YAML parsing."""
    result = {}

    # scene_extensions (list)
    r = subprocess.run(
        ["yq", "-r", '.scene_extensions[]', path],
        capture_output=True, text=True, check=False,
    )
    if r.returncode == 0 and r.stdout.strip():
        result["scene_extensions"] = [line.strip() for line in r.stdout.strip().split("\n") if line.strip()]

    # mode
    r = subprocess.run(
        ["yq", "-r", '.mode // "batch"', path],
        capture_output=True, text=True, check=False,
    )
    if r.returncode == 0 and r.stdout.strip():
        result["mode"] = r.stdout.strip()

    # Flat string fields
    for key in ("render_script", "pre_render_script", "service_script",
                "inspect_script", "validate_script", "sourcemap"):
        r = subprocess.run(
            ["yq", "-r", f'.{key} // ""', path],
            capture_output=True, text=True, check=False,
        )
        if r.returncode == 0 and r.stdout.strip():
            result[key] = r.stdout.strip()

    # Integer fields
    for key in ("service_port_min", "service_port_max"):
        r = subprocess.run(
            ["yq", "-r", f'.{key} // ""', path],
            capture_output=True, text=True, check=False,
        )
        if r.returncode == 0 and r.stdout.strip():
            try:
                result[key] = int(r.stdout.strip())
            except ValueError:
                pass

    return result


def parse_with_grep(path: str) -> dict:
    """Fallback: grep/awk for flat fields."""
    result = {}

    # scene_extensions
    r = subprocess.run(
        ["grep", "-oP", r"^scene_extensions:\s*\K.*", path],
        capture_output=True, text=True, check=False,
    )
    if r.returncode == 0 and r.stdout.strip():
        raw = r.stdout.strip()
        raw = raw.lstrip("[").rstrip("]")
        result["scene_extensions"] = [x.strip().strip('"').strip("'") for x in raw.split(",") if x.strip()]

    if not result.get("scene_extensions"):
        r = subprocess.run(
            ["awk", "/scene_extensions:/{found=1; next} found && /^[[:space:]]*-/{print $2; next} found && /^[[:space:]]*[^#-]/{exit}", path],
            capture_output=True, text=True, check=False,
        )
        if r.returncode == 0 and r.stdout.strip():
            result["scene_extensions"] = [line.strip().strip('"').strip("'") for line in r.stdout.strip().split("\n") if line.strip()]

    # mode
    r = subprocess.run(
        ["grep", "-oP", r"^mode:\s*\K\S+", path],
        capture_output=True, text=True, check=False,
    )
    if r.returncode == 0 and r.stdout.strip():
        result["mode"] = r.stdout.strip()

    # Flat string fields
    for key in ("render_script", "pre_render_script", "service_script",
                "inspect_script", "validate_script", "sourcemap"):
        r = subprocess.run(
            ["grep", "-oP", rf'^{key}:\s*\K\S+', path],
            capture_output=True, text=True, check=False,
        )
        if r.returncode == 0 and r.stdout.strip():
            result[key] = r.stdout.strip()

    # Integer fields
    for key in ("service_port_min", "service_port_max"):
        r = subprocess.run(
            ["grep", "-oP", rf'^{key}:\s*\K\d+', path],
            capture_output=True, text=True, check=False,
        )
        if r.returncode == 0 and r.stdout.strip():
            try:
                result[key] = int(r.stdout.strip())
            except ValueError:
                pass

    return result


def parse_engine_conf(path: str) -> dict:
    if not os.path.isfile(path):
        return {
            "scene_extensions": [".py"],
            "mode": "batch",
        }

    result = {}

    # Try yq first
    try:
        result = parse_with_yq(path)
    except FileNotFoundError:
        pass

    # Fallback to grep/awk for missing fields
    if not result.get("scene_extensions"):
        result.update(parse_with_grep(path))

    if not result.get("scene_extensions"):
        result["scene_extensions"] = [".py"]

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

    result = parse_engine_conf(sys.argv[1])
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
