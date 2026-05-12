"""tests/unit/test_narrative_scene.py
Unit tests for narrative template constraints and validation logic.

Tests the split modules directly:
- utils.narrative_validator  (pure constraint logic)
- engines/*/templates/narratives/*.json  (JSON schema)

No OpenGL display required.
"""

import json
import sys
import unittest
from pathlib import Path

# Inject engines/manimgl/src/ into path so we can import utils directly
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "engines" / "manimgl" / "src"))

from utils.narrative_validator import (
    PrimaryZoneVisualTimeoutError,
    StageNotFoundError,
    StageOrderError,
    get_stage_def,
    validate_primary_zone_visual_timing,
    validate_stage_order,
)

# ---------------------------------------------------------------------------
# JSON Schema Tests
# ---------------------------------------------------------------------------


class NarrativeJSONSchemaTests(unittest.TestCase):
    """Verify narrative template JSON files exist and are well-formed."""

    def setUp(self):
        self.narratives_dir = (
            Path(__file__).parent.parent.parent
            / "engines"
            / "manimgl"
            / "src"
            / "templates"
            / "narratives"
        )

    def _load(self, name):
        path = self.narratives_dir / f"{name}.json"
        with open(path, encoding="utf-8") as f:
            return json.load(f)

    def test_definition_reveal_exists(self):
        self.assertTrue((self.narratives_dir / "definition_reveal.json").exists())

    def test_build_up_payoff_exists(self):
        self.assertTrue((self.narratives_dir / "build_up_payoff.json").exists())

    def test_wrong_to_right_exists(self):
        self.assertTrue((self.narratives_dir / "wrong_to_right.json").exists())

    def test_all_have_required_top_level_fields(self):
        for name in ("definition_reveal", "build_up_payoff", "wrong_to_right"):
            with self.subTest(profile=name):
                data = self._load(name)
                self.assertIn("name", data)
                self.assertIn("description", data)
                self.assertIn("stages", data)
                self.assertIn("rules", data)
                self.assertIsInstance(data["stages"], list)
                self.assertIsInstance(data["rules"], dict)

    def test_all_stages_have_id_zone_type(self):
        for name in ("definition_reveal", "build_up_payoff", "wrong_to_right"):
            with self.subTest(profile=name):
                data = self._load(name)
                for st in data["stages"]:
                    self.assertIn("id", st)
                    self.assertIn("zone", st)
                    self.assertIn("type", st)
                    self.assertIn(st["type"], ("text", "visual"))

    def test_rules_contain_primary_zone_timeout(self):
        for name in ("definition_reveal", "build_up_payoff", "wrong_to_right"):
            with self.subTest(profile=name):
                data = self._load(name)
                self.assertIn("primary_zone_first_visual_within", data["rules"])
                timeout = data["rules"]["primary_zone_first_visual_within"]
                self.assertIsInstance(timeout, (int, float))
                self.assertGreater(data["rules"]["primary_zone_first_visual_within"], 0)

    def test_definition_reveal_stage_sequence(self):
        data = self._load("definition_reveal")
        ids = [s["id"] for s in data["stages"]]
        self.assertEqual(ids, ["statement", "visual", "annotation", "example"])

    def test_build_up_payoff_has_reflection(self):
        data = self._load("build_up_payoff")
        ids = [s["id"] for s in data["stages"]]
        self.assertIn("reflection", ids)
        self.assertIn("payoff", ids)

    def test_wrong_to_right_first_stage_is_must_be_first(self):
        data = self._load("wrong_to_right")
        first = data["stages"][0]
        self.assertTrue(first.get("must_be_first", False))


# ---------------------------------------------------------------------------
# get_stage_def Tests
# ---------------------------------------------------------------------------


class GetStageDefTests(unittest.TestCase):
    def test_found(self):
        stages = [{"id": "a"}, {"id": "b"}]
        result = get_stage_def(stages, "b")
        self.assertEqual(result["id"], "b")

    def test_not_found_raises(self):
        stages = [{"id": "a"}]
        with self.assertRaises(StageNotFoundError):
            get_stage_def(stages, "z")


# ---------------------------------------------------------------------------
# validate_stage_order Tests
# ---------------------------------------------------------------------------


class ValidateStageOrderTests(unittest.TestCase):
    def test_must_be_first_passes_when_empty(self):
        stages = [{"id": "intro", "must_be_first": True}]
        validate_stage_order(stages, "intro", set())  # should not raise

    def test_must_be_first_fails_when_not_empty(self):
        stages = [{"id": "intro", "must_be_first": True}]
        with self.assertRaises(StageOrderError):
            validate_stage_order(stages, "intro", {"other"})

    def test_requires_satisfied(self):
        stages = [
            {"id": "a"},
            {"id": "b", "requires": ["a"]},
        ]
        validate_stage_order(stages, "b", {"a"})

    def test_requires_missing(self):
        stages = [
            {"id": "a"},
            {"id": "b", "requires": ["a"]},
        ]
        with self.assertRaises(StageOrderError):
            validate_stage_order(stages, "b", set())

    def test_multiple_requires_all_needed(self):
        stages = [
            {"id": "a"},
            {"id": "b"},
            {"id": "c", "requires": ["a", "b"]},
        ]
        with self.assertRaises(StageOrderError):
            validate_stage_order(stages, "c", {"a"})
        validate_stage_order(stages, "c", {"a", "b"})  # should pass

    def test_no_requires_always_passes(self):
        stages = [{"id": "x"}]
        validate_stage_order(stages, "x", {"anything"})


# ---------------------------------------------------------------------------
# validate_primary_zone_visual_timing Tests
# ---------------------------------------------------------------------------


class ValidatePrimaryZoneVisualTimingTests(unittest.TestCase):
    def setUp(self):
        self.stages = [
            {"id": "statement", "zone": "title", "type": "text"},
            {"id": "visual", "zone": "main_visual", "type": "visual"},
            {"id": "annotation", "zone": "annotation", "type": "text"},
        ]
        self.zones = {
            "title": {"importance": "context"},
            "main_visual": {"importance": "primary"},
            "annotation": {"importance": "secondary"},
        }

    def test_within_timeout_passes(self):
        validate_primary_zone_visual_timing(
            self.stages, self.zones, {"statement"}, "visual", scene_elapsed=1.0, timeout=1.5
        )

    def test_exceeds_timeout_raises(self):
        with self.assertRaises(PrimaryZoneVisualTimeoutError):
            validate_primary_zone_visual_timing(
                self.stages, self.zones, {"statement"}, "visual", scene_elapsed=2.0, timeout=1.5
            )

    def test_non_visual_stage_ignored(self):
        # text stage in primary zone should not trigger the check
        # (even though in reality text shouldn't be in primary,
        #  the function should simply not raise for non-visual)
        stages = [{"id": "bad", "zone": "main_visual", "type": "text"}]
        validate_primary_zone_visual_timing(
            stages, self.zones, set(), "bad", scene_elapsed=99.0, timeout=1.5
        )

    def test_non_primary_zone_ignored(self):
        validate_primary_zone_visual_timing(
            self.stages, self.zones, set(), "annotation", scene_elapsed=99.0, timeout=1.5
        )

    def test_second_visual_ignored(self):
        # If a prior visual in primary zone already played, current one is not "first"
        stages = [
            {"id": "first", "zone": "main_visual", "type": "visual"},
            {"id": "second", "zone": "main_visual", "type": "visual"},
        ]
        validate_primary_zone_visual_timing(
            stages, self.zones, {"first"}, "second", scene_elapsed=99.0, timeout=1.5
        )

    def test_no_primary_zone_always_passes(self):
        zones = {"title": {"importance": "context"}}
        validate_primary_zone_visual_timing(
            self.stages, zones, set(), "visual", scene_elapsed=99.0, timeout=1.5
        )

    def test_zero_or_none_timeout_always_passes(self):
        validate_primary_zone_visual_timing(
            self.stages, self.zones, set(), "visual", scene_elapsed=99.0, timeout=0
        )
        validate_primary_zone_visual_timing(
            self.stages, self.zones, set(), "visual", scene_elapsed=99.0, timeout=None
        )


# ---------------------------------------------------------------------------
# Narrative Profile Content Tests
# ---------------------------------------------------------------------------


class NarrativeProfileContentTests(unittest.TestCase):
    """Semantic checks on specific narrative templates."""

    def setUp(self):
        self.dir = (
            Path(__file__).parent.parent.parent
            / "engines"
            / "manimgl"
            / "src"
            / "templates"
            / "narratives"
        )

    def test_definition_reveal_statement_requires_none(self):
        with open(self.dir / "definition_reveal.json", encoding="utf-8") as f:
            data = json.load(f)
        statement = next(s for s in data["stages"] if s["id"] == "statement")
        self.assertTrue(statement.get("must_be_first"))
        self.assertNotIn("requires", statement)

    def test_definition_reveal_visual_requires_statement(self):
        with open(self.dir / "definition_reveal.json", encoding="utf-8") as f:
            data = json.load(f)
        visual = next(s for s in data["stages"] if s["id"] == "visual")
        self.assertEqual(visual["requires"], ["statement"])

    def test_build_up_payoff_setup_is_first(self):
        with open(self.dir / "build_up_payoff.json", encoding="utf-8") as f:
            data = json.load(f)
        setup = data["stages"][0]
        self.assertEqual(setup["id"], "setup")
        self.assertTrue(setup.get("must_be_first"))

    def test_build_up_payoff_payoff_requires_all_builds(self):
        with open(self.dir / "build_up_payoff.json", encoding="utf-8") as f:
            data = json.load(f)
        payoff = next(s for s in data["stages"] if s["id"] == "payoff")
        self.assertIn("build_3", payoff["requires"])

    def test_wrong_to_right_has_four_stages(self):
        with open(self.dir / "wrong_to_right.json", encoding="utf-8") as f:
            data = json.load(f)
        self.assertEqual(len(data["stages"]), 4)

    def test_all_profiles_engine_agnostic(self):
        for name in ("definition_reveal", "build_up_payoff", "wrong_to_right"):
            with self.subTest(profile=name):
                with open(self.dir / f"{name}.json", encoding="utf-8") as f:
                    data = json.load(f)
                meta = data.get("meta", {})
                self.assertEqual(meta.get("engine"), "agnostic")


if __name__ == "__main__":
    unittest.main(verbosity=2)
