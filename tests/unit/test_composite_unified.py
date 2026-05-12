"""Unit tests for bin/composite-unified.py.

Covers:
  - find_scene_class: AST inheritance detection, multi-class files, fallback
  - engine selection: manim vs manimgl vs default
  - params injection: generated code when present, omitted when absent
"""

import importlib.util
import json
import os
import sys
import tempfile

import pytest

BIN_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "bin")

spec = importlib.util.spec_from_file_location(
    "composite_unified", os.path.join(BIN_DIR, "composite-unified.py")
)
composite_unified = importlib.util.module_from_spec(spec)
sys.modules["composite_unified"] = composite_unified
spec.loader.exec_module(composite_unified)


class TestFindSceneClass:
    """Tests for find_scene_class AST + regex fallback."""

    def test_ast_detects_scene_inheritance(self):
        source = """
class Helper:
    pass

class MyScene(Scene):
    def construct(self):
        pass
"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
            f.write(source)
            path = f.name
        try:
            result = composite_unified.find_scene_class(path)
            assert result == "MyScene"
        finally:
            os.unlink(path)

    def test_ast_detects_macodescene(self):
        source = """
class MyScene(MaCodeScene):
    def construct(self):
        pass
"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
            f.write(source)
            path = f.name
        try:
            result = composite_unified.find_scene_class(path)
            assert result == "MyScene"
        finally:
            os.unlink(path)

    def test_ast_prefers_first_scene_subclass(self):
        source = """
class FirstScene(Scene):
    pass

class SecondScene(Scene):
    pass
"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
            f.write(source)
            path = f.name
        try:
            result = composite_unified.find_scene_class(path)
            assert result == "FirstScene"
        finally:
            os.unlink(path)

    def test_fallback_regex_when_no_scene_subclass(self):
        source = """
class Helper():
    pass

class AnotherHelper():
    pass
"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
            f.write(source)
            path = f.name
        try:
            result = composite_unified.find_scene_class(path)
            # Regex fallback returns first class found
            assert result == "Helper"
        finally:
            os.unlink(path)

    def test_fallback_regex_on_syntax_error(self):
        source = "this is not valid python !!!"
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
            f.write(source)
            path = f.name
        try:
            result = composite_unified.find_scene_class(path)
            # No class definition found, returns default "Scene"
            assert result == "Scene"
        finally:
            os.unlink(path)

    def test_fallback_regex_on_empty_file(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
            f.write("")
            path = f.name
        try:
            result = composite_unified.find_scene_class(path)
            assert result == "Scene"
        finally:
            os.unlink(path)


class TestEngineSelection:
    """Tests for engine-specific import generation."""

    @pytest.fixture
    def tmp_composite_scene(self):
        with tempfile.TemporaryDirectory() as tmp:
            scene_dir = os.path.join(tmp, "composite_scene")
            os.makedirs(scene_dir)

            # Create a simple shot
            shot_dir = os.path.join(scene_dir, "shots", "00_intro")
            os.makedirs(shot_dir)
            with open(os.path.join(shot_dir, "scene.py"), "w", encoding="utf-8") as f:
                f.write("class IntroScene(Scene):\n    def construct(self):\n        pass\n")
            with open(os.path.join(shot_dir, "manifest.json"), "w", encoding="utf-8") as f:
                json.dump({"duration": 1.0}, f)

            yield scene_dir

    def test_engine_manim(self, tmp_composite_scene):
        manifest = {
            "type": "composite-unified",
            "engine": "manim",
            "segments": [{"id": "intro", "scene_dir": "shots/00_intro"}],
        }
        with open(os.path.join(tmp_composite_scene, "manifest.json"), "w", encoding="utf-8") as f:
            json.dump(manifest, f)

        output_dir = os.path.join(tmp_composite_scene, "output")
        composite_unified.generate_orchestrator(tmp_composite_scene, output_dir)

        with open(os.path.join(output_dir, "scene.py"), encoding="utf-8") as f:
            content = f.read()
        assert "from manim import *" in content
        assert "from manimlib import *" not in content

    def test_engine_manimgl(self, tmp_composite_scene):
        manifest = {
            "type": "composite-unified",
            "engine": "manimgl",
            "segments": [{"id": "intro", "scene_dir": "shots/00_intro"}],
        }
        with open(os.path.join(tmp_composite_scene, "manifest.json"), "w", encoding="utf-8") as f:
            json.dump(manifest, f)

        output_dir = os.path.join(tmp_composite_scene, "output")
        composite_unified.generate_orchestrator(tmp_composite_scene, output_dir)

        with open(os.path.join(output_dir, "scene.py"), encoding="utf-8") as f:
            content = f.read()
        assert "from manimlib import *" in content
        assert "from manim import *" not in content

    def test_engine_default(self, tmp_composite_scene):
        manifest = {
            "type": "composite-unified",
            # no engine field
            "segments": [{"id": "intro", "scene_dir": "shots/00_intro"}],
        }
        with open(os.path.join(tmp_composite_scene, "manifest.json"), "w", encoding="utf-8") as f:
            json.dump(manifest, f)

        output_dir = os.path.join(tmp_composite_scene, "output")
        composite_unified.generate_orchestrator(tmp_composite_scene, output_dir)

        with open(os.path.join(output_dir, "scene.py"), encoding="utf-8") as f:
            content = f.read()
        assert "from manim import *" in content


class TestParamsInjection:
    """Tests for composite params code generation."""

    @pytest.fixture
    def tmp_composite_scene(self):
        with tempfile.TemporaryDirectory() as tmp:
            scene_dir = os.path.join(tmp, "composite_scene")
            os.makedirs(scene_dir)

            shot_dir = os.path.join(scene_dir, "shots", "00_intro")
            os.makedirs(shot_dir)
            with open(os.path.join(shot_dir, "scene.py"), "w", encoding="utf-8") as f:
                f.write("class IntroScene(Scene):\n    def construct(self):\n        pass\n")
            with open(os.path.join(shot_dir, "manifest.json"), "w", encoding="utf-8") as f:
                json.dump({"duration": 1.0}, f)

            yield scene_dir

    def test_params_injected_when_present(self, tmp_composite_scene):
        manifest = {
            "type": "composite-unified",
            "engine": "manim",
            "params": {"theme_color": "#1E90FF", "title_text": "Test"},
            "segments": [{"id": "intro", "scene_dir": "shots/00_intro"}],
        }
        with open(os.path.join(tmp_composite_scene, "manifest.json"), "w", encoding="utf-8") as f:
            json.dump(manifest, f)

        output_dir = os.path.join(tmp_composite_scene, "output")
        composite_unified.generate_orchestrator(tmp_composite_scene, output_dir)

        with open(os.path.join(output_dir, "scene.py"), encoding="utf-8") as f:
            content = f.read()
        assert "_params = {}" in content
        assert 'os.environ.get("MACODE_PARAMS_JSON", "")' in content
        assert "json.load(f)" in content

    def test_params_omitted_when_absent(self, tmp_composite_scene):
        manifest = {
            "type": "composite-unified",
            "engine": "manim",
            "segments": [{"id": "intro", "scene_dir": "shots/00_intro"}],
        }
        with open(os.path.join(tmp_composite_scene, "manifest.json"), "w", encoding="utf-8") as f:
            json.dump(manifest, f)

        output_dir = os.path.join(tmp_composite_scene, "output")
        composite_unified.generate_orchestrator(tmp_composite_scene, output_dir)

        with open(os.path.join(output_dir, "scene.py"), encoding="utf-8") as f:
            content = f.read()
        assert "_params" not in content
        assert "MACODE_PARAMS_JSON" not in content
