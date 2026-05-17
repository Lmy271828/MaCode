"""Shared filesystem state + progress writers for MaCode orchestration.

All state.json files are written in OrchestrationState v1.1 format.
This module replaces the previous dual-track v1.0/v1.1 split.
"""

from __future__ import annotations

import json
import os
from datetime import UTC, datetime
from typing import Any, NotRequired, TypedDict

ORCHESTRATION_VERSION = "1.1"

_ORCH_STATUSES = frozenset({"running", "completed", "failed", "timeout"})


class OrchestrationStateV11(TypedDict):
    """Orchestration ``state.json`` written by ``write_state`` / ``write_state_to_path`` (version 1.1)."""

    version: str
    taskId: str
    status: str
    exitCode: int
    startedAt: NotRequired[str]
    endedAt: NotRequired[str]
    outputs: NotRequired[dict[str, Any]]
    error: NotRequired[str]
    # Extended fields (formerly v1.0 Task State)
    cmd: NotRequired[list[str]]
    pid: NotRequired[int]
    durationSec: NotRequired[float]
    tool: NotRequired[str]


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


def load_existing_state_file(state_path: str) -> dict[str, Any]:
    """Read existing state.json if present and valid."""
    if os.path.exists(state_path):
        try:
            with open(state_path, encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError):
            pass
    return {}


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
        raise ValueError(
            f"orchestration state version must be {ORCHESTRATION_VERSION!r}, got {ver!r}"
        )
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
    # Extended fields (formerly v1.0)
    for key, expected_type in (
        ("cmd", list),
        ("pid", int),
        ("durationSec", (int, float)),
        ("tool", str),
    ):
        val = data.get(key)
        if val is not None and not isinstance(val, expected_type):
            raise TypeError(
                f"{key} must be {getattr(expected_type, '__name__', expected_type)} or omitted"
            )


def write_state_to_path(
    state_path: str,
    task_id: str,
    status: str,
    *,
    exit_code: int = 0,
    outputs: dict[str, Any] | None = None,
    error: str | None = None,
    started_at: str | None = None,
    ended_at: str | None = None,
    cmd: list[str] | None = None,
    pid: int | None = None,
    duration_sec: float | None = None,
    tool: str | None = None,
) -> None:
    """Write orchestration ``state.json`` to an arbitrary path (atomic, merge-aware)."""
    os.makedirs(os.path.dirname(os.path.abspath(state_path)) or ".", exist_ok=True)
    ts = _iso_utc_iso()
    existing = load_existing_state_file(state_path)

    data: dict[str, Any] = {
        "version": ORCHESTRATION_VERSION,
        "taskId": task_id,
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

    # Auto-compute durationSec if both timestamps are present and no explicit duration given
    if duration_sec is None and status != "running":
        started = data.get("startedAt") or existing.get("startedAt")
        ended = data.get("endedAt") or existing.get("endedAt")
        if started and ended:
            try:
                ds = datetime.fromisoformat(started.replace("Z", "+00:00"))
                de = datetime.fromisoformat(ended.replace("Z", "+00:00"))
                duration_sec = round((de - ds).total_seconds(), 2)
            except (ValueError, TypeError):
                pass

    # Preserve extended fields from existing if not explicitly overridden
    for key, val in (
        ("cmd", cmd),
        ("pid", pid),
        ("durationSec", duration_sec),
        ("tool", tool),
    ):
        if val is not None:
            data[key] = val
        elif existing.get(key) is not None:
            data[key] = existing[key]

    _validate_orchestration(data)
    atomic_write_json(state_path, data)


def write_state(
    scene_name: str,
    status: str,
    *,
    exit_code: int = 0,
    outputs: dict[str, Any] | None = None,
    error: str | None = None,
    started_at: str | None = None,
    ended_at: str | None = None,
    cmd: list[str] | None = None,
    pid: int | None = None,
    duration_sec: float | None = None,
    tool: str | None = None,
) -> None:
    """Write orchestration ``state.json`` under ``.agent/tmp/<scene_name>/`` (atomic)."""
    state_dir = os.path.join(".agent", "tmp", scene_name)
    state_path = os.path.join(state_dir, "state.json")
    write_state_to_path(
        state_path,
        scene_name,
        status,
        exit_code=exit_code,
        outputs=outputs,
        error=error,
        started_at=started_at,
        ended_at=ended_at,
        cmd=cmd,
        pid=pid,
        duration_sec=duration_sec,
        tool=tool,
    )
