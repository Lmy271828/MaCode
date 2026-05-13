"""Unit tests for pipeline._render.engine (S7-CLEAN-1)."""

from __future__ import annotations

import os
import sys

import pytest

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if REPO not in sys.path:
    sys.path.insert(0, REPO)

from pipeline._render import engine  # noqa: E402
from pipeline._render.validate import RenderContext  # noqa: E402


def _ctx(tmp_path, *, engine_name="manim", unified_mc=False, mode="batch"):
    return RenderContext(
        scene_dir=str(tmp_path / "scene"),
        scene_name="s",
        scene_file=str(tmp_path / "scene.py"),
        manifest={},
        engine=engine_name,
        engine_conf={
            "scene_extensions": [".py"],
            "mode": mode,
            "render_script": "engines/manim/scripts/render.sh",
        },
        ext_list=[".py"],
        engine_mode=mode,
        render_script_rel="engines/manim/scripts/render.sh",
        unified_mc_render=unified_mc,
        fps=30,
        duration=1.0,
        width=1920,
        height=1080,
        output_dir=str(tmp_path / "out"),
        frames_dir=str(tmp_path / "out" / "frames"),
        log_file=str(tmp_path / "render.log"),
    )


def test_cache_hit_short_circuits_engine(tmp_path, monkeypatch):
    """When cache.sh exits 0, engine.run must skip pre-render + service + invoke."""
    monkeypatch.chdir(tmp_path)
    ctx = _ctx(tmp_path)
    os.makedirs(ctx.output_dir, exist_ok=True)
    open(ctx.log_file, "a").close()

    # Make _resolve_engine_script return a fake path (file existence not required
    # because engine should never be invoked on cache hit).
    monkeypatch.setattr(engine, "_resolve_engine_script", lambda c: "/fake")

    import subprocess

    invocations: list[list[str]] = []

    def fake_run(cmd, *a, **kw):
        invocations.append(list(cmd))

        class R:
            returncode = 0
            stdout = ""
            stderr = ""

        return R()

    monkeypatch.setattr(subprocess, "run", fake_run)
    # Force cache hit
    monkeypatch.setattr(engine, "_check_cache", lambda c: True)

    result = engine.run(ctx)
    assert result.cache_hit is True
    assert result.service_was_started is False
    # No engine call was issued
    invoked_node_or_bash = any(
        ("/fake" in c) or ("macode-run" in " ".join(c)) for c in invocations
    )
    assert not invoked_node_or_bash


def test_engine_invocation_passes_scene_file_for_bash_engine(tmp_path, monkeypatch):
    """Non-cache-hit path: engine.run must call macode-run + the bash engine."""
    monkeypatch.chdir(tmp_path)
    ctx = _ctx(tmp_path)
    os.makedirs(ctx.output_dir, exist_ok=True)
    open(ctx.log_file, "a").close()

    monkeypatch.setattr(engine, "_resolve_engine_script", lambda c: "/fake/render.sh")
    monkeypatch.setattr(engine, "_check_cache", lambda c: False)
    monkeypatch.setattr(engine, "_run_pre_render", lambda c: None)
    monkeypatch.setattr(engine, "_start_service", lambda c: (None, None))

    invoked: list[list[str]] = []

    import subprocess

    def fake_run(cmd, *a, **kw):
        invoked.append(list(cmd))

        class R:
            returncode = 0

        return R()

    monkeypatch.setattr(subprocess, "run", fake_run)

    result = engine.run(ctx)
    assert result.cache_hit is False
    # Last call must contain "macode-run" and the engine.sh path + scene file
    last = invoked[-1]
    assert any("macode-run" in str(p) for p in last)
    assert "bash" in last
    assert "/fake/render.sh" in last
    assert ctx.scene_file in last


def test_engine_invocation_fails_loud_when_mjs_without_service_or_unified(
    tmp_path, monkeypatch, capsys
):
    monkeypatch.chdir(tmp_path)
    ctx = _ctx(tmp_path)
    os.makedirs(ctx.output_dir, exist_ok=True)
    open(ctx.log_file, "a").close()

    monkeypatch.setattr(engine, "_resolve_engine_script", lambda c: "/fake/render.mjs")
    monkeypatch.setattr(engine, "_check_cache", lambda c: False)
    monkeypatch.setattr(engine, "_run_pre_render", lambda c: None)
    monkeypatch.setattr(engine, "_start_service", lambda c: (None, None))

    with pytest.raises(SystemExit) as ei:
        engine.run(ctx)
    assert ei.value.code == 1
    err = capsys.readouterr().err
    assert "unified render.mjs or a running service URL" in err
