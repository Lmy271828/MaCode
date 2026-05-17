"""Unit tests for duration_consistency.py Motion Canvas branch."""

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


class TestDurationConsistencyMC:
    def test_pass_when_duration_matches(self):
        with tempfile.TemporaryDirectory() as scene_dir:
            manifest = {
                "engine": "motion_canvas",
                "segments": [
                    {"id": "intro", "time_range": [0.0, 2.5], "line_start": 1, "line_end": 15}
                ],
            }
            with open(os.path.join(scene_dir, "manifest.json"), "w") as f:
                json.dump(manifest, f)
            with open(os.path.join(scene_dir, "scene.tsx"), "w") as f:
                f.write("// @segment:intro\n")
                f.write("// @time:0.0-2.5s\n")
                f.write("export default function() {\n")
                f.write("  yield* title().opacity(1, 1.0);\n")
                f.write("  yield* waitFor(0.5);\n")
                f.write("  yield* formula().opacity(1, 1.0);\n")
                f.write("}\n")

            result = duration_mod.check(scene_dir)
            assert result["status"] == "pass"
            assert result["segments"][0]["status"] == "pass"

    def test_warning_when_duration_mismatch(self):
        with tempfile.TemporaryDirectory() as scene_dir:
            manifest = {
                "engine": "motion_canvas",
                "segments": [
                    {"id": "intro", "time_range": [0.0, 1.0], "line_start": 1, "line_end": 15}
                ],
            }
            with open(os.path.join(scene_dir, "manifest.json"), "w") as f:
                json.dump(manifest, f)
            with open(os.path.join(scene_dir, "scene.tsx"), "w") as f:
                f.write("// @segment:intro\n")
                f.write("// @time:0.0-1.0s\n")
                f.write("export default function() {\n")
                f.write("  yield* title().opacity(1, 2.0);\n")
                f.write("  yield* waitFor(1.0);\n")
                f.write("}\n")

            result = duration_mod.check(scene_dir)
            assert result["status"] == "warning"
            seg = result["segments"][0]
            assert seg["status"] == "warning"
            assert any(i["type"] == "duration_mismatch" for i in seg["issues"])

    def test_fixable_fields_present(self):
        with tempfile.TemporaryDirectory() as scene_dir:
            manifest = {
                "engine": "motion_canvas",
                "segments": [
                    {"id": "intro", "time_range": [0.0, 1.0], "line_start": 1, "line_end": 15}
                ],
            }
            with open(os.path.join(scene_dir, "manifest.json"), "w") as f:
                json.dump(manifest, f)
            with open(os.path.join(scene_dir, "scene.tsx"), "w") as f:
                f.write("// @segment:intro\n")
                f.write("// @time:0.0-1.0s\n")
                f.write("export default function() {\n")
                f.write("  yield* waitFor(3.0);\n")
                f.write("}\n")

            result = duration_mod.check(scene_dir)
            issue = result["segments"][0]["issues"][0]
            assert issue["fixable"] is True
            assert 0.0 <= issue["fix_confidence"] <= 1.0
            assert "fix" in issue
            assert "strategy" in issue["fix"]
