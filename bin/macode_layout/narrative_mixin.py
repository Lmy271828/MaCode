"""Shared NarrativeScene behaviour (template load + stage orchestration)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from macode_layout.narrative_validator import (
    NarrativeProfileError,
    PrimaryZoneVisualTimeoutError,
    get_stage_def,
    validate_primary_zone_visual_timing,
    validate_stage_order,
)


class NarrativeSceneMixin:
    """Expects mixin host to be a ZoneLayoutMixin-backed scene with ``play``, ``wait``, ``place``."""

    _narrative: dict[str, Any]
    _stages_played: set[str]
    _stage_start_times: dict[str, float]
    _narrative_time_origin: float

    CREATION_ANIM: Any
    FADEIN_ANIM: Any
    WRITE_ANIM: Any

    def _macode_narratives_dir(self) -> Path:
        raise NotImplementedError

    def setup(self):  # type: ignore[no-untyped-def]
        super().setup()
        self._narr_load(self.NARRATIVE_PROFILE)
        self._narrative_time_origin = getattr(self, "time", 0.0) or 0.0

    def _narr_load(self, profile: str) -> None:
        narratives_dir = self._macode_narratives_dir()
        path = narratives_dir / f"{profile}.json"
        if not path.exists():
            available = (
                [p.stem for p in narratives_dir.glob("*.json")] if narratives_dir.exists() else []
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

    def stage(
        self,
        stage_id: str,
        *mobjects: Any,
        run_time: float | None = None,
    ) -> list[Any]:
        stages = self._narrative.get("stages", [])
        stage_def = get_stage_def(stages, stage_id)

        validate_stage_order(stages, stage_id, self._stages_played)

        zone_name = stage_def["zone"]
        for mobj in mobjects:
            self.place(mobj, zone_name)

        anims = self._build_animations(mobjects, stage_def.get("type", "visual"))

        if run_time is None:
            run_time = stage_def.get("duration_hint", 1.0)

        elapsed_before = (getattr(self, "time", 0.0) or 0.0) - self._narrative_time_origin
        timeout = self._narrative.get("rules", {}).get("primary_zone_first_visual_within")
        if timeout is not None:
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
                self._stages_played.discard(stage_id)
                raise

        if anims:
            self.play(*anims, run_time=run_time)
        else:
            self.wait(run_time)

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
        return {
            "profile": self.NARRATIVE_PROFILE,
            "played": sorted(self._stages_played),
            "stage_times": self._stage_start_times,
            "total_elapsed": (getattr(self, "time", 0.0) or 0.0) - self._narrative_time_origin,
        }

    def _build_animations(
        self,
        mobjects: tuple[Any, ...],
        stage_type: str,
    ) -> list[Any]:
        if not mobjects:
            return []

        if stage_type == "text":
            return [self.WRITE_ANIM(mobj) for mobj in mobjects]
        if stage_type == "visual":
            return [self.CREATION_ANIM(mobj) for mobj in mobjects]
        return [self.FADEIN_ANIM(mobj) for mobj in mobjects]
