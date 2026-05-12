"""Unit tests for calc_animation_time_mc in bin/checks/_utils.py."""

import importlib.util
import os
import sys

BIN_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "bin")

spec = importlib.util.spec_from_file_location("checks._utils", os.path.join(BIN_DIR, "checks", "_utils.py"))
checks_utils = importlib.util.module_from_spec(spec)
sys.modules["checks._utils"] = checks_utils
spec.loader.exec_module(checks_utils)


class TestCalcAnimationTimeMC:
    def test_single_yield(self):
        code = "yield* circle().scale(1.5, 0.8);\n"
        assert checks_utils.calc_animation_time_mc(code) == 0.8

    def test_multiple_yields(self):
        code = """
        yield* title().opacity(1, 0.6);
        yield* title().scale(1, 0.5);
        yield* formula().opacity(1, 0.8);
        """
        assert abs(checks_utils.calc_animation_time_mc(code) - 1.9) < 0.001

    def test_wait_for(self):
        code = "yield* waitFor(0.5);\n"
        assert checks_utils.calc_animation_time_mc(code) == 0.5

    def test_combined(self):
        code = """
        yield* title().opacity(1, 0.6);
        yield* waitFor(0.5);
        yield* formula().opacity(1, 0.8);
        yield* waitFor(0.6);
        """
        assert checks_utils.calc_animation_time_mc(code) == 2.5

    def test_no_duration(self):
        code = "const x = 1;\n"
        assert checks_utils.calc_animation_time_mc(code) == 0.0

    def test_comment_not_matched(self):
        # Comments containing yield* should not be counted
        code = "// yield* some_comment(1, 5.0)\nyield* real().anim(2, 1.0)\n"
        assert checks_utils.calc_animation_time_mc(code) == 1.0
