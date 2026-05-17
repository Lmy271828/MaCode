"""Unit tests for bin/scene-init.py.

Covers:
  - init_scene: manifest + scene file generation for all engines
  - sanitize_class_name: directory name → Python class name
  - compact_json: short arrays kept on one line
  - error handling: existing directory
"""

import importlib.util
import json
import os
import sys
import tempfile

import pytest

BIN_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "bin")

spec = importlib.util.spec_from_file_location("scene_init", os.path.join(BIN_DIR, "scene-init.py"))
scene_init = importlib.util.module_from_spec(spec)
sys.modules["scene_init"] = scene_init
spec.loader.exec_module(scene_init)


class TestSanitizeClassName:
    def test_simple_name(self):
        assert scene_init.sanitize_class_name("demo") == "DemoScene"

    def test_underscore(self):
        assert scene_init.sanitize_class_name("my_scene") == "MySceneScene"

    def test_hyphen(self):
        assert scene_init.sanitize_class_name("my-scene") == "MySceneScene"


class TestCompactJson:
    def test_resolution_oneline(self):
        data = {"resolution": [1920, 1080]}
        raw = scene_init.compact_json(data)
        assert '"resolution": [1920, 1080]' in raw

    def test_empty_arrays_compact(self):
        data = {"assets": [], "dependencies": []}
        raw = scene_init.compact_json(data)
        assert '"assets": []' in raw


class TestInitScene:
    def test_manim_scene(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "test_scene")
            scene_init.init_scene(path, "manim", duration=5.0)

            assert os.path.isfile(os.path.join(path, "manifest.json"))
            assert os.path.isfile(os.path.join(path, "scene.py"))

            with open(os.path.join(path, "manifest.json"), encoding="utf-8") as f:
                manifest = json.load(f)
            assert manifest["engine"] == "manim"
            assert manifest["duration"] == 5.0
            assert manifest["template"] == "Scene"

            with open(os.path.join(path, "scene.py"), encoding="utf-8") as f:
                code = f.read()
            assert "from manim import *" in code
            assert "class TestSceneScene(Scene)" in code
            assert "self.wait(4.0)" in code

    def test_manimgl_scene(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "test_scene")
            scene_init.init_scene(path, "manimgl", duration=3.0)

            with open(os.path.join(path, "scene.py"), encoding="utf-8") as f:
                code = f.read()
            assert "from manimlib import *" in code

    def test_motion_canvas_scene(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "test_scene")
            scene_init.init_scene(path, "motion_canvas", duration=2.0)

            assert os.path.isfile(os.path.join(path, "manifest.json"))
            assert os.path.isfile(os.path.join(path, "scene.tsx"))

            with open(os.path.join(path, "manifest.json"), encoding="utf-8") as f:
                manifest = json.load(f)
            assert manifest["engine"] == "motion_canvas"
            assert manifest["template"] == "makeScene2D"

            with open(os.path.join(path, "scene.tsx"), encoding="utf-8") as f:
                code = f.read()
            assert "makeScene2D" in code
            assert "test_scene" in code

    def test_existing_directory_fails(self, capsys):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "exists")
            os.makedirs(path)
            with pytest.raises(SystemExit) as exc_info:
                scene_init.init_scene(path, "manim")
            assert exc_info.value.code == 1
            captured = capsys.readouterr()
            assert "already exists" in captured.err
