#!/usr/bin/env python3
"""bin/project_engine.py
Resolve scene engine consistently: manifest.engine → extension → project.yaml defaults.engine.

Used by check-runner, check-static, and related tools.
"""

from __future__ import annotations

import argparse
import json
import os

# When project.yaml has no defaults.engine (should not happen in a healthy repo).
_FALLBACK_DEFAULT: str = "manimgl"


def _here_bin_dir() -> str:
    return os.path.dirname(os.path.abspath(__file__))


def find_project_root(start_path: str | None = None) -> str:
    """Walk upward from start_path (or cwd) until project.yaml is found."""
    if start_path is None:
        start_path = os.getcwd()
    d = os.path.abspath(start_path)
    if os.path.isdir(d):
        candidate = d
    else:
        candidate = os.path.dirname(d)
    seen: set[str] = set()
    for _ in range(64):
        if candidate in seen:
            break
        seen.add(candidate)
        py = os.path.join(candidate, "project.yaml")
        if os.path.isfile(py):
            return candidate
        parent = os.path.dirname(candidate)
        if parent == candidate:
            break
        candidate = parent
    # Last resort: repo root = parent of bin/
    return os.path.dirname(_here_bin_dir())


def load_defaults_engine(project_root: str) -> str:
    """Return ``defaults.engine`` from project.yaml, else ``_FALLBACK_DEFAULT``."""
    path = os.path.join(project_root, "project.yaml")
    if not os.path.isfile(path):
        return _FALLBACK_DEFAULT
    try:
        import yaml  # type: ignore[import-untyped]

        with open(path, encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
        defaults = data.get("defaults")
        if isinstance(defaults, dict):
            eng = defaults.get("engine")
            if isinstance(eng, str) and eng.strip():
                return eng.strip()
    except Exception:
        pass
    return _FALLBACK_DEFAULT


def resolve_engine_from_manifest(manifest: dict | None, scene_dir: str, project_root: str) -> str:
    """Resolve engine when manifest dict is already loaded."""
    if manifest:
        eng = manifest.get("engine")
        if isinstance(eng, str) and eng.strip():
            return eng.strip()

    sd = os.path.abspath(scene_dir)
    if os.path.isfile(os.path.join(sd, "scene.tsx")):
        return "motion_canvas"
    if os.path.isfile(os.path.join(sd, "scene.py")):
        return load_defaults_engine(project_root)
    return load_defaults_engine(project_root)


def resolve_engine(scene_dir: str, project_root: str | None = None) -> str:
    """Full resolution: read manifest.json if present, then same rules as ``resolve_engine_from_manifest``."""
    sd = os.path.abspath(scene_dir)
    root = project_root if project_root else find_project_root(sd)
    manifest: dict | None = None
    mp = os.path.join(sd, "manifest.json")
    if os.path.isfile(mp):
        try:
            with open(mp, encoding="utf-8") as f:
                manifest = json.load(f)
        except (json.JSONDecodeError, OSError):
            manifest = {}
    return resolve_engine_from_manifest(manifest, sd, root)


def _main() -> None:
    p = argparse.ArgumentParser(description="Print resolved engine name for a scene directory.")
    p.add_argument(
        "--scene-dir",
        required=True,
        help="Scene directory (with optional manifest.json / scene.py / scene.tsx)",
    )
    p.add_argument(
        "--project-root",
        default=None,
        help="MaCode repo root (default: discover from scene-dir)",
    )
    args = p.parse_args()
    root = args.project_root or find_project_root(args.scene_dir)
    print(resolve_engine(args.scene_dir, root))


if __name__ == "__main__":
    _main()
