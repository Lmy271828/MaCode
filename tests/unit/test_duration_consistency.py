"""Unit tests for bin/checks/duration_consistency.py."""

import importlib.util
import json
import os
import sys
import tempfile

BIN_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "bin")

spec = importlib.util.spec_from_file_location(
    "checks.duration_consistency", os.path.join(BIN_DIR, "checks", "duration_consistency.py")
)
duration_mod = importlib.util.module_from_spec(spec)
sys.modules["checks.duration_consistency"] = duration_mod
spec.loader.exec_module(duration_mod)


class TestDurationMismatch:
    def test_pass_when_duration_matches(self):
        with tempfile.TemporaryDirectory() as scene_dir:
            manifest = {
                "segments": [
                    {"id": "intro", "time_range": [0.0, 2.5], "line_start": 1, "line_end": 5}
                ]
            }
            with open(os.path.join(scene_dir, "manifest.json"), "w") as f:
                json.dump(manifest, f)
            with open(os.path.join(scene_dir, "scene.py"), "w") as f:
                f.write("# @segment:intro\n")
                f.write("# @time:0.0-2.5s\n")
                f.write("def construct(self):\n")
                f.write("    self.wait(2.5)\n")

            result = duration_mod.check(scene_dir)
            assert result["status"] == "pass"
            assert result["segments"][0]["status"] == "pass"

    def test_warning_when_duration_mismatch(self):
        with tempfile.TemporaryDirectory() as scene_dir:
            manifest = {
                "segments": [
                    {"id": "intro", "time_range": [0.0, 1.0], "line_start": 1, "line_end": 5}
                ]
            }
            with open(os.path.join(scene_dir, "manifest.json"), "w") as f:
                json.dump(manifest, f)
            with open(os.path.join(scene_dir, "scene.py"), "w") as f:
                f.write("# @segment:intro\n")
                f.write("# @time:0.0-1.0s\n")
                f.write("def construct(self):\n")
                f.write("    self.wait(3.0)\n")

            result = duration_mod.check(scene_dir)
            assert result["status"] == "warning"
            seg = result["segments"][0]
            assert seg["status"] == "warning"
            assert any(i["type"] == "duration_mismatch" for i in seg["issues"])

    def test_fixable_fields_present(self):
        with tempfile.TemporaryDirectory() as scene_dir:
            manifest = {
                "segments": [
                    {"id": "intro", "time_range": [0.0, 1.0], "line_start": 1, "line_end": 5}
                ]
            }
            with open(os.path.join(scene_dir, "manifest.json"), "w") as f:
                json.dump(manifest, f)
            with open(os.path.join(scene_dir, "scene.py"), "w") as f:
                f.write("# @segment:intro\n")
                f.write("# @time:0.0-1.0s\n")
                f.write("def construct(self):\n")
                f.write("    self.wait(3.0)\n")

            result = duration_mod.check(scene_dir)
            issue = result["segments"][0]["issues"][0]
            assert issue["fixable"] is True
            assert 0.0 <= issue["fix_confidence"] <= 1.0
            assert "fix" in issue
            assert "strategy" in issue["fix"]


class TestAnimationOverlap:
    def test_no_overlap_for_non_consecutive(self):
        segs = [
            {"id": "a", "time_range": [0.0, 1.0]},
            {"id": "b", "time_range": [2.0, 3.0]},
        ]
        assert duration_mod._detect_overlap(segs) == []

    def test_detects_overlap(self):
        segs = [
            {"id": "a", "time_range": [0.0, 2.0]},
            {"id": "b", "time_range": [1.5, 3.0]},
        ]
        issues = duration_mod._detect_overlap(segs)
        assert len(issues) == 1
        assert issues[0]["seg_a"] == "a"
        assert issues[0]["seg_b"] == "b"
        assert issues[0]["overlap"] == 0.5

    def test_overlap_attached_to_segments(self):
        with tempfile.TemporaryDirectory() as scene_dir:
            manifest = {
                "segments": [
                    {"id": "a", "time_range": [0.0, 2.0], "line_start": 1, "line_end": 3},
                    {"id": "b", "time_range": [1.5, 3.0], "line_start": 4, "line_end": 6},
                ]
            }
            with open(os.path.join(scene_dir, "manifest.json"), "w") as f:
                json.dump(manifest, f)
            with open(os.path.join(scene_dir, "scene.py"), "w") as f:
                f.write("# @segment:a\n# @time:0.0-2.0s\ndef a(self): pass\n")
                f.write("# @segment:b\n# @time:1.5-3.0s\ndef b(self): pass\n")

            result = duration_mod.check(scene_dir)
            assert result["status"] == "warning"
            seg_a = [s for s in result["segments"] if s["id"] == "a"][0]
            assert any(i["type"] == "animation_overlap" for i in seg_a["issues"])
