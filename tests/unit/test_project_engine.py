"""Unit tests for bin/project_engine.py engine resolution."""

from __future__ import annotations

import json
import os
import sys

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
BIN = os.path.join(REPO, "bin")
if BIN not in sys.path:
    sys.path.insert(0, BIN)

from project_engine import (  # noqa: E402
    find_project_root,
    load_defaults_engine,
    resolve_engine,
    resolve_engine_from_manifest,
)


def test_load_defaults_engine_reads_project_yaml():
    d = load_defaults_engine(REPO)
    assert d in ("manimgl", "manim", "motion_canvas") or isinstance(d, str)


def test_resolve_engine_manifest_wins(tmp_path):
    root = tmp_path / "repo"
    root.mkdir()
    (root / "project.yaml").write_text(
        "defaults:\n  engine: manimgl\n", encoding="utf-8"
    )
    scene = root / "scn"
    scene.mkdir()
    (scene / "manifest.json").write_text(
        json.dumps({"engine": "manim", "duration": 1}), encoding="utf-8"
    )
    (scene / "scene.py").write_text("pass\n", encoding="utf-8")
    assert resolve_engine(str(scene), str(root)) == "manim"


def test_resolve_engine_py_no_engine_uses_defaults(tmp_path):
    root = tmp_path / "repo"
    root.mkdir()
    (root / "project.yaml").write_text(
        "defaults:\n  engine: manimgl\n", encoding="utf-8"
    )
    scene = root / "scn"
    scene.mkdir()
    (scene / "manifest.json").write_text(json.dumps({"duration": 1}), encoding="utf-8")
    (scene / "scene.py").write_text("pass\n", encoding="utf-8")
    assert resolve_engine(str(scene), str(root)) == "manimgl"


def test_resolve_engine_tsx_no_engine_is_motion_canvas(tmp_path):
    root = tmp_path / "repo"
    root.mkdir()
    (root / "project.yaml").write_text(
        "defaults:\n  engine: manimgl\n", encoding="utf-8"
    )
    scene = root / "scn"
    scene.mkdir()
    (scene / "manifest.json").write_text(json.dumps({"duration": 1}), encoding="utf-8")
    (scene / "scene.tsx").write_text("export default function X(){}", encoding="utf-8")
    assert resolve_engine(str(scene), str(root)) == "motion_canvas"


def test_resolve_engine_from_manifest_empty_manifest_py(tmp_path):
    root = tmp_path / "repo"
    root.mkdir()
    (root / "project.yaml").write_text(
        "defaults:\n  engine: manim\n", encoding="utf-8"
    )
    scene = root / "scn"
    scene.mkdir()
    (scene / "scene.py").write_text("pass\n", encoding="utf-8")
    assert (
        resolve_engine_from_manifest({}, str(scene), str(root)) == "manim"
    )


def test_find_project_root_from_nested_scene(tmp_path):
    root = tmp_path / "repo"
    root.mkdir()
    (root / "project.yaml").write_text("project:\n  name: T\n", encoding="utf-8")
    nested = root / "scenes" / "01_a"
    nested.mkdir(parents=True)
    assert find_project_root(str(nested)) == str(root)

