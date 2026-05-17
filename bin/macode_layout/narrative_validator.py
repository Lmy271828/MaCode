"""Pure validation utilities for narrative template constraints."""

from __future__ import annotations

from typing import Any


class NarrativeError(Exception):
    """Base exception for narrative constraint violations."""

    pass


class NarrativeProfileError(NarrativeError):
    """Raised when a narrative profile is missing or malformed."""

    pass


class StageOrderError(NarrativeError):
    """Raised when a stage is played out of order (requires or must_be_first)."""

    pass


class PrimaryZoneVisualTimeoutError(NarrativeError):
    """Raised when the primary zone does not receive a visual within the allowed time."""

    pass


class StageNotFoundError(NarrativeError):
    """Raised when a referenced stage does not exist in the narrative profile."""

    pass


def get_stage_def(stages: list[dict[str, Any]], stage_id: str) -> dict[str, Any]:
    """Return the stage dictionary with matching *stage_id*."""
    for st in stages:
        if st.get("id") == stage_id:
            return st
    raise StageNotFoundError(
        f"Stage '{stage_id}' not found in narrative profile. "
        f"Available: {[s.get('id') for s in stages]}"
    )


def validate_stage_order(
    stages: list[dict[str, Any]],
    stage_id: str,
    played: set[str],
) -> None:
    """Enforce ``must_be_first`` and ``requires`` constraints."""
    st = get_stage_def(stages, stage_id)

    if st.get("must_be_first"):
        if played:
            raise StageOrderError(
                f"Stage '{stage_id}' must be first, but stages {sorted(played)} "
                f"have already been played."
            )

    reqs = st.get("requires", [])
    missing = [r for r in reqs if r not in played]
    if missing:
        raise StageOrderError(f"Stage '{stage_id}' requires stages {missing} to be played first.")


def validate_primary_zone_visual_timing(
    stages: list[dict[str, Any]],
    zones: dict[str, dict[str, Any]],
    played: set[str],
    stage_id: str,
    scene_elapsed: float,
    timeout: float,
) -> None:
    """Check that the primary zone receives its first visual within *timeout*."""
    if timeout is None or timeout <= 0:
        return

    primary_zone = None
    for name, meta in zones.items():
        if meta.get("importance") == "primary":
            primary_zone = name
            break

    if primary_zone is None:
        return

    st = get_stage_def(stages, stage_id)
    if st.get("type") != "visual" or st.get("zone") != primary_zone:
        return

    for pid in played:
        if pid == stage_id:
            continue
        pst = get_stage_def(stages, pid)
        if pst.get("type") == "visual" and pst.get("zone") == primary_zone:
            return

    if scene_elapsed > timeout:
        raise PrimaryZoneVisualTimeoutError(
            f"Primary zone '{primary_zone}' first visual appeared at {scene_elapsed:.2f}s, "
            f"exceeds limit of {timeout:.2f}s."
        )
