"""tests/unit/test_zoned_scene.py
Unit tests for ZoneScene layout constraints.

Tests the split modules directly:
- utils.layout_geometry  (pure coordinate math)
- utils.layout_validator (pure constraint logic)
- components.zoned_scene (orchestration — optional smoke test)

No OpenGL display required.
"""

import json
import sys
import unittest
from pathlib import Path

# Inject engines/manimgl/src/ into path so we can import utils directly
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "engines" / "manimgl" / "src"))

import numpy as np
from utils.layout_geometry import compute_position, px_per_unit, zone_bounds
from utils.layout_validator import (
    PrimaryZoneEmptyError,
    ZoneOverflowError,
    ZoneTypeError,
    validate_primary_zone,
    validate_zone,
)


class MockMobject:
    """Minimal stand-in for a Manim Mobject."""

    def __init__(self, name="MockMobject"):
        self._name = name
        self.position = np.array([0.0, 0.0, 0.0])

    def move_to(self, point):
        self.position = np.array(point)

    def __repr__(self):
        return self._name


class CoordinateConversionTests(unittest.TestCase):
    """Test layout_geometry pure functions."""

    def setUp(self):
        self.fw = 8 * 1920 / 1080  # ~14.222
        self.fh = 8.0
        self.canvas = [1920, 1080]

    def test_px_per_unit(self):
        self.assertAlmostEqual(px_per_unit(self.fw, 1920), self.fw / 1920, places=6)

    def test_title_zone_center(self):
        zone = {"rect": [0.0, 0.0, 1.0, 0.12], "padding": [20, 10, 20, 10]}
        pos = compute_position((self.fw, self.fh), self.canvas, zone, "center")
        self.assertAlmostEqual(pos[0], 0.0, places=3)
        self.assertAlmostEqual(pos[1], 3.520, places=3)

    def test_main_visual_zone_center(self):
        zone = {"rect": [0.0, 0.12, 0.70, 0.60], "padding": [30, 20, 30, 20]}
        pos = compute_position((self.fw, self.fh), self.canvas, zone, "center")
        self.assertAlmostEqual(pos[0], -2.133, places=3)
        self.assertAlmostEqual(pos[1], 0.640, places=3)

    def test_align_edges(self):
        zone = {"rect": [0.0, 0.0, 1.0, 0.12], "padding": 0}
        top_pos = compute_position((self.fw, self.fh), self.canvas, zone, "top")
        bottom_pos = compute_position((self.fw, self.fh), self.canvas, zone, "bottom")
        self.assertGreater(top_pos[1], bottom_pos[1])

    def test_padding_reduces_effective_area(self):
        zone_no_pad = {"rect": [0.0, 0.0, 1.0, 0.12], "padding": 0}
        zone_pad = {"rect": [0.0, 0.0, 1.0, 0.12], "padding": 100}
        pos_no = compute_position((self.fw, self.fh), self.canvas, zone_no_pad, "right")
        pos_pad = compute_position((self.fw, self.fh), self.canvas, zone_pad, "right")
        self.assertLess(pos_pad[0], pos_no[0])

    def test_zone_bounds(self):
        bounds = zone_bounds((self.fw, self.fh), [0.0, 0.0, 1.0, 0.12])
        self.assertAlmostEqual(bounds["left"], -self.fw / 2, places=3)
        self.assertAlmostEqual(bounds["right"], self.fw / 2, places=3)
        self.assertAlmostEqual(bounds["top"], self.fh / 2, places=3)
        self.assertAlmostEqual(bounds["bottom"], self.fh / 2 - 0.12 * self.fh, places=3)


class ConstraintValidationTests(unittest.TestCase):
    """Test layout_validator pure functions."""

    def test_max_objects_enforced(self):
        zone = {"max_objects": 2}
        objs = {"title": [MockMobject("Text"), MockMobject("Text")]}
        with self.assertRaises(ZoneOverflowError):
            validate_zone("title", MockMobject(), zone, objs)

    def test_max_objects_under_limit(self):
        zone = {"max_objects": 3}
        objs = {"title": [MockMobject(), MockMobject()]}
        validate_zone("title", MockMobject(), zone, objs)  # should not raise

    def test_allowed_types_enforced(self):
        zone = {"allowed_types": ["Text", "Tex"]}

        class CircleLike(MockMobject):
            pass

        circle = CircleLike()
        with self.assertRaises(ZoneTypeError):
            validate_zone("caption", circle, zone, {})

    def test_allowed_types_permits_exact_match(self):
        """If type name itself is in allowed list, it passes."""
        zone = {"allowed_types": ["MockMobject"]}
        validate_zone("title", MockMobject(), zone, {})

    def test_no_constraints_always_passes(self):
        zone = {}
        validate_zone("any", MockMobject(), zone, {})

    def test_validate_primary_zone_passes_with_visual(self):
        zones = {"main": {"importance": "primary"}}
        objs = {"main": [MockMobject("Circle")]}
        validate_primary_zone(zones, objs)  # should not raise

    def test_validate_primary_zone_fails_with_only_text(self):
        zones = {"main": {"importance": "primary"}}

        # Dynamically create a class named "Text" so it matches default text_types
        FakeText = type("Text", (MockMobject,), {})
        objs = {"main": [FakeText()]}
        with self.assertRaises(PrimaryZoneEmptyError):
            validate_primary_zone(zones, objs)

    def test_validate_primary_zone_no_primary(self):
        zones = {"title": {"importance": "context"}}
        objs = {}
        validate_primary_zone(zones, objs)  # nothing to validate


class LayoutProfileTests(unittest.TestCase):
    """Test JSON profile structure."""

    def setUp(self):
        self.profile_path = (
            Path(__file__).parent.parent.parent
            / "engines"
            / "manimgl"
            / "src"
            / "templates"
            / "layouts"
            / "lecture_3zones.json"
        )

    def test_profile_exists(self):
        self.assertTrue(self.profile_path.exists())

    def test_profile_has_required_fields(self):
        with open(self.profile_path, encoding="utf-8") as f:
            data = json.load(f)
        self.assertIn("name", data)
        self.assertIn("canvas", data)
        self.assertIn("zones", data)
        self.assertIn("constraints", data)

    def test_all_zones_have_rect(self):
        with open(self.profile_path, encoding="utf-8") as f:
            data = json.load(f)
        for name, zone in data["zones"].items():
            self.assertIn("rect", zone, f"Zone '{name}' missing rect")
            self.assertEqual(len(zone["rect"]), 4)

    def test_rects_cover_canvas(self):
        with open(self.profile_path, encoding="utf-8") as f:
            data = json.load(f)
        title = data["zones"]["title"]["rect"]
        main = data["zones"]["main_visual"]["rect"]
        caption = data["zones"]["caption"]["rect"]
        self.assertAlmostEqual(title[1] + title[3], main[1], places=5)
        self.assertAlmostEqual(main[1] + main[3], caption[1], places=5)
        self.assertAlmostEqual(caption[1] + caption[3], 1.0, places=5)


if __name__ == "__main__":
    unittest.main(verbosity=2)
