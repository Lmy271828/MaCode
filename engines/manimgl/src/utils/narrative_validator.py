"""engines/manimgl/src/utils/narrative_validator.py
Pure validation utilities for narrative template constraints.

No dependency on manimlib/manim — operates on plain Python types.
"""

from __future__ import annotations

from typing import Any

# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------


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


# ---------------------------------------------------------------------------
# Validation functions
# ---------------------------------------------------------------------------


def get_stage_def(stages: list[dict[str, Any]], stage_id: str) -> dict[str, Any]:
    """Return the stage dictionary with matching *stage_id*.

    Raises:
        StageNotFoundError: If no stage with *stage_id* exists.
    """
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
    """Enforce ``must_be_first`` and ``requires`` constraints.

    Args:
        stages: List of stage definitions from the narrative profile.
        stage_id: The stage about to be played.
        played: Set of stage IDs already played.

    Raises:
        StageNotFoundError: If *stage_id* is not in *stages*.
        StageOrderError: If order constraints are violated.
    """
    st = get_stage_def(stages, stage_id)

    # must_be_first
    if st.get("must_be_first"):
        if played:
            raise StageOrderError(
                f"Stage '{stage_id}' must be first, but stages {sorted(played)} "
                f"have already been played."
            )

    # requires
    reqs = st.get("requires", [])
    missing = [r for r in reqs if r not in played]
    if missing:
        raise StageOrderError(
            f"Stage '{stage_id}' requires stages {missing} to be played first."
        )


def validate_primary_zone_visual_timing(
    stages: list[dict[str, Any]],
    zones: dict[str, dict[str, Any]],
    played: set[str],
    stage_id: str,
    scene_elapsed: float,
    timeout: float,
) -> None:
    """Check that the primary zone receives its first visual within *timeout*.

    Args:
        stages: Stage definitions.
        zones: Layout zones dictionary.
        played: Set of already-played stage IDs.
        stage_id: The stage just played.
        scene_elapsed: Seconds elapsed since scene start.
        timeout: Maximum allowed seconds (from narrative rules).

    Raises:
        PrimaryZoneVisualTimeoutError: If the timeout is exceeded.
    """
    if timeout is None or timeout <= 0:
        return

    # Find primary zone name
    primary_zone = None
    for name, meta in zones.items():
        if meta.get("importance") == "primary":
            primary_zone = name
            break

    if primary_zone is None:
        return

    # Check if this stage is the first visual in the primary zone
    st = get_stage_def(stages, stage_id)
    if st.get("type") != "visual" or st.get("zone") != primary_zone:
        return

    # Check if any earlier played stage was also a visual in primary zone
    for pid in played:
        if pid == stage_id:
            continue
        pst = get_stage_def(stages, pid)
        if pst.get("type") == "visual" and pst.get("zone") == primary_zone:
            return  # not the first

    # This is the first visual in primary zone
    if scene_elapsed > timeout:
        raise PrimaryZoneVisualTimeoutError(
            f"Primary zone '{primary_zone}' first visual appeared at {scene_elapsed:.2f}s, "
            f"exceeds limit of {timeout:.2f}s."
        )
