"""engines/manimgl/src/components/narrative_scene.py
NarrativeScene — Template-driven stage orchestration for ManimGL.

Extends :class:`ZoneScene` with narrative-profile aware ``stage()``
scheduling.  Validates stage order (``requires``, ``must_be_first``),
auto-places mobjects into the correct zone, and auto-selects animation
primitives based on stage type.

Usage::

    from components.narrative_scene import NarrativeScene

    class MyScene(NarrativeScene):
        LAYOUT_PROFILE = "lecture_3zones"
        NARRATIVE_PROFILE = "definition_reveal"

        def construct(self):
            self.stage("statement", Text("极限的定义"))
            self.stage("visual", NumberLine(x_range=[-5, 5]))
            self.stage("annotation", MathTex(r"\\lim_{x\\to a} f(x) = L"))
            self.stage("example", Circle())
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from components.zoned_scene import ZoneScene
from manimlib import *
from utils.narrative_validator import (
    NarrativeProfileError,
    PrimaryZoneVisualTimeoutError,
    get_stage_def,
    validate_primary_zone_visual_timing,
    validate_stage_order,
)


class NarrativeScene(ZoneScene):
    """Scene base class with declarative narrative-driven staging.

    Subclasses override :attr:`NARRATIVE_PROFILE` to select a narrative
    template from ``engines/manimgl/src/templates/narratives/``.
    """

    NARRATIVE_PROFILE: str = "definition_reveal"

    # Animation primitives — subclasses may override for stylistic tweaks.
    CREATION_ANIM = ShowCreation
    FADEIN_ANIM = FadeIn
    WRITE_ANIM = Write

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._narrative: dict[str, Any] = {}
        self._stages_played: set[str] = set()
        self._stage_start_times: dict[str, float] = {}
        self._narrative_time_origin: float = 0.0

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------
    def setup(self):
        """Load layout profile (via ZoneScene) and narrative profile."""
        super().setup()
        self._load_narrative(self.NARRATIVE_PROFILE)
        self._narrative_time_origin = getattr(self, "time", 0.0) or 0.0

    def _load_narrative(self, profile: str) -> None:
        """Load a JSON narrative profile from *templates/narratives/*."""
        narratives_dir = Path(__file__).parent.parent / "templates" / "narratives"
        path = narratives_dir / f"{profile}.json"
        if not path.exists():
            available = (
                [p.stem for p in narratives_dir.glob("*.json")]
                if narratives_dir.exists()
                else []
            )
            raise NarrativeProfileError(
                f"Narrative profile '{profile}.json' not found in {narratives_dir}. "
                f"Available: {available}"
            )

        with open(path, encoding="utf-8") as f:
            data = json.load(f)

        if "stages" not in data:
            raise NarrativeProfileError(
                f"Narrative profile '{profile}' missing required field 'stages'."
            )

        self._narrative = data

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def stage(
        self,
        stage_id: str,
        *mobjects: Mobject,
        run_time: float | None = None,
    ) -> list[Mobject]:
        """Play a narrative stage: validate, place, animate, record.

        Args:
            stage_id: Key in the narrative's ``stages`` list.
            mobjects: One or more mobjects to place and animate.
            run_time: Override animation duration (seconds).  If ``None``,
                the stage's ``duration_hint`` is used.

        Returns:
            List of placed mobjects.

        Raises:
            StageNotFoundError: If *stage_id* is unknown.
            StageOrderError: If ``must_be_first`` or ``requires`` violated.
            PrimaryZoneVisualTimeoutError: If primary zone visual arrives
                too late per narrative rules.
        """
        stages = self._narrative.get("stages", [])
        stage_def = get_stage_def(stages, stage_id)

        # 1. Order validation
        validate_stage_order(stages, stage_id, self._stages_played)

        # 2. Placement
        zone_name = stage_def["zone"]
        for mobj in mobjects:
            self.place(mobj, zone_name)

        # 3. Animation selection
        anims = self._build_animations(mobjects, stage_def.get("type", "visual"))

        # 4. Duration
        if run_time is None:
            run_time = stage_def.get("duration_hint", 1.0)

        # 5. Primary zone visual timing check (before play, "appears" = called)
        elapsed_before = (getattr(self, "time", 0.0) or 0.0) - self._narrative_time_origin
        timeout = self._narrative.get("rules", {}).get("primary_zone_first_visual_within")
        if timeout is not None:
            # Temporarily add to played so validator sees this as the first visual
            self._stages_played.add(stage_id)
            try:
                validate_primary_zone_visual_timing(
                    stages,
                    self._zones,
                    self._stages_played,
                    stage_id,
                    elapsed_before,
                    timeout,
                )
            except PrimaryZoneVisualTimeoutError:
                # Roll back if validation fails so the scene can catch it
                self._stages_played.discard(stage_id)
                raise

        # 6. Play
        if anims:
            self.play(*anims, run_time=run_time)
        else:
            self.wait(run_time)

        # 7. Record
        self._stages_played.add(stage_id)
        elapsed = (getattr(self, "time", 0.0) or 0.0) - self._narrative_time_origin
        self._stage_start_times[stage_id] = elapsed

        return list(mobjects)

    def play_stage(
        self,
        stage_id: str,
        *extra_anims,
        run_time: float | None = None,
    ) -> None:
        """Replay or extend a stage with additional animations.

        This is a lower-level hook for cases where ``stage()``'s default
        animation choice is insufficient.  The caller is responsible for
        having already placed mobjects (via ``place()``).

        Args:
            stage_id: Narrative stage being played (for duration lookup).
            extra_anims: Additional animations to play.
            run_time: Override duration; falls back to stage ``duration_hint``.
        """
        stages = self._narrative.get("stages", [])
        stage_def = get_stage_def(stages, stage_id)

        if run_time is None:
            run_time = stage_def.get("duration_hint", 1.0)

        if extra_anims:
            self.play(*extra_anims, run_time=run_time)
        else:
            self.wait(run_time)

        self._stages_played.add(stage_id)
        elapsed = (getattr(self, "time", 0.0) or 0.0) - self._narrative_time_origin
        self._stage_start_times[stage_id] = elapsed

    def narrative_summary(self) -> dict[str, Any]:
        """Return a snapshot of played stages and timing for diagnostics."""
        return {
            "profile": self.NARRATIVE_PROFILE,
            "played": sorted(self._stages_played),
            "stage_times": self._stage_start_times,
            "total_elapsed": (
                getattr(self, "time", 0.0) or 0.0
            ) - self._narrative_time_origin,
        }

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    def _build_animations(
        self,
        mobjects: tuple[Mobject, ...],
        stage_type: str,
    ) -> list[Any]:
        """Select animation primitives based on stage type."""
        if not mobjects:
            return []

        if stage_type == "text":
            return [self.WRITE_ANIM(mobj) for mobj in mobjects]
        elif stage_type == "visual":
            return [self.CREATION_ANIM(mobj) for mobj in mobjects]
        else:
            # Default: fade everything in
            return [self.FADEIN_ANIM(mobj) for mobj in mobjects]
