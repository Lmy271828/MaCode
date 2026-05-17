"""Unit tests for bin/check-density.py.

Covers:
  - object count limit
  - color variety limit
  - animation complexity limit
"""

import importlib.util
import os
import sys
import tempfile

BIN_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "bin")

spec = importlib.util.spec_from_file_location(
    "check_density", os.path.join(BIN_DIR, "check-density.py")
)
check_density = importlib.util.module_from_spec(spec)
sys.modules["check_density"] = check_density
spec.loader.exec_module(check_density)


def _make_scene(code: str) -> str:
    with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
        f.write(code)
        return f.name


def _cleanup(path: str):
    try:
        os.unlink(path)
    except OSError:
        pass


class TestObjectCount:
    def test_too_many_objects(self):
        code = """
class MyScene(ZoneScene):
    def construct(self):
        self.add(Circle())
        self.add(Circle())
        self.add(Circle())
        self.add(Circle())
        self.add(Circle())
        self.add(Circle())
        self.add(Circle())
        self.add(Circle())
        self.add(Circle())
        self.add(Circle())
        self.add(Circle())
        self.add(Circle())
"""
        path = _make_scene(code)
        try:
            report = check_density.check(path)
            assert report["status"] == "fail"
            assert any(i["type"] == "too_many_objects" for i in report["issues"])
        finally:
            _cleanup(path)

    def test_object_count_ok(self):
        code = """
class MyScene(ZoneScene):
    def construct(self):
        self.add(Circle())
        self.add(Square())
"""
        path = _make_scene(code)
        try:
            report = check_density.check(path)
            assert not any(i["type"] == "too_many_objects" for i in report["issues"])
        finally:
            _cleanup(path)


class TestColorCount:
    def test_too_many_colors(self):
        code = """
class MyScene(ZoneScene):
    def construct(self):
        c1 = Circle().set_color("RED")
        c2 = Circle().set_color("GREEN")
        c3 = Circle().set_color("BLUE")
        c4 = Circle().set_color("YELLOW")
        c5 = Circle().set_color("ORANGE")
        c6 = Circle().set_color("PURPLE")
        c7 = Circle().set_color("WHITE")
        self.add(c1, c2, c3, c4, c5, c6, c7)
"""
        path = _make_scene(code)
        try:
            report = check_density.check(path)
            assert report["status"] == "fail"
            assert any(i["type"] == "too_many_colors" for i in report["issues"])
        finally:
            _cleanup(path)

    def test_color_count_ok(self):
        code = """
class MyScene(ZoneScene):
    def construct(self):
        c1 = Circle().set_color("RED")
        c2 = Circle().set_color("GREEN")
        self.add(c1, c2)
"""
        path = _make_scene(code)
        try:
            report = check_density.check(path)
            assert not any(i["type"] == "too_many_colors" for i in report["issues"])
        finally:
            _cleanup(path)

    def test_colors_from_keywords(self):
        code = """
class MyScene(ZoneScene):
    def construct(self):
        c1 = Circle(fill="RED")
        c2 = Circle(color="GREEN")
        c3 = Circle(stroke_color="BLUE")
        c4 = Circle().set_fill("YELLOW")
        c5 = Circle().set_stroke("ORANGE")
        c6 = Circle().set_color("PURPLE")
        c7 = Circle(fill_color="WHITE")
        self.add(c1, c2, c3, c4, c5, c6, c7)
"""
        path = _make_scene(code)
        try:
            report = check_density.check(path)
            assert report["status"] == "fail"
            assert any(i["type"] == "too_many_colors" for i in report["issues"])
        finally:
            _cleanup(path)


class TestAnimationCount:
    def test_too_many_animations(self):
        code = """
class MyScene(ZoneScene):
    def construct(self):
        self.play(Create(Circle()))
        self.play(Create(Circle()))
        self.play(Create(Circle()))
        self.play(Create(Circle()))
        self.play(Create(Circle()))
        self.play(Create(Circle()))
        self.play(Create(Circle()))
        self.play(Create(Circle()))
        self.play(Create(Circle()))
        self.play(Create(Circle()))
        self.play(Create(Circle()))
        self.play(Create(Circle()))
        self.play(Create(Circle()))
        self.play(Create(Circle()))
        self.play(Create(Circle()))
        self.play(Create(Circle()))
        self.play(Create(Circle()))
        self.play(Create(Circle()))
        self.play(Create(Circle()))
        self.play(Create(Circle()))
"""
        path = _make_scene(code)
        try:
            report = check_density.check(path)
            assert report["status"] == "fail"
            assert any(i["type"] == "too_many_animations" for i in report["issues"])
        finally:
            _cleanup(path)

    def test_animation_count_ok(self):
        code = """
class MyScene(ZoneScene):
    def construct(self):
        self.play(Create(Circle()))
        self.play(FadeIn(Square()))
"""
        path = _make_scene(code)
        try:
            report = check_density.check(path)
            assert not any(i["type"] == "too_many_animations" for i in report["issues"])
        finally:
            _cleanup(path)

    def test_place_and_add_counted_as_objects(self):
        code = """
class MyScene(ZoneScene):
    def construct(self):
        self.place(Circle(), "main_visual")
        self.place(Square(), "main_visual")
        self.add(Axes())
"""
        path = _make_scene(code)
        try:
            report = check_density.check(path)
            assert report["summary"]["total_objects"] == 3
        finally:
            _cleanup(path)
