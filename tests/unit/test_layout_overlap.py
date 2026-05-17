"""Unit tests for bin/checks/layout_overlap.py."""

import importlib.util
import json
import os
import sys
import tempfile

BIN_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "bin")

spec = importlib.util.spec_from_file_location(
    "checks.layout_overlap", os.path.join(BIN_DIR, "checks", "layout_overlap.py")
)
layout_mod = importlib.util.module_from_spec(spec)
sys.modules["checks.layout_overlap"] = layout_mod
spec.loader.exec_module(layout_mod)


class TestAabbIntersect:
    def test_non_overlapping(self):
        a = {"x": 0.0, "y": 0.0, "w": 0.5, "h": 0.5}
        b = {"x": 0.6, "y": 0.6, "w": 0.3, "h": 0.3}
        assert layout_mod.aabb_intersect(a, b) is False

    def test_overlapping(self):
        a = {"x": 0.3, "y": 0.3, "w": 0.4, "h": 0.4}
        b = {"x": 0.5, "y": 0.5, "w": 0.4, "h": 0.4}
        assert layout_mod.aabb_intersect(a, b) is True

    def test_edge_touching_not_overlap(self):
        a = {"x": 0.0, "y": 0.0, "w": 0.5, "h": 0.5}
        b = {"x": 0.5, "y": 0.0, "w": 0.5, "h": 0.5}
        assert layout_mod.aabb_intersect(a, b) is False


class TestOverlapArea:
    def test_no_overlap_zero_area(self):
        a = {"x": 0.0, "y": 0.0, "w": 0.3, "h": 0.3}
        b = {"x": 0.5, "y": 0.5, "w": 0.3, "h": 0.3}
        assert layout_mod.overlap_area(a, b) == 0.0

    def test_partial_overlap(self):
        a = {"x": 0.3, "y": 0.3, "w": 0.4, "h": 0.4}
        b = {"x": 0.5, "y": 0.5, "w": 0.4, "h": 0.4}
        area = layout_mod.overlap_area(a, b)
        assert 0.0 < area < 0.16

    def test_full_overlap(self):
        a = {"x": 0.3, "y": 0.3, "w": 0.4, "h": 0.4}
        b = {"x": 0.3, "y": 0.3, "w": 0.4, "h": 0.4}
        assert abs(layout_mod.overlap_area(a, b) - 0.16) < 1e-9


class TestCheckSnapshot:
    def test_no_text_objects(self):
        snapshot = {
            "timestamp": 0,
            "objects": [
                {"id": "circle", "type": "visual", "bbox": {"x": 0.1, "y": 0.1, "w": 0.2, "h": 0.2}}
            ],
        }
        assert layout_mod.check_snapshot(snapshot) == []

    def test_text_overlap_detected(self):
        snapshot = {
            "timestamp": 1.5,
            "objects": [
                {"id": "title", "type": "text", "bbox": {"x": 0.3, "y": 0.1, "w": 0.4, "h": 0.08}},
                {
                    "id": "subtitle",
                    "type": "text",
                    "bbox": {"x": 0.35, "y": 0.12, "w": 0.3, "h": 0.06},
                },
            ],
        }
        issues = layout_mod.check_snapshot(snapshot)
        assert len(issues) == 1
        assert issues[0]["type"] == "text_overlap"
        assert issues[0]["severity"] == "warning"
        assert "title" in issues[0]["objects"]
        assert "subtitle" in issues[0]["objects"]
        assert issues[0]["overlap_area"] > 0

    def test_formula_and_text_overlap(self):
        snapshot = {
            "timestamp": 0,
            "objects": [
                {"id": "label", "type": "text", "bbox": {"x": 0.2, "y": 0.2, "w": 0.3, "h": 0.1}},
                {
                    "id": "eq",
                    "type": "formula",
                    "bbox": {"x": 0.25, "y": 0.25, "w": 0.2, "h": 0.08},
                },
            ],
        }
        issues = layout_mod.check_snapshot(snapshot)
        assert len(issues) == 1
        assert issues[0]["type"] == "text_overlap"

    def test_no_overlap_same_types(self):
        snapshot = {
            "timestamp": 0,
            "objects": [
                {"id": "a", "type": "text", "bbox": {"x": 0.1, "y": 0.1, "w": 0.2, "h": 0.1}},
                {"id": "b", "type": "text", "bbox": {"x": 0.5, "y": 0.5, "w": 0.2, "h": 0.1}},
            ],
        }
        assert layout_mod.check_snapshot(snapshot) == []


class TestCheck:
    def test_pass_when_no_snapshot_file(self):
        with tempfile.TemporaryDirectory() as scene_dir:
            result = layout_mod.check(scene_dir)
            assert result["status"] == "pass"
            assert result["segments"] == []

    def test_detects_overlap_in_snapshot_file(self):
        with tempfile.TemporaryDirectory() as scene_dir:
            snapshot = {
                "timestamp": 0,
                "engine": "manimgl",
                "canvas": [1920, 1080],
                "objects": [
                    {"id": "t1", "type": "text", "bbox": {"x": 0.3, "y": 0.1, "w": 0.4, "h": 0.08}},
                    {
                        "id": "t2",
                        "type": "text",
                        "bbox": {"x": 0.35, "y": 0.12, "w": 0.3, "h": 0.06},
                    },
                ],
            }
            path = os.path.join(scene_dir, "layout_snapshots.jsonl")
            with open(path, "w") as f:
                f.write(json.dumps(snapshot) + "\n")

            result = layout_mod.check(scene_dir)
            assert result["status"] == "warning"
            assert len(result["segments"]) == 1
            assert result["segments"][0]["status"] == "warning"
            assert any(i["type"] == "text_overlap" for i in result["segments"][0]["issues"])
