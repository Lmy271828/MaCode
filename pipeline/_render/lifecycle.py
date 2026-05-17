"""Lifecycle: human-override handling and progress writes.

Pure orchestration concerns that don't depend on a particular engine.
The orchestrator calls these in a fixed order:

    ctx = prepare_lifecycle(scene_name)
    handle_override_or_exit(ctx)           # may sys.exit(0/1/2)
    ...                                    # validate / engine / encode
"""

from __future__ import annotations

import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass
class LifecycleContext:
    scene_name: str
    signals_dir: Path
    per_scene_dir: Path
    override_path: Path


def prepare_lifecycle(scene_name: str) -> LifecycleContext:
    signals_dir = Path(".agent") / "signals"
    per_scene_dir = signals_dir / "per-scene" / scene_name
    return LifecycleContext(
        scene_name=scene_name,
        signals_dir=signals_dir,
        per_scene_dir=per_scene_dir,
        override_path=per_scene_dir / "human_override.json",
    )


def handle_override_or_exit(ctx: LifecycleContext) -> None:
    """If ``human_override.json`` exists, act on it and ``sys.exit`` accordingly.

    Exit codes:
      0  approve
      1  reject
      2  retry (with instruction; emits JSON to stdout)
    """
    if not ctx.override_path.exists():
        return

    try:
        override = json.loads(ctx.override_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        print(f"[review] Warning: corrupt override file: {exc}", file=sys.stderr)
        ctx.override_path.unlink(missing_ok=True)
        return

    action = override.get("action")
    if action == "approve":
        ctx.override_path.unlink(missing_ok=True)
        print(f"[review] '{ctx.scene_name}' approved.")
        sys.exit(0)
    if action == "reject":
        reason = override.get("reason", "")
        ctx.override_path.unlink(missing_ok=True)
        print(f"[review] '{ctx.scene_name}' rejected: {reason}", file=sys.stderr)
        sys.exit(1)
    if action == "retry":
        instruction = override.get("instruction", "")
        ctx.override_path.unlink(missing_ok=True)
        print(
            json.dumps(
                {
                    "status": "override_received",
                    "action": "retry",
                    "instruction": instruction,
                    "scene": ctx.scene_name,
                }
            )
        )
        sys.exit(2)


def progress(scene_name: str, phase: str, status: str, **extra: Any) -> None:
    """Thin wrapper around ``macode_state.write_progress`` to keep imports local."""
    from macode_state import write_progress  # late import to keep cycle-free

    message = extra.pop("message", "")
    write_progress(scene_name, phase, status, message=message, extra=extra or None)
