"""Shared filesystem state + progress writers for MaCode orchestration."""

from __future__ import annotations

import json
import os
from datetime import UTC, datetime
from typing import Any, NotRequired, TypedDict

ORCHESTRATION_VERSION = "1.1"

_ORCH_STATUSES = frozenset({"running", "completed", "failed", "timeout"})


class OrchestrationStateV11(TypedDict):
    """Orchestration ``state.json`` written by ``write_state`` (version 1.1)."""

    version: str
    taskId: str
    status: str
    exitCode: int
    startedAt: NotRequired[str]
    endedAt: NotRequired[str]
    outputs: NotRequired[dict[str, Any]]
    error: NotRequired[str]


def _iso_utc_z() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def _iso_utc_iso() -> str:
    return datetime.now(UTC).isoformat()


def atomic_write_json(path: str, data: dict[str, Any]) -> None:
    """Atomic write JSON object to ``path`` (tmp + replace)."""
    tmp = path + ".tmp"
    os.makedirs(os.path.dirname(os.path.abspath(path)) or ".", exist_ok=True)
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
        f.write("\n")
    os.replace(tmp, path)


def read_state(scene_name: str) -> dict[str, Any] | None:
    path = os.path.join(".agent", "tmp", scene_name, "state.json")
    if not os.path.isfile(path):
        return None
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return None


def write_progress(
    scene_name: str,
    phase: str,
    status: str,
    *,
    message: str = "",
    extra: dict[str, Any] | None = None,
) -> None:
    """Append one JSON line to ``.agent/progress/{scene).jsonl``."""
    if not isinstance(phase, str) or not isinstance(status, str):
        raise TypeError("phase and status must be str")
    progress_dir = os.path.join(".agent", "progress")
    os.makedirs(progress_dir, exist_ok=True)
    progress_path = os.path.join(progress_dir, f"{scene_name}.jsonl")
    entry: dict[str, Any] = {
        "timestamp": _iso_utc_z(),
        "phase": phase,
        "status": status,
    }
    if extra:
        entry.update(extra)
    if message:
        entry["message"] = message
    with open(progress_path, "a", encoding="utf-8") as f:
        json.dump(entry, f, ensure_ascii=False)
        f.write("\n")


def write_progress_to_path(
    progress_path: str,
    phase: str,
    status: str,
    *,
    message: str = "",
    extra: dict[str, Any] | None = None,
) -> None:
    """Append one JSON line to ``progress_path`` (user-provided absolute or relative path).

    Parent directories are created if missing. Used by ``bin/progress-write.py`` CLI.
    Python callers writing to ``.agent/progress/{scene}.jsonl`` should use ``write_progress`` instead.
    """
    if not isinstance(phase, str) or not isinstance(status, str):
        raise TypeError("phase and status must be str")
    os.makedirs(os.path.dirname(progress_path) or ".", exist_ok=True)
    entry: dict[str, Any] = {
        "timestamp": _iso_utc_z(),
        "phase": phase,
        "status": status,
    }
    if extra:
        entry.update(extra)
    if message:
        entry["message"] = message
    with open(progress_path, "a", encoding="utf-8") as f:
        json.dump(entry, f, ensure_ascii=False)
        f.write("\n")


def _merge_outputs(
    existing: dict[str, Any] | None, new_outputs: dict[str, Any] | None
) -> dict[str, Any] | None:
    if existing is None:
        return new_outputs
    if new_outputs is None:
        return existing
    merged = dict(existing)
    merged.update(new_outputs)
    return merged


def _validate_orchestration(data: dict[str, Any]) -> None:
    ver = data.get("version")
    if ver != ORCHESTRATION_VERSION:
        raise ValueError(f"orchestration state version must be {ORCHESTRATION_VERSION!r}, got {ver!r}")
    if not isinstance(data.get("taskId"), str):
        raise TypeError("taskId must be str")
    st = data.get("status")
    if st not in _ORCH_STATUSES:
        raise ValueError(f"invalid status {st!r}")
    if not isinstance(data.get("exitCode"), int):
        raise TypeError("exitCode must be int")
    outs = data.get("outputs")
    if outs is not None and not isinstance(outs, dict):
        raise TypeError("outputs must be dict or omitted")
    err = data.get("error")
    if err is not None and not isinstance(err, str):
        raise TypeError("error must be str or omitted")
    for key in ("startedAt", "endedAt"):
        val = data.get(key)
        if val is not None and not isinstance(val, str):
            raise TypeError(f"{key} must be str or omitted")


def write_state(
    scene_name: str,
    status: str,
    *,
    exit_code: int = 0,
    outputs: dict[str, Any] | None = None,
    error: str | None = None,
    started_at: str | None = None,
    ended_at: str | None = None,
) -> None:
    """Write orchestration ``state.json`` under ``.agent/tmp/<scene_name>/`` (atomic)."""
    state_dir = os.path.join(".agent", "tmp", scene_name)
    os.makedirs(state_dir, exist_ok=True)
    state_path = os.path.join(state_dir, "state.json")
    ts = _iso_utc_iso()
    existing: dict[str, Any] = {}
    if os.path.isfile(state_path):
        try:
            with open(state_path, encoding="utf-8") as f:
                existing = json.load(f)
        except (json.JSONDecodeError, OSError):
            existing = {}

    data: dict[str, Any] = {
        "version": ORCHESTRATION_VERSION,
        "taskId": scene_name,
        "status": status,
        "exitCode": exit_code,
    }

    if status == "running":
        data["startedAt"] = started_at if started_at is not None else ts
    else:
        data["endedAt"] = ended_at if ended_at is not None else ts
        if existing.get("startedAt"):
            data["startedAt"] = existing["startedAt"]
        elif started_at is not None:
            data["startedAt"] = started_at

    merged_out = _merge_outputs(
        existing.get("outputs") if isinstance(existing.get("outputs"), dict) else None,
        outputs,
    )
    if merged_out:
        data["outputs"] = merged_out

    if error is not None:
        data["error"] = error
    elif status == "completed":
        data.pop("error", None)
    elif existing.get("error") and status == "running":
        data["error"] = existing["error"]

    _validate_orchestration(data)
    atomic_write_json(state_path, data)


# --- Task state v1.0 (``bin/state-write.py`` CLI / richer merges) -----------------

_TASK_VERSION = "1.0"


def load_existing_state_file(state_path: str) -> dict[str, Any]:
    if os.path.exists(state_path):
        try:
            with open(state_path, encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError):
            pass
    return {}


def _compute_duration_sec(started_at: str | None, ended_at: str | None) -> float | None:
    if not started_at or not ended_at:
        return None
    try:
        fmt = "%Y-%m-%dT%H:%M:%SZ"
        s = started_at.replace("+00:00", "Z")
        e = ended_at.replace("+00:00", "Z")
        if not s.endswith("Z"):
            s = s[:19] + "Z"
        if not e.endswith("Z"):
            e = e[:19] + "Z"
        ds = datetime.strptime(s, fmt)
        de = datetime.strptime(e, fmt)
        return (de - ds).total_seconds()
    except (ValueError, TypeError):
        return None


def write_task_state_v1_from_cli(
    state_dir: str,
    status: str,
    exit_code: int | None,
    *,
    tool: str = "",
    outputs: dict[str, Any] | None = None,
    error: str = "",
    started_at: str = "",
    ended_at: str = "",
    duration: float | None = None,
    task_id: str = "",
) -> None:
    """Full MaCode Task State v1.0 merge+write (used by ``state-write.py``)."""
    os.makedirs(state_dir, exist_ok=True)
    state_path = os.path.join(state_dir, "state.json")
    existing = load_existing_state_file(state_path)

    is_terminal = status in ("completed", "failed", "timeout")

    started = started_at or existing.get("startedAt")
    if status == "running" and not started:
        started = _iso_utc_z()

    ended = ended_at or existing.get("endedAt")
    if is_terminal and not ended:
        ended = _iso_utc_z()

    dur = duration
    if dur is None and is_terminal:
        dur = _compute_duration_sec(
            str(started) if started else None, str(ended) if ended else None
        )
        if dur is None:
            d0 = existing.get("durationSec")
            dur = float(d0) if isinstance(d0, (int, float)) else None

    state: dict[str, Any] = {
        "version": _TASK_VERSION,
        "tool": tool or existing.get("tool", "unknown"),
        "status": status,
    }

    if task_id or existing.get("taskId"):
        state["taskId"] = task_id or existing.get("taskId")

    if exit_code is not None:
        state["exitCode"] = exit_code
    elif "exitCode" in existing:
        state["exitCode"] = existing["exitCode"]

    if started:
        state["startedAt"] = started
    if ended:
        state["endedAt"] = ended
    if dur is not None:
        state["durationSec"] = dur

    merged_outputs = _merge_outputs(
        existing.get("outputs") if isinstance(existing.get("outputs"), dict) else None,
        outputs,
    )
    if merged_outputs:
        state["outputs"] = merged_outputs

    if error:
        state["error"] = error
    elif existing.get("error") and not is_terminal:
        state["error"] = existing["error"]
    if is_terminal and status == "completed":
        state.pop("error", None)

    atomic_write_json(state_path, state)
