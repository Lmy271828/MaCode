"""Unit tests for bin/check-layout.py.

Covers:
  - zone overflow detection
  - object overlap estimation
  - whitespace check
  - font size minimums
"""

import ast
import importlib.util
import os
import sys
import tempfile

BIN_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "bin")

spec = importlib.util.spec_from_file_location(
    "check_layout", os.path.join(BIN_DIR, "check-layout.py")
)
check_layout = importlib.util.module_from_spec(spec)
sys.modules["check_layout"] = check_layout
spec.loader.exec_module(check_layout)


def _make_scene(code: str) -> str:
    with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
        f.write(code)
        return f.name


def _cleanup(path: str):
    try:
        os.unlink(path)
    except OSError:
        pass


class TestZoneOverflow:
    def test_overflow_detected(self):
        code = """
class MyScene(ZoneScene):
    def construct(self):
        self.place(Text("A", font_size=48), "title")
        self.place(Text("B", font_size=48), "title")
        self.place(Text("C", font_size=48), "title")
"""
        path = _make_scene(code)
        try:
            profile = check_layout.load_layout_profile("lecture_3zones")
            report = check_layout.check(path, profile)
            assert report["status"] == "fail"
            assert any(
                i["type"] == "zone_overflow" and i["zone"] == "title" for i in report["issues"]
            )
        finally:
            _cleanup(path)

    def test_no_overflow_when_under_limit(self):
        code = """
class MyScene(ZoneScene):
    def construct(self):
        self.place(Text("A", font_size=48), "title")
        self.place(Text("B", font_size=48), "title")
"""
        path = _make_scene(code)
        try:
            profile = check_layout.load_layout_profile("lecture_3zones")
            report = check_layout.check(path, profile)
            assert not any(
                i["type"] == "zone_overflow" and i["zone"] == "title" for i in report["issues"]
            )
        finally:
            _cleanup(path)


class TestObjectOverlap:
    def test_overlap_detected_for_large_objects(self):
        # Use large rectangles that exceed 50% occupancy when placed together
        code = """
class MyScene(ZoneScene):
    def construct(self):
        self.place(Rectangle(width=1200, height=60), "title")
        self.place(Rectangle(width=1200, height=60), "title")
"""
        path = _make_scene(code)
        try:
            profile = check_layout.load_layout_profile("lecture_3zones")
            report = check_layout.check(path, profile)
            assert any(
                i["type"] == "object_overlap" and i["zone"] == "title" for i in report["issues"]
            )
        finally:
            _cleanup(path)

    def test_no_overlap_for_small_objects(self):
        code = """
class MyScene(ZoneScene):
    def construct(self):
        self.place(Dot(), "title")
        self.place(Dot(), "title")
"""
        path = _make_scene(code)
        try:
            profile = check_layout.load_layout_profile("lecture_3zones")
            report = check_layout.check(path, profile)
            assert not any(
                i["type"] == "object_overlap" and i["zone"] == "title" for i in report["issues"]
            )
        finally:
            _cleanup(path)


class TestWhitespace:
    def test_insufficient_whitespace(self):
        # Large rectangle fills nearly all of the small title zone
        code = """
class MyScene(ZoneScene):
    def construct(self):
        self.place(Rectangle(width=1800, height=110), "title")
"""
        path = _make_scene(code)
        try:
            profile = check_layout.load_layout_profile("lecture_3zones")
            report = check_layout.check(path, profile)
            assert any(i["type"] == "insufficient_whitespace" for i in report["issues"])
        finally:
            _cleanup(path)

    def test_sufficient_whitespace(self):
        code = """
class MyScene(ZoneScene):
    def construct(self):
        self.place(Text("A", font_size=24), "title")
"""
        path = _make_scene(code)
        try:
            profile = check_layout.load_layout_profile("lecture_3zones")
            report = check_layout.check(path, profile)
            assert not any(i["type"] == "insufficient_whitespace" for i in report["issues"])
        finally:
            _cleanup(path)


class TestFontSize:
    def test_title_font_size_too_small(self):
        code = """
class MyScene(ZoneScene):
    def construct(self):
        self.place(Text("Title", font_size=30), "title")
"""
        path = _make_scene(code)
        try:
            profile = check_layout.load_layout_profile("lecture_3zones")
            report = check_layout.check(path, profile)
            assert any(
                i["type"] == "font_size_too_small" and i["zone"] == "title"
                for i in report["issues"]
            )
        finally:
            _cleanup(path)

    def test_body_font_size_ok(self):
        code = """
class MyScene(ZoneScene):
    def construct(self):
        self.place(Text("Caption", font_size=30), "caption")
"""
        path = _make_scene(code)
        try:
            profile = check_layout.load_layout_profile("lecture_3zones")
            report = check_layout.check(path, profile)
            assert not any(
                i["type"] == "font_size_too_small" and i["zone"] == "caption"
                for i in report["issues"]
            )
        finally:
            _cleanup(path)

    def test_body_font_size_too_small(self):
        code = """
class MyScene(ZoneScene):
    def construct(self):
        self.place(Text("Caption", font_size=20), "caption")
"""
        path = _make_scene(code)
        try:
            profile = check_layout.load_layout_profile("lecture_3zones")
            report = check_layout.check(path, profile)
            assert any(
                i["type"] == "font_size_too_small" and i["zone"] == "caption"
                for i in report["issues"]
            )
        finally:
            _cleanup(path)


class TestBboxEstimation:
    def test_mathtex_counts_text_chars(self):
        node = ast.parse("MathTex(r'\\\\lim_{x \\to a} f(x) = L')").body[0].value
        bbox = check_layout.estimate_bbox(node)
        assert bbox["type"] == "text"
        assert bbox["text_chars"] > 0

    def test_circle_radius(self):
        node = ast.parse("Circle(radius=3)").body[0].value
        bbox = check_layout.estimate_bbox(node)
        assert bbox["width"] == 6.0
        assert bbox["height"] == 6.0
