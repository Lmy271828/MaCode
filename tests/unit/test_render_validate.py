"""Unit tests for pipeline._render.validate (S7-CLEAN-1)."""

from __future__ import annotations

import json
import os
import sys

import pytest

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if REPO not in sys.path:
    sys.path.insert(0, REPO)

from pipeline._render import validate  # noqa: E402


def _make_scene(tmp_path, *, engine="manim", with_scene_py=True):
    scene_dir = tmp_path / "01_test"
    scene_dir.mkdir()
    manifest = {
        "engine": engine,
        "fps": 30,
        "duration": 1,
        "resolution": [1920, 1080],
    }
    (scene_dir / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    if with_scene_py:
        (scene_dir / "scene.py").write_text(
            "from manim import Scene\nclass Foo(Scene):\n    def construct(self): pass\n",
            encoding="utf-8",
        )
    return scene_dir


def test_validate_scene_exits_when_manifest_missing(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    scene_dir = tmp_path / "missing"
    scene_dir.mkdir()
    with pytest.raises(SystemExit):
        validate.validate_scene(
            scene_dir=str(scene_dir),
            scene_name="missing",
            args_fps=None,
            args_duration=None,
            args_width=None,
            args_height=None,
            skip_checks=True,
        )
    err = capsys.readouterr().err
    assert "manifest.json not found" in err


def test_validate_scene_exits_on_unknown_engine(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    scene_dir = _make_scene(tmp_path, engine="totally_made_up")
    with pytest.raises(SystemExit):
        validate.validate_scene(
            scene_dir=str(scene_dir),
            scene_name="01_test",
            args_fps=None,
            args_duration=None,
            args_width=None,
            args_height=None,
            skip_checks=True,
        )
    err = capsys.readouterr().err
    assert "engine.conf not found" in err


def test_validate_scene_args_override_manifest(tmp_path, monkeypatch):
    """Mock subprocess calls so we can exercise the merge logic in isolation."""
    monkeypatch.chdir(tmp_path)
    scene_dir = _make_scene(tmp_path, engine="manim")

    # Patch out subprocess.run for inspect-conf.py + validate-manifest + api-gate
    import subprocess

    calls: list[list[str]] = []
    real_run = subprocess.run

    def fake_run(cmd, *a, **kw):
        calls.append(cmd)
        # inspect-conf
        if any("inspect-conf.py" in str(p) for p in cmd):

            class R:
                returncode = 0
                stdout = json.dumps(
                    {
                        "scene_extensions": [".py", ".tsx"],
                        "mode": "batch",
                        "render_script": "engines/manim/scripts/render.sh",
                    }
                )
                stderr = ""

            return R()
        # validate-manifest
        if any("validate-manifest.py" in str(p) for p in cmd):

            class R:
                returncode = 0
                stdout = ""
                stderr = ""

            return R()
        # api-gate / other: just return success without writing logs
        return real_run(cmd, *a, **kw)

    monkeypatch.setattr(subprocess, "run", fake_run)

    rctx = validate.validate_scene(
        scene_dir=str(scene_dir),
        scene_name="01_test",
        args_fps=12,
        args_duration=2.0,
        args_width=640,
        args_height=480,
        skip_checks=True,
    )
    assert rctx.fps == 12
    assert rctx.duration == 2.0
    assert rctx.width == 640
    assert rctx.height == 480
    assert rctx.engine == "manim"
    assert rctx.scene_file.endswith("scene.py")
    assert rctx.frames_dir.endswith(os.path.join("01_test", "frames"))


def test_validate_scene_falls_back_to_manifest_values(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    scene_dir = _make_scene(tmp_path, engine="manim")

    import subprocess

    def fake_run(cmd, *a, **kw):
        if any("inspect-conf.py" in str(p) for p in cmd):

            class R:
                returncode = 0
                stdout = json.dumps(
                    {
                        "scene_extensions": [".py", ".tsx"],
                        "mode": "batch",
                    }
                )
                stderr = ""

            return R()
        if any("validate-manifest.py" in str(p) for p in cmd):

            class R:
                returncode = 0
                stdout = ""
                stderr = ""

            return R()

        class R:
            returncode = 0
            stdout = ""
            stderr = ""

        return R()

    monkeypatch.setattr(subprocess, "run", fake_run)

    rctx = validate.validate_scene(
        scene_dir=str(scene_dir),
        scene_name="01_test",
        args_fps=None,
        args_duration=None,
        args_width=None,
        args_height=None,
        skip_checks=True,
    )
    assert rctx.fps == 30
    assert rctx.duration == 1
    assert rctx.width == 1920
    assert rctx.height == 1080


def test_validate_scene_exits_on_missing_engine_in_manifest(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    scene_dir = tmp_path / "01_test"
    scene_dir.mkdir()
    manifest = {"fps": 30, "duration": 1, "resolution": [1920, 1080]}
    (scene_dir / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    (scene_dir / "scene.py").write_text(
        "from manim import Scene\nclass Foo(Scene):\n    def construct(self): pass\n",
        encoding="utf-8",
    )
    with pytest.raises(SystemExit):
        validate.validate_scene(
            scene_dir=str(scene_dir),
            scene_name="01_test",
            args_fps=None,
            args_duration=None,
            args_width=None,
            args_height=None,
            skip_checks=True,
        )
    err = capsys.readouterr().err
    assert "engine" in err.lower() or "manifest" in err.lower()


def test_validate_scene_exits_on_missing_scene_file(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    scene_dir = tmp_path / "01_test"
    scene_dir.mkdir()
    manifest = {"engine": "manim", "fps": 30, "duration": 1, "resolution": [1920, 1080]}
    (scene_dir / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    # No scene.py
    with pytest.raises(SystemExit):
        validate.validate_scene(
            scene_dir=str(scene_dir),
            scene_name="01_test",
            args_fps=None,
            args_duration=None,
            args_width=None,
            args_height=None,
            skip_checks=True,
        )
    err = capsys.readouterr().err
    assert "scene file" in err.lower() or "not found" in err.lower()
