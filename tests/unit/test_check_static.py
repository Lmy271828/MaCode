"""Unit tests for bin/check-static.py and bin/checks/_utils.py.

Covers:
  - extract_segments_from_source: @segment annotations
  - calc_animation_time: self.wait() and run_time accumulation
  - count_formulas: MathTex/Tex/ChineseMathTex detection
  - segments_equal: segment comparison
  - find_function_blocks: AST-based function discovery
  - get_code_block: line-range extraction
"""

import importlib.util
import os
import sys
import tempfile

BIN_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "bin")

# Load shared utilities directly from the extracted module
spec = importlib.util.spec_from_file_location("checks._utils", os.path.join(BIN_DIR, "checks", "_utils.py"))
checks_utils = importlib.util.module_from_spec(spec)
sys.modules["checks._utils"] = checks_utils
spec.loader.exec_module(checks_utils)


class TestExtractSegments:
    def test_single_segment(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
            f.write("# @segment:intro\n")
            f.write("# @time:0.0-2.5s\n")
            f.write("# @keyframes:[0.0, 1.0, 2.5]\n")
            f.write("# @description:Title card\n")
            f.write("# @checks:[no_overlap, readable]\n")
            f.write("def construct(self):\n")
            f.write("    pass\n")
            path = f.name

        try:
            segments = checks_utils.extract_segments_from_source(path)
            assert len(segments) == 1
            seg = segments[0]
            assert seg["id"] == "intro"
            assert seg["time_range"] == [0.0, 2.5]
            assert seg["keyframes"] == [0.0, 1.0, 2.5]
            assert seg["description"] == "Title card"
            assert seg["checks"] == ["no_overlap", "readable"]
            assert seg["file"] == os.path.basename(path)
        finally:
            os.unlink(path)

    def test_multiple_segments(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
            f.write("# @segment:intro\n")
            f.write("# @time:0.0-1.0s\n")
            f.write("def intro(self): pass\n")
            f.write("\n")
            f.write("# @segment:main\n")
            f.write("# @time:1.0-5.0s\n")
            f.write("def main(self): pass\n")
            path = f.name

        try:
            segments = checks_utils.extract_segments_from_source(path)
            assert len(segments) == 2
            assert segments[0]["id"] == "intro"
            assert segments[1]["id"] == "main"
        finally:
            os.unlink(path)

    def test_no_segments(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
            f.write("def construct(self):\n")
            f.write("    pass\n")
            path = f.name

        try:
            segments = checks_utils.extract_segments_from_source(path)
            assert len(segments) == 0
        finally:
            os.unlink(path)


class TestCalcAnimationTime:
    def test_self_wait_with_arg(self):
        code = "self.wait(2.5)\n"
        assert checks_utils.calc_animation_time(code) == 2.5

    def test_self_wait_no_arg(self):
        code = "self.wait()\n"
        assert checks_utils.calc_animation_time(code) == 1.0

    def test_run_time(self):
        code = "self.play(Create(circle), run_time=3.0)\n"
        assert checks_utils.calc_animation_time(code) == 3.0

    def test_multiple_waits(self):
        code = "self.wait(1.0)\nself.wait()\nself.wait(2.0)\n"
        assert checks_utils.calc_animation_time(code) == 4.0

    def test_combined(self):
        code = "self.wait(1.0)\nself.play(FadeIn(t), run_time=2.0)\nself.wait()\n"
        assert checks_utils.calc_animation_time(code) == 4.0


class TestCountFormulas:
    def test_mathtex(self):
        assert checks_utils.count_formulas("t = MathTex('x^2')\n") == 1

    def test_tex(self):
        assert checks_utils.count_formulas("t = Tex('hello')\n") == 1

    def test_chinese_mathtex(self):
        assert checks_utils.count_formulas("t = ChineseMathTex('\\pi')\n") == 1

    def test_multiple(self):
        code = "t1 = MathTex('a')\nt2 = Tex('b')\n"
        assert checks_utils.count_formulas(code) == 2

    def test_none(self):
        assert checks_utils.count_formulas("import numpy\n") == 0


class TestSegmentsEqual:
    def test_equal(self):
        a = {"id": "x", "time_range": [0, 1], "keyframes": [0], "description": "d", "checks": ["c"]}
        b = {"id": "x", "time_range": [0, 1], "keyframes": [0], "description": "d", "checks": ["c"]}
        assert checks_utils.segments_equal(a, b) is True

    def test_different_id(self):
        a = {"id": "x"}
        b = {"id": "y"}
        assert checks_utils.segments_equal(a, b) is False

    def test_different_time_range(self):
        a = {"id": "x", "time_range": [0, 1]}
        b = {"id": "x", "time_range": [0, 2]}
        assert checks_utils.segments_equal(a, b) is False


class TestFindFunctionBlocks:
    def test_finds_functions(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
            f.write("def foo():\n    pass\n")
            f.write("def bar():\n    pass\n")
            path = f.name

        try:
            blocks = checks_utils.find_function_blocks(path)
            names = {b[2] for b in blocks.values()}
            assert "foo" in names
            assert "bar" in names
        finally:
            os.unlink(path)


class TestGetCodeBlock:
    def test_extracts_lines(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
            f.write("line1\nline2\nline3\nline4\n")
            path = f.name

        try:
            block = checks_utils.get_code_block(path, 2, 3)
            assert block == "line2\nline3\n"
        finally:
            os.unlink(path)
