"""Tests for bin/macode_state."""

from __future__ import annotations

import json
import os
import sys

import pytest

REPO = os.path.join(os.path.dirname(__file__), "..", "..")
BIN = os.path.join(REPO, "bin")
if BIN not in sys.path:
    sys.path.insert(0, BIN)

from macode_state import (  # noqa: E402
    ORCHESTRATION_VERSION,
    OrchestrationStateV11,
    atomic_write_json,
    read_state,
    write_progress,
    write_state,
    write_state_to_path,
)


def test_write_state_atomic_and_merge_outputs(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    write_state("s1", "running")
    write_state("s1", "completed", exit_code=0, outputs={"a": 1})
    write_state("s1", "completed", exit_code=0, outputs={"b": 2})
    st = read_state("s1")
    assert st is not None
    assert st["version"] == ORCHESTRATION_VERSION
    assert st["status"] == "completed"
    assert st["exitCode"] == 0
    assert st["outputs"] == {"a": 1, "b": 2}
    assert "startedAt" in st


def test_read_state_corrupt_returns_none(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    d = tmp_path / ".agent" / "tmp" / "bad"
    d.mkdir(parents=True)
    p = d / "state.json"
    p.write_text("not-json{{{", encoding="utf-8")
    assert read_state("bad") is None


def test_write_state_after_corrupt_json_starts_fresh(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    d = tmp_path / ".agent" / "tmp" / "x"
    d.mkdir(parents=True)
    (d / "state.json").write_text("NOTJSON", encoding="utf-8")
    write_state("x", "running")
    st = read_state("x")
    assert st and st["status"] == "running"


def test_progress_line_shape_and_message(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    write_progress("sc", "capture", "running", message="hi", extra={"fps": 30})
    p = tmp_path / ".agent" / "progress" / "sc.jsonl"
    line = p.read_text(encoding="utf-8").strip()
    row = json.loads(line)
    assert row["phase"] == "capture"
    assert row["status"] == "running"
    assert row["message"] == "hi"
    assert row["fps"] == 30
    assert row["timestamp"].endswith("Z")


def test_schema_validation_bad_status():
    with pytest.raises(ValueError):
        write_state("z", "nope", exit_code=0)


def test_orchestration_typeddict_runtime_check():
    sample: OrchestrationStateV11 = {
        "version": ORCHESTRATION_VERSION,
        "taskId": "t",
        "status": "running",
        "exitCode": 0,
        "startedAt": "2026-01-01T00:00:00Z",
    }
    assert sample["taskId"] == "t"


def test_atomic_write_json_creates_parent_dirs(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    path = str(tmp_path / "nested" / "state.json")
    atomic_write_json(path, {"a": 1})
    assert json.loads((tmp_path / "nested" / "state.json").read_text()) == {"a": 1}


def test_write_state_to_path_preserves_extended_fields(tmp_path, monkeypatch):
    """Extended fields (cmd, pid, tool, durationSec) should be preserved across writes."""
    monkeypatch.chdir(tmp_path)
    sd = str(tmp_path / ".agent" / "tmp" / "job")
    sp = os.path.join(sd, "state.json")
    os.makedirs(sd, exist_ok=True)

    write_state_to_path(sp, "job", "running", cmd=["bash", "render.sh"], tool="render.sh")
    write_state_to_path(sp, "job", "running", pid=12345)
    write_state_to_path(sp, "job", "completed", exit_code=0, outputs={"frames": 90}, duration_sec=5.0)

    with open(sp, encoding="utf-8") as f:
        data = json.load(f)

    assert data["version"] == ORCHESTRATION_VERSION
    assert data["cmd"] == ["bash", "render.sh"]
    assert data["pid"] == 12345
    assert data["tool"] == "render.sh"
    assert data["durationSec"] == 5.0
    assert data["outputs"]["frames"] == 90


def test_write_state_extended_fields_round_trip(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    write_state("s2", "running", cmd=["node", "render.mjs"], tool="mc")
    write_state("s2", "completed", exit_code=0, duration_sec=3.5)
    st = read_state("s2")
    assert st is not None
    assert st["cmd"] == ["node", "render.mjs"]
    assert st["tool"] == "mc"
    assert st["durationSec"] == 3.5
