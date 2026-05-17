#!/usr/bin/env python3
"""bin/sourcemap-version-check.py
Detect engine version drift against engines/*/sourcemap.json (canonical).

Runs without Host Agent intervention. Designed to be called by setup.sh,
macode status, or CI to surface outdated sourcemap.json early.

Usage:
    sourcemap-version-check.py [--all] [engine_name]

Exit codes:
    0 - all versions match (or engine not installed)
    1 - one or more declared versions are outdated vs installed engine
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path


def get_project_root() -> Path:
    return Path(__file__).parent.parent.resolve()


def extract_sourcemap_declared_version(jp: Path) -> str:
    """Parse engine version from engines/{engine}/sourcemap.json."""
    if not jp.is_file():
        return ""
    try:
        data = json.loads(jp.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return ""
    ver = data.get("version")
    return ver.strip() if isinstance(ver, str) else ""


def get_manimce_version(project_root: Path) -> str | None:
    py = project_root / ".venv" / "bin" / "python"
    if not py.exists():
        return None
    try:
        result = subprocess.run(
            [str(py), "-c", "import manim; print(manim.__version__)"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode == 0:
            return result.stdout.strip()
    except Exception:
        pass
    return None


def get_manimgl_version(project_root: Path) -> str | None:
    py = project_root / ".venv-manimgl" / "bin" / "python"
    if not py.exists():
        return None
    try:
        result = subprocess.run(
            [str(py), "-c", "import manimlib; print(manimlib.__version__)"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode == 0:
            return result.stdout.strip()
    except Exception:
        pass
    return None


def get_motion_canvas_version(project_root: Path) -> str | None:
    try:
        result = subprocess.run(
            ["node", "-e", 'console.log(require("@motion-canvas/core/package.json").version)'],
            capture_output=True,
            text=True,
            timeout=10,
            cwd=str(project_root),
        )
        if result.returncode == 0:
            return result.stdout.strip()
    except Exception:
        pass
    return None


ENGINE_VERSION_DETECTORS = {
    "manim": get_manimce_version,
    "manimgl": get_manimgl_version,
    "motion_canvas": get_motion_canvas_version,
}


def check_engine(engine: str, project_root: Path) -> dict:
    jp = project_root / "engines" / engine / "sourcemap.json"
    result = {
        "engine": engine,
        "sourcemap_exists": jp.exists(),
        "sourcemap_version": "",
        "installed_version": None,
        "match": True,
        "message": "",
    }

    if not jp.exists():
        result["match"] = True
        result["message"] = "No sourcemap.json"
        return result

    result["sourcemap_version"] = extract_sourcemap_declared_version(jp)
    detector = ENGINE_VERSION_DETECTORS.get(engine)
    if not detector:
        result["match"] = True
        result["message"] = "No version detector for this engine"
        return result

    installed = detector(project_root)
    result["installed_version"] = installed

    if installed is None:
        result["match"] = True
        result["message"] = "Engine not installed, cannot verify"
        return result

    if not result["sourcemap_version"]:
        result["match"] = False
        result["message"] = "sourcemap.json missing version field"
        return result

    # Loose match: installed version starts with sourcemap version prefix
    # or exact match. This handles patch-level drift.
    smv = result["sourcemap_version"]
    if installed == smv or installed.startswith(smv + "."):
        result["match"] = True
        result["message"] = f"OK ({installed})"
    else:
        result["match"] = False
        result["message"] = f"DRIFT: sourcemap.json={smv}, installed={installed}"

    return result


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Detect engine version drift against engines/*/sourcemap.json",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("engine", nargs="?", help="Engine name to check")
    parser.add_argument("--all", action="store_true", help="Check all engines")
    parser.add_argument("--json", action="store_true", help="Output JSON")
    args = parser.parse_args()

    project_root = get_project_root()

    engines = []
    if args.all:
        engines_dir = project_root / "engines"
        if engines_dir.exists():
            engines = sorted([d.name for d in engines_dir.iterdir() if d.is_dir()])
    elif args.engine:
        engines = [args.engine]
    else:
        # Default: check engines with installed sourcemaps
        engines_dir = project_root / "engines"
        if engines_dir.exists():
            engines = sorted(
                [
                    d.name
                    for d in engines_dir.iterdir()
                    if d.is_dir() and (d / "sourcemap.json").exists()
                ]
            )

    results = [check_engine(e, project_root) for e in engines]
    drifted = [r for r in results if not r["match"]]

    if args.json:
        print(
            json.dumps(
                {
                    "drift_count": len(drifted),
                    "engines": results,
                },
                indent=2,
                ensure_ascii=False,
            )
        )
    else:
        print("=== SOURCEMAP Version Check ===")
        for r in results:
            icon = "✓" if r["match"] else "✗"
            print(f"  {icon} {r['engine']}: {r['message']}")
        print("")
        if drifted:
            print(f"WARNING: {len(drifted)} engine(s) have version drift.")
            print("  Action: bump engines/*/sourcemap.json version and run validate_sourcemap.sh")
        else:
            print("All sourcemap.json versions match installed engines.")

    return 1 if drifted else 0


if __name__ == "__main__":
    sys.exit(main())
