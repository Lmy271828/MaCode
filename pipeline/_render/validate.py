"""Validation stages: manifest, engine.conf, api-gate, static checks.

The orchestrator calls ``validate_scene(...)`` once. It returns a fully-populated
``RenderContext`` consumed by ``engine.run(...)`` and ``encode.run(...)``.

All failures fail-loud via ``sys.exit(1)`` to preserve the existing CLI contract.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from dataclasses import dataclass, field
from typing import Any

from ._paths import (
    PROJECT_ROOT,
    get_python,
    locate_scene_file,
    read_manifest,
    scene_inherits_from,
)


@dataclass
class RenderContext:
    """Everything the engine + encoder need, derived from manifest + CLI args."""

    scene_dir: str
    scene_name: str
    scene_file: str
    manifest: dict
    engine: str
    engine_conf: dict
    ext_list: list[str]
    engine_mode: str
    render_script_rel: str
    unified_mc_render: bool
    fps: int
    duration: float
    width: int
    height: int
    output_dir: str
    frames_dir: str
    log_file: str
    skip_checks: bool = False
    extras: dict[str, Any] = field(default_factory=dict)


def _exit_with(msg: str, code: int = 1) -> None:
    print(msg, file=sys.stderr)
    sys.exit(code)


def _parse_engine_conf(engine: str) -> dict:
    engine_conf_path = os.path.join(PROJECT_ROOT, "engines", engine, "engine.conf")
    if not os.path.isfile(engine_conf_path):
        _exit_with(
            f"Error: engine.conf not found for '{engine}'\n  Expected: {engine_conf_path}"
        )
    result = subprocess.run(
        [get_python(), os.path.join(PROJECT_ROOT, "bin", "inspect-conf.py"), engine_conf_path],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        _exit_with(f"Error: failed to parse engine.conf for '{engine}'")
    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        _exit_with(f"Error: invalid engine.conf output: {exc}")
        return {}  # unreachable, satisfies type checker


def _run_validate_manifest(manifest_path: str) -> None:
    result = subprocess.run(
        [
            get_python(),
            os.path.join(PROJECT_ROOT, "pipeline", "validate-manifest.py"),
            manifest_path,
        ],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        print(result.stdout + result.stderr, file=sys.stderr)
        sys.exit(1)
    print("[validate] OK")


def _run_api_gate(scene_file: str, engine: str, log_file: str) -> None:
    sourcemap_path = os.path.join(PROJECT_ROOT, "engines", engine, "sourcemap.json")
    api_gate = os.path.join(PROJECT_ROOT, "bin", "api-gate.py")
    if not (os.path.isfile(sourcemap_path) and os.path.isfile(api_gate) and os.access(api_gate, os.X_OK)):
        return
    print(f"[api-gate] Checking {scene_file} against sourcemap.json BLACKLIST...")
    with open(log_file, "a", encoding="utf-8") as logf:
        result = subprocess.run(
            [get_python(), api_gate, scene_file, sourcemap_path, "--engine", engine],
            stdout=logf,
            stderr=subprocess.STDOUT,
        )
    if result.returncode != 0:
        print("[api-gate] BLOCKED. Fix violations before rendering.")
        subprocess.run(["tail", "-n", "10", log_file], check=False)
        sys.exit(1)
    print("[api-gate] OK")


def _run_dry_run(scene_file: str, engine: str) -> None:
    """Fast pre-render validation: syntax, imports, LaTeX, ffmpeg filters."""
    dry_run = os.path.join(PROJECT_ROOT, "bin", "dry-run.py")
    if not os.path.isfile(dry_run):
        return
    print(f"[dry-run] Pre-flight check for {scene_file}...")
    result = subprocess.run(
        [get_python(), dry_run, scene_file, engine],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        print(result.stdout)
        print(result.stderr, file=sys.stderr)
        print("[dry-run] FAILED. Fix errors before rendering.", file=sys.stderr)
        sys.exit(1)
    print("[dry-run] OK")


def _run_one_check(
    label: str,
    checker_basename: str,
    scene_file: str,
    report_path: str,
    *extra_args: str,
) -> None:
    print(f"[{label}] Running...")
    result = subprocess.run(
        [
            get_python(),
            os.path.join(PROJECT_ROOT, "bin", checker_basename),
            scene_file,
            *extra_args,
            "--output",
            report_path,
        ],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        print(f"[{label}] FAILED. See report for details.")
        print(result.stdout)
        sys.exit(1)
    print(f"[{label}] OK")


def _run_static_checks(
    *, scene_file: str, scene_name: str, manifest: dict, check_reports_dir: str
) -> None:
    """Layout / narrative / density. Only for Python scenes with Zoned base class."""
    if not scene_file.endswith(".py"):
        return

    is_zoned = scene_inherits_from(scene_file, ["ZoneScene", "NarrativeScene"])
    if not is_zoned:
        print("[checks] Scene does not inherit ZoneScene/NarrativeScene — skipping static checks.")
        return

    layout_profile = manifest.get("layout_profile")
    narrative_profile = manifest.get("narrative_profile")

    if layout_profile:
        _run_one_check(
            f"layout-check (profile={layout_profile})",
            "check-layout.py",
            scene_file,
            os.path.join(check_reports_dir, f"{scene_name}_layout.json"),
            "--layout-profile",
            layout_profile,
        )
    if narrative_profile:
        _run_one_check(
            f"narrative-check (profile={narrative_profile})",
            "check-narrative.py",
            scene_file,
            os.path.join(check_reports_dir, f"{scene_name}_narrative.json"),
            "--narrative-profile",
            narrative_profile,
        )
    # Density check runs for all zoned scenes
    _run_one_check(
        "density-check",
        "check-density.py",
        scene_file,
        os.path.join(check_reports_dir, f"{scene_name}_density.json"),
    )


def validate_scene(
    *,
    scene_dir: str,
    scene_name: str,
    args_fps: int | None,
    args_duration: float | None,
    args_width: int | None,
    args_height: int | None,
    skip_checks: bool,
    skip_dry_run: bool = False,
) -> RenderContext:
    """Full validation pipeline. Returns RenderContext or sys.exit(1) on failure."""
    manifest_path = os.path.join(scene_dir, "manifest.json")
    if not os.path.isfile(manifest_path):
        _exit_with(f"Error: manifest.json not found in {scene_dir}")

    manifest = read_manifest(manifest_path)
    engine = manifest.get("engine", "manim")
    engine_conf = _parse_engine_conf(engine)
    ext_list = engine_conf["scene_extensions"]
    engine_mode = engine_conf["mode"]
    render_script_rel = (engine_conf.get("render_script") or "").replace("\\", "/")
    unified_mc_render = render_script_rel.endswith("render.mjs")

    scene_file = locate_scene_file(scene_dir, ext_list)
    if not scene_file:
        _exit_with(
            f"Error: scene file not found in {scene_dir}\n  Tried extensions: {ext_list}"
        )

    fps = args_fps if args_fps is not None else manifest.get("fps", 30)
    duration = args_duration if args_duration is not None else manifest.get("duration", 3)
    resolution = manifest.get("resolution", [1920, 1080])
    width = args_width if args_width is not None else resolution[0]
    height = args_height if args_height is not None else resolution[1]

    output_dir = os.path.join(".agent", "tmp", scene_name)
    frames_dir = os.path.join(output_dir, "frames")
    os.makedirs(frames_dir, exist_ok=True)

    log_dir = os.path.join(".agent", "log")
    os.makedirs(log_dir, exist_ok=True)
    import datetime

    log_file = os.path.join(
        log_dir, f"{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}_{scene_name}.log"
    )

    _run_validate_manifest(manifest_path)
    _run_api_gate(scene_file, engine, log_file)

    if not skip_dry_run:
        _run_dry_run(scene_file, engine)

    check_reports_dir = os.path.join(".agent", "check_reports")
    os.makedirs(check_reports_dir, exist_ok=True)

    if not skip_checks:
        _run_static_checks(
            scene_file=scene_file,
            scene_name=scene_name,
            manifest=manifest,
            check_reports_dir=check_reports_dir,
        )

    return RenderContext(
        scene_dir=scene_dir,
        scene_name=scene_name,
        scene_file=scene_file,
        manifest=manifest,
        engine=engine,
        engine_conf=engine_conf,
        ext_list=ext_list,
        engine_mode=engine_mode,
        render_script_rel=render_script_rel,
        unified_mc_render=unified_mc_render,
        fps=fps,
        duration=duration,
        width=width,
        height=height,
        output_dir=output_dir,
        frames_dir=frames_dir,
        log_file=log_file,
        skip_checks=skip_checks,
    )
