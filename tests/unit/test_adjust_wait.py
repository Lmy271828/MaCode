"""Unit tests for bin/fix_strategies/adjust_wait.py.

Covers:
  - can_fix: correct issue type and confidence
  - apply: Python self.wait() adjustment (increase & decrease)
  - apply: Python run_time adjustment when no wait found
  - apply: Motion Canvas yield* wait adjustment
  - apply: failure when no adjustable calls found
"""

import importlib.util
import os
import sys
import tempfile

BIN_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "bin")

spec = importlib.util.spec_from_file_location(
    "adjust_wait", os.path.join(BIN_DIR, "fix_strategies", "adjust_wait.py")
)
adjust_wait = importlib.util.module_from_spec(spec)
sys.modules["adjust_wait"] = adjust_wait
spec.loader.exec_module(adjust_wait)


def _make_issue(declared: float, computed: float, lines: list[int] | None = None) -> dict:
    return {
        "type": "duration_mismatch",
        "severity": "warning",
        "declared": declared,
        "computed": computed,
        "suggested_lines": lines or [1, 20],
        "fixable": True,
        "fix_confidence": 0.9,
        "fix": {
            "strategy": "adjust_wait",
            "action": "modify_wait_duration",
            "params": {"target_duration": declared},
        },
    }


class TestCanFix:
    def test_accepts_duration_mismatch(self):
        issue = _make_issue(3.0, 4.0)
        can, conf = adjust_wait.can_fix(issue, "/tmp/fake")
        assert can is True
        assert conf == 0.9

    def test_rejects_wrong_type(self):
        issue = {"type": "overlap", "fix": {"strategy": "adjust_wait"}}
        can, _ = adjust_wait.can_fix(issue, "/tmp/fake")
        assert can is False

    def test_rejects_wrong_strategy(self):
        issue = {"type": "duration_mismatch", "fix": {"strategy": "other"}}
        can, _ = adjust_wait.can_fix(issue, "/tmp/fake")
        assert can is False


class TestApplyPythonWait:
    def test_decreases_wait(self):
        with tempfile.TemporaryDirectory() as d:
            scene_file = os.path.join(d, "scene.py")
            with open(scene_file, "w", encoding="utf-8") as f:
                f.write("from manim import *\n\nclass S(Scene):\n")
                f.write("    def construct(self):\n")
                f.write("        self.play(Create(Circle()), run_time=2.0)\n")
                f.write("        self.wait(2.0)\n")

            issue = _make_issue(3.0, 4.0, lines=[3, 6])
            result = adjust_wait.apply(issue, d)

            assert result["success"] is True
            assert len(result["patches"]) == 1
            patch = result["patches"][0]
            assert "self.wait(1.0)" in patch["new_text"]
            assert "self.wait(2.0)" in patch["old_text"]

    def test_increases_wait(self):
        with tempfile.TemporaryDirectory() as d:
            scene_file = os.path.join(d, "scene.py")
            with open(scene_file, "w", encoding="utf-8") as f:
                f.write("from manim import *\n\nclass S(Scene):\n")
                f.write("    def construct(self):\n")
                f.write("        self.play(Create(Circle()), run_time=1.0)\n")
                f.write("        self.wait(0.5)\n")

            issue = _make_issue(3.0, 1.5, lines=[3, 6])
            result = adjust_wait.apply(issue, d)

            assert result["success"] is True
            patch = result["patches"][0]
            assert "self.wait(2.0)" in patch["new_text"]

    def test_adjusts_run_time_when_no_wait(self):
        with tempfile.TemporaryDirectory() as d:
            scene_file = os.path.join(d, "scene.py")
            with open(scene_file, "w", encoding="utf-8") as f:
                f.write("from manim import *\n\nclass S(Scene):\n")
                f.write("    def construct(self):\n")
                f.write("        self.play(Create(Circle()), run_time=3.0)\n")

            issue = _make_issue(2.0, 3.0, lines=[3, 5])
            result = adjust_wait.apply(issue, d)

            assert result["success"] is True
            patch = result["patches"][0]
            assert "run_time=2.0" in patch["new_text"]


class TestApplyMotionCanvas:
    def test_decreases_mc_wait(self):
        with tempfile.TemporaryDirectory() as d:
            scene_file = os.path.join(d, "scene.tsx")
            with open(scene_file, "w", encoding="utf-8") as f:
                f.write("import {makeScene2D} from '@motion-canvas/2d';\n")
                f.write("export default makeScene2D(function* (view) {\n")
                f.write("  yield* wait(2.0);\n")
                f.write("});\n")

            issue = _make_issue(1.0, 2.0, lines=[2, 4])
            result = adjust_wait.apply(issue, d)

            assert result["success"] is True
            patch = result["patches"][0]
            assert "yield* wait(1.0)" in patch["new_text"]
            assert "yield* wait(2.0)" in patch["old_text"]


class TestApplyFailure:
    def test_no_adjustable_calls(self):
        with tempfile.TemporaryDirectory() as d:
            scene_file = os.path.join(d, "scene.py")
            with open(scene_file, "w", encoding="utf-8") as f:
                f.write("from manim import *\n\nclass S(Scene):\n")
                f.write("    def construct(self):\n")
                f.write("        pass\n")

            issue = _make_issue(3.0, 4.0, lines=[3, 6])
            result = adjust_wait.apply(issue, d)

            assert result["success"] is False
            assert "No adjustable" in result["message"]
