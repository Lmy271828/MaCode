"""Unit tests for pipeline._render.encode (S7-CLEAN-1)."""

from __future__ import annotations

import os
import sys

import pytest

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if REPO not in sys.path:
    sys.path.insert(0, REPO)

from pipeline._render import encode  # noqa: E402
from pipeline._render.validate import RenderContext  # noqa: E402


def _ctx(tmp_path, *, mode="batch"):
    output_dir = tmp_path / "out"
    frames_dir = output_dir / "frames"
    frames_dir.mkdir(parents=True)
    log = tmp_path / "render.log"
    log.touch()
    return RenderContext(
        scene_dir=str(tmp_path / "scene"),
        scene_name="s",
        scene_file=str(tmp_path / "scene.py"),
        manifest={},
        engine="manim",
        engine_conf={"scene_extensions": [".py"], "mode": mode},
        ext_list=[".py"],
        engine_mode=mode,
        render_script_rel="",
        unified_mc_render=False,
        fps=30,
        duration=1.0,
        width=1920,
        height=1080,
        output_dir=str(output_dir),
        frames_dir=str(frames_dir),
        log_file=str(log),
    )


def test_fuse_blocks_when_too_many_frames(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    ctx = _ctx(tmp_path)
    # Fake many frames by lowering fuse, since creating 10001 files is slow
    monkeypatch.setattr(encode, "FUSE_MAX_FRAMES", 2)
    for i in range(3):
        open(os.path.join(ctx.frames_dir, f"frame_{i:04d}.png"), "w").close()
    with pytest.raises(SystemExit) as ei:
        encode._check_fuses(ctx)
    assert ei.value.code == 1
    assert "FUSE" in capsys.readouterr().err


def test_fuse_skipped_for_interactive_engine(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    ctx = _ctx(tmp_path, mode="interactive")
    # Even with no frames, interactive mode should return 0 (no fuse check)
    assert encode._check_fuses(ctx) == 0


def test_run_interactive_skips_concat_and_creates_final_mp4(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    ctx = _ctx(tmp_path, mode="interactive")
    # raw.mp4 missing → final.mp4 should be created as empty file
    monkeypatch.setattr(encode, "_layer2_check", lambda c: None)
    monkeypatch.setattr(encode, "_populate_cache", lambda c: None)
    monkeypatch.setattr(encode, "_deliver", lambda c: None)
    result = encode.run(ctx, cache_hit=False)
    assert os.path.isfile(result.final_mp4)


def test_run_batch_concat_failure_exits(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    ctx = _ctx(tmp_path, mode="batch")
    # Frame fuse OK
    open(os.path.join(ctx.frames_dir, "frame_0001.png"), "w").close()

    monkeypatch.setattr(encode, "_layer2_check", lambda c: None)

    import subprocess

    def fake_run(cmd, *a, **kw):
        if isinstance(cmd, list) and len(cmd) > 1 and "concat.sh" in str(cmd[1]):
            class R:
                returncode = 1

            return R()

        class R:
            returncode = 0
            stdout = "0\t.agent/tmp"

        return R()

    monkeypatch.setattr(subprocess, "run", fake_run)

    with pytest.raises(SystemExit) as ei:
        encode.run(ctx, cache_hit=False)
    assert ei.value.code == 1
