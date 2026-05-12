"""Unit tests for bin/check-narrative.py.

Covers:
  - stage order compliance
  - primary zone visual timeout
  - text length limits
  - text/visual ratio
"""

import importlib.util
import os
import sys
import tempfile

BIN_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "bin")

spec = importlib.util.spec_from_file_location(
    "check_narrative", os.path.join(BIN_DIR, "check-narrative.py")
)
check_narrative = importlib.util.module_from_spec(spec)
sys.modules["check_narrative"] = check_narrative
spec.loader.exec_module(check_narrative)


def _make_scene(code: str) -> str:
    with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
        f.write(code)
        return f.name


def _cleanup(path: str):
    try:
        os.unlink(path)
    except OSError:
        pass


class TestStageOrder:
    def test_correct_order_passes(self):
        # Enough visual objects to keep ratio <= 0.4
        code = '''
class MyScene(NarrativeScene):
    def construct(self):
        self.stage("statement", Text("D"))
        self.stage("visual", Circle(), Axes(), Square(), Rectangle(), Dot())
        self.stage("annotation", MathTex("x"))
        self.stage("example", Circle())
'''
        path = _make_scene(code)
        try:
            profile = check_narrative.load_narrative_profile("definition_reveal")
            report = check_narrative.check(path, profile)
            assert report["status"] == "pass"
        finally:
            _cleanup(path)

    def test_wrong_order_fails(self):
        code = '''
class MyScene(NarrativeScene):
    def construct(self):
        self.stage("visual", Circle(), Axes(), Square(), Rectangle(), Dot())
        self.stage("statement", Text("D"))
'''
        path = _make_scene(code)
        try:
            profile = check_narrative.load_narrative_profile("definition_reveal")
            report = check_narrative.check(path, profile)
            assert report["status"] == "fail"
            assert any(i["type"] == "stage_order_error" for i in report["issues"])
        finally:
            _cleanup(path)

    def test_must_be_first_violation(self):
        code = '''
class MyScene(NarrativeScene):
    def construct(self):
        self.stage("visual", Circle(), Axes(), Square(), Rectangle(), Dot())
        self.stage("statement", Text("D"))
'''
        path = _make_scene(code)
        try:
            profile = check_narrative.load_narrative_profile("definition_reveal")
            report = check_narrative.check(path, profile)
            assert any(
                i["type"] == "stage_order_error" and "must be first" in i["message"]
                for i in report["issues"]
            )
        finally:
            _cleanup(path)


class TestPrimaryZoneVisualTimeout:
    def test_visual_within_timeout_passes(self):
        code = '''
class MyScene(NarrativeScene):
    def construct(self):
        self.stage("statement", Text("Definition"), run_time=1.0)
        self.stage("visual", Circle(), run_time=1.0)
'''
        path = _make_scene(code)
        try:
            profile = check_narrative.load_narrative_profile("definition_reveal")
            report = check_narrative.check(path, profile)
            assert not any(
                i["type"] == "primary_zone_visual_timeout" for i in report["issues"]
            )
        finally:
            _cleanup(path)

    def test_visual_timeout_fails(self):
        code = '''
class MyScene(NarrativeScene):
    def construct(self):
        self.stage("statement", Text("Definition"), run_time=4.0)
        self.stage("visual", Circle(), run_time=1.0)
'''
        path = _make_scene(code)
        try:
            profile = check_narrative.load_narrative_profile("definition_reveal")
            report = check_narrative.check(path, profile)
            assert any(
                i["type"] == "primary_zone_visual_timeout" for i in report["issues"]
            )
        finally:
            _cleanup(path)


class TestTextLimits:
    def test_text_too_long(self):
        long_text = "A" * 90
        code = f'''
class MyScene(NarrativeScene):
    def construct(self):
        self.stage("statement", Text("{long_text}"))
        self.stage("visual", Circle(), Axes(), Square(), Rectangle(), Dot())
'''
        path = _make_scene(code)
        try:
            profile = check_narrative.load_narrative_profile("definition_reveal")
            report = check_narrative.check(path, profile)
            assert any(i["type"] == "text_too_long" for i in report["issues"])
        finally:
            _cleanup(path)

    def test_text_length_ok(self):
        code = '''
class MyScene(NarrativeScene):
    def construct(self):
        self.stage("statement", Text("Short"))
        self.stage("visual", Circle(), Axes(), Square(), Rectangle(), Dot())
'''
        path = _make_scene(code)
        try:
            profile = check_narrative.load_narrative_profile("definition_reveal")
            report = check_narrative.check(path, profile)
            assert not any(i["type"] == "text_too_long" for i in report["issues"])
        finally:
            _cleanup(path)

    def test_text_visual_ratio_exceeded(self):
        code = '''
class MyScene(NarrativeScene):
    def construct(self):
        self.stage("statement", Text("ABCDEFGHIJ"))
        self.stage("annotation", Text("KLMNOPQRST"))
        self.stage("visual", Circle())
'''
        path = _make_scene(code)
        try:
            profile = check_narrative.load_narrative_profile("definition_reveal")
            report = check_narrative.check(path, profile)
            # 20 text chars / 1 visual = 20.0 > 0.4
            assert any(
                i["type"] == "text_visual_ratio_exceeded" for i in report["issues"]
            )
        finally:
            _cleanup(path)

    def test_text_visual_ratio_ok(self):
        code = '''
class MyScene(NarrativeScene):
    def construct(self):
        self.stage("statement", Text("S"))
        self.stage("visual", Circle(), Axes(), Square(), Rectangle(), Dot())
        self.stage("visual", Rectangle())
'''
        path = _make_scene(code)
        try:
            profile = check_narrative.load_narrative_profile("definition_reveal")
            report = check_narrative.check(path, profile)
            # 1 text char / 6 visual = 0.17 <= 0.4
            assert not any(
                i["type"] == "text_visual_ratio_exceeded" for i in report["issues"]
            )
        finally:
            _cleanup(path)
