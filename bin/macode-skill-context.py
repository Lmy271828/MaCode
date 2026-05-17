#!/usr/bin/env python3
"""bin/macode-skill-context.py
Generate dynamic skill context for Host Agent consumption.

Outputs JSON to .agent/context/skill_context.json containing:
- project configuration
- engine health & availability
- scene inventory
- recent errors / activity
- recommended next steps
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from datetime import UTC, datetime

_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _load_project_config() -> dict:
    path = os.path.join(_PROJECT_ROOT, "project.yaml")
    if not os.path.isfile(path):
        return {}
    try:
        import yaml

        with open(path, encoding="utf-8") as f:
            return yaml.safe_load(f) or {}
    except Exception:
        return {}


def _scan_engines() -> dict:
    engines = {}
    engines_dir = os.path.join(_PROJECT_ROOT, "engines")
    if not os.path.isdir(engines_dir):
        return engines
    for name in sorted(os.listdir(engines_dir)):
        ed = os.path.join(engines_dir, name)
        if not os.path.isdir(ed):
            continue
        conf = os.path.join(ed, "engine.conf")
        sourcemap = os.path.join(ed, "sourcemap.json")
        info = {
            "has_conf": os.path.isfile(conf),
            "has_sourcemap": os.path.isfile(sourcemap),
        }
        # Quick version probe
        if os.path.isfile(conf):
            try:
                result = subprocess.run(
                    ["bash", "-c", f"grep '^version_cmd:' '{conf}' | head -1"],
                    capture_output=True,
                    text=True,
                )
                if result.returncode == 0:
                    vcmd = result.stdout.strip().split(":", 1)[1].strip().strip('"')
                    vcmd = vcmd.replace('\\"', '"')
                    vresult = subprocess.run(vcmd, shell=True, capture_output=True, text=True)
                    if vresult.returncode == 0:
                        info["version"] = vresult.stdout.strip()
            except Exception:
                pass
        engines[name] = info
    return engines


def _scan_scenes() -> list[dict]:
    scenes = []
    scenes_dir = os.path.join(_PROJECT_ROOT, "scenes")
    if not os.path.isdir(scenes_dir):
        return scenes
    for d in sorted(os.listdir(scenes_dir)):
        sd = os.path.join(scenes_dir, d)
        if not os.path.isdir(sd):
            continue
        manifest_path = os.path.join(sd, "manifest.json")
        info = {"id": d, "has_manifest": os.path.isfile(manifest_path)}
        if os.path.isfile(manifest_path):
            try:
                with open(manifest_path, encoding="utf-8") as f:
                    m = json.load(f)
                info["engine"] = m.get("engine", "?")
                info["duration"] = m.get("duration", "?")
                info["type"] = m.get("type", "scene")
            except Exception:
                pass
        # Check for uncommitted changes
        try:
            result = subprocess.run(
                ["git", "diff", "--quiet", "--", sd],
                cwd=_PROJECT_ROOT,
                capture_output=True,
            )
            info["dirty"] = result.returncode != 0
        except Exception:
            info["dirty"] = False
        scenes.append(info)
    return scenes


def _recent_errors() -> dict | None:
    log_dir = os.path.join(_PROJECT_ROOT, ".agent", "log")
    if not os.path.isdir(log_dir):
        return None
    logs = sorted(
        [f for f in os.listdir(log_dir) if f.endswith(".log")],
        reverse=True,
    )
    if not logs:
        return None
    recent = os.path.join(log_dir, logs[0])
    try:
        with open(recent, encoding="utf-8") as f:
            content = f.read()
        lines = content.strip().split("\n")
        # Extract ERROR / FATAL lines
        errors = [ln for ln in lines if "ERROR" in ln or "FATAL" in ln or "Traceback" in ln]
        return {
            "log_file": logs[0],
            "total_lines": len(lines),
            "error_lines": errors[-5:] if errors else [],
            "last_lines": lines[-5:],
        }
    except Exception:
        return None


def _last_render() -> dict | None:
    tmp_dir = os.path.join(_PROJECT_ROOT, ".agent", "tmp")
    if not os.path.isdir(tmp_dir):
        return None
    finals = []
    for root, _dirs, files in os.walk(tmp_dir):
        for f in files:
            if f == "final.mp4":
                finals.append(os.path.join(root, f))
    if not finals:
        return None
    finals.sort(key=lambda p: os.path.getmtime(p), reverse=True)
    latest = finals[0]
    scene_name = os.path.basename(os.path.dirname(latest))
    return {
        "scene": scene_name,
        "path": latest,
        "mtime": datetime.fromtimestamp(os.path.getmtime(latest), UTC).isoformat(),
    }


def main() -> int:
    config = _load_project_config()
    engines = _scan_engines()
    scenes = _scan_scenes()
    recent_error = _recent_errors()
    last_render = _last_render()

    context = {
        "project": {
            "name": config.get("project", {}).get("name", "MaCode"),
            "root": _PROJECT_ROOT,
            "default_engine": config.get("defaults", {}).get("engine", "?"),
        },
        "engines": engines,
        "scenes": {
            "count": len(scenes),
            "list": scenes,
            "composite_count": sum(1 for s in scenes if s.get("type") == "composite-unified"),
        },
        "activity": {
            "last_render": last_render,
            "recent_errors": recent_error,
        },
        "recommendations": [],
        "timestamp": datetime.now(UTC).isoformat(),
    }

    # Generate recommendations
    recs = context["recommendations"]
    dirty_scenes = [s["id"] for s in scenes if s.get("dirty")]
    if dirty_scenes:
        recs.append(f"Scenes with uncommitted changes: {', '.join(dirty_scenes)}")
    if recent_error and recent_error.get("error_lines"):
        recs.append("Recent errors detected in logs — review .agent/log/")
    engines_without_sourcemap = [n for n, e in engines.items() if not e.get("has_sourcemap")]
    if engines_without_sourcemap:
        recs.append(f"Engines missing sourcemap: {', '.join(engines_without_sourcemap)}")
    if not scenes:
        recs.append("No scenes found. Use 'macode init <dir>' to create one.")

    output_dir = os.path.join(_PROJECT_ROOT, ".agent", "context")
    os.makedirs(output_dir, exist_ok=True)
    output_path = os.path.join(output_dir, "skill_context.json")
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(context, f, indent=2, ensure_ascii=False)
        f.write("\n")

    print(f"Skill context written to {output_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
