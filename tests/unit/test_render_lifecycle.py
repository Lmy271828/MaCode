"""Unit tests for pipeline._render.lifecycle (S7-CLEAN-1)."""

from __future__ import annotations

import json
import os
import sys

import pytest

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if REPO not in sys.path:
    sys.path.insert(0, REPO)

from pipeline._render import lifecycle  # noqa: E402


def test_prepare_lifecycle_paths(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    ctx = lifecycle.prepare_lifecycle("01_test", no_review=False)
    assert ctx.scene_name == "01_test"
    assert ctx.signals_dir.as_posix() == ".agent/signals"
    assert ctx.per_scene_dir.as_posix() == ".agent/signals/per-scene/01_test"
    assert ctx.override_path.name == "human_override.json"
    assert ctx.review_path.name == "review_needed"


def test_handle_override_approve(monkeypatch, tmp_path, capsys):
    monkeypatch.chdir(tmp_path)
    ctx = lifecycle.prepare_lifecycle("s", no_review=False)
    ctx.per_scene_dir.mkdir(parents=True)
    ctx.override_path.write_text(json.dumps({"action": "approve"}), encoding="utf-8")
    ctx.review_path.touch()
    with pytest.raises(SystemExit) as ei:
        lifecycle.handle_override_or_exit(ctx)
    assert ei.value.code == 0
    assert not ctx.override_path.exists()
    assert not ctx.review_path.exists()


def test_handle_override_retry_emits_json(monkeypatch, tmp_path, capsys):
    monkeypatch.chdir(tmp_path)
    ctx = lifecycle.prepare_lifecycle("s", no_review=False)
    ctx.per_scene_dir.mkdir(parents=True)
    ctx.override_path.write_text(
        json.dumps({"action": "retry", "instruction": "redo wait"}), encoding="utf-8"
    )
    with pytest.raises(SystemExit) as ei:
        lifecycle.handle_override_or_exit(ctx)
    assert ei.value.code == 2
    out = capsys.readouterr().out
    payload = json.loads(out.strip())
    assert payload["action"] == "retry"
    assert payload["instruction"] == "redo wait"


def test_handle_override_corrupt_file_clears(monkeypatch, tmp_path, capsys):
    monkeypatch.chdir(tmp_path)
    ctx = lifecycle.prepare_lifecycle("s", no_review=False)
    ctx.per_scene_dir.mkdir(parents=True)
    ctx.override_path.write_text("not-json{{", encoding="utf-8")
    # Should NOT raise SystemExit; should remove corrupt file
    lifecycle.handle_override_or_exit(ctx)
    assert not ctx.override_path.exists()


def test_check_review_pending_exits_3_when_set(monkeypatch, tmp_path, capsys):
    monkeypatch.chdir(tmp_path)
    ctx = lifecycle.prepare_lifecycle("s", no_review=False)
    ctx.per_scene_dir.mkdir(parents=True)
    ctx.review_path.touch()
    with pytest.raises(SystemExit) as ei:
        lifecycle.check_review_pending_or_exit(ctx)
    assert ei.value.code == 3


def test_check_review_pending_skipped_when_no_review(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    ctx = lifecycle.prepare_lifecycle("s", no_review=True)
    ctx.per_scene_dir.mkdir(parents=True)
    ctx.review_path.touch()
    # Should not exit
    lifecycle.check_review_pending_or_exit(ctx)


def test_mark_review_creates_marker(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    ctx = lifecycle.prepare_lifecycle("s", no_review=False)
    lifecycle.mark_review_if_needed(ctx)
    assert ctx.review_path.exists()


def test_mark_review_skipped_when_no_review(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    ctx = lifecycle.prepare_lifecycle("s", no_review=True)
    lifecycle.mark_review_if_needed(ctx)
    assert not ctx.review_path.exists()
