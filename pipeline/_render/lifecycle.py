"""Lifecycle: human-override handling, review markers, progress writes.

Pure orchestration concerns that don't depend on a particular engine.
The orchestrator calls these in a fixed order:

    ctx = prepare_lifecycle(scene_name, no_review=args.no_review)
    handle_override_or_exit(ctx)           # may sys.exit(0/1/2)
    check_review_pending_or_exit(ctx)      # may sys.exit(3)
    ...                                    # validate / engine / encode
    mark_review_if_needed(ctx)
"""

from __future__ import annotations

import json
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass
class LifecycleContext:
    scene_name: str
    no_review: bool
    signals_dir: Path
    per_scene_dir: Path
    override_path: Path
    review_path: Path


def prepare_lifecycle(scene_name: str, *, no_review: bool) -> LifecycleContext:
    signals_dir = Path(".agent") / "signals"
    per_scene_dir = signals_dir / "per-scene" / scene_name
    return LifecycleContext(
        scene_name=scene_name,
        no_review=no_review,
        signals_dir=signals_dir,
        per_scene_dir=per_scene_dir,
        override_path=per_scene_dir / "human_override.json",
        review_path=per_scene_dir / "review_needed",
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
        ctx.review_path.unlink(missing_ok=True)
        ctx.override_path.unlink(missing_ok=True)
        print(f"[review] '{ctx.scene_name}' approved.")
        sys.exit(0)
    if action == "reject":
        reason = override.get("reason", "")
        ctx.review_path.unlink(missing_ok=True)
        ctx.override_path.unlink(missing_ok=True)
        print(f"[review] '{ctx.scene_name}' rejected: {reason}", file=sys.stderr)
        sys.exit(1)
    if action == "retry":
        instruction = override.get("instruction", "")
        ctx.review_path.unlink(missing_ok=True)
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


def check_review_pending_or_exit(ctx: LifecycleContext) -> None:
    """If ``review_needed`` exists and ``--no-review`` not set, exit 3."""
    if ctx.review_path.exists() and not ctx.no_review:
        print(
            json.dumps(
                {
                    "status": "awaiting_review",
                    "scene": ctx.scene_name,
                    "message": (
                        f"Scene is awaiting human review. Run "
                        f"'macode review approve {ctx.scene_name}' or "
                        f"'macode review reject {ctx.scene_name}' to proceed."
                    ),
                }
            )
        )
        sys.exit(3)


def mark_review_if_needed(ctx: LifecycleContext) -> None:
    """Write ``review_needed`` marker unless ``--no-review`` was passed."""
    if ctx.no_review:
        return
    ctx.per_scene_dir.mkdir(parents=True, exist_ok=True)
    ctx.review_path.touch()
    print(f"[review] '{ctx.scene_name}' marked for review.")


def progress(scene_name: str, phase: str, status: str, **extra: Any) -> None:
    """Thin wrapper around ``macode_state.write_progress`` to keep imports local."""
    from macode_state import write_progress  # late import to keep cycle-free

    message = extra.pop("message", "")
    write_progress(scene_name, phase, status, message=message, extra=extra or None)
