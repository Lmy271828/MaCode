"""Unit tests for bin/scene-compile.py.

Covers:
  - Primitive loading
  - Mobject code generation (all engines)
  - Stage code generation (all engines)
  - Template rendering
  - YAML parser
  - CLI exit codes
"""

import importlib.util
import json
import os
import sys
import tempfile

import pytest

BIN_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "bin")

spec = importlib.util.spec_from_file_location(
    "scene_compile", os.path.join(BIN_DIR, "scene-compile.py")
)
scene_compile = importlib.util.module_from_spec(spec)
sys.modules["scene_compile"] = scene_compile
spec.loader.exec_module(scene_compile)


@pytest.fixture
def primitives():
    return scene_compile.load_primitives()


class TestLoadPrimitives:
    def test_load_primitives_has_mappings(self, primitives):
        assert "primitives" in primitives
        assert "Text" in primitives["primitives"]
        assert primitives["primitives"]["Text"]["manimgl"] == "Text"
        assert primitives["primitives"]["Text"]["manim"] == "Text"
        assert primitives["primitives"]["Text"]["motion_canvas"] == "Txt"

    def test_axes_null_for_motion_canvas(self, primitives):
        assert primitives["primitives"]["Axes"]["motion_canvas"] is None


class TestBuildMobjectCode:
    def test_text_manimgl(self, primitives):
        item = {"type": "text", "text": "Hello World"}
        code = scene_compile.build_mobject_code(item, "manimgl", primitives)
        assert code == 'Text("Hello World")'

    def test_text_escapes_backslash(self, primitives):
        item = {"type": "text", "text": "foo \\ bar"}
        code = scene_compile.build_mobject_code(item, "manimgl", primitives)
        assert 'foo \\\\ bar' in code

    def test_formula_manimgl(self, primitives):
        item = {"type": "formula", "latex": "\\lim_{x \\to a} f(x) = L"}
        code = scene_compile.build_mobject_code(item, "manimgl", primitives)
        assert code == 'Tex(R"\\lim_{x \\to a} f(x) = L")'

    def test_formula_manim(self, primitives):
        item = {"type": "formula", "latex": "\\frac{a}{b}"}
        code = scene_compile.build_mobject_code(item, "manim", primitives)
        assert code == 'MathTex(r"\\frac{a}{b}")'

    def test_visual_numberline(self, primitives):
        item = {"type": "visual", "primitive": "NumberLine", "params": {"x_range": [-5, 5]}}
        code = scene_compile.build_mobject_code(item, "manimgl", primitives)
        assert code == "NumberLine(x_range=[-5, 5])"

    def test_visual_no_params(self, primitives):
        item = {"type": "visual", "primitive": "Circle"}
        code = scene_compile.build_mobject_code(item, "manimgl", primitives)
        assert code == "Circle()"

    def test_unmapped_primitive(self, primitives):
        item = {"type": "visual", "primitive": "Axes"}
        code = scene_compile.build_mobject_code(item, "motion_canvas", primitives)
        assert "TODO" in code
        assert "Axes" in code


class TestBuildStageCodeManim:
    def test_basic_stage(self, primitives):
        stage = {
            "id": "statement",
            "zone": "title",
            "type": "text",
            "duration_hint": 2.0,
            "content": [{"type": "text", "text": "Title"}],
        }
        code = scene_compile.build_stage_code_manim(stage, "manimgl", primitives)
        assert 'self.stage("statement"' in code
        assert 'Text("Title")' in code

    def test_empty_stage(self, primitives):
        stage = {
            "id": "example",
            "zone": "main_visual",
            "type": "visual",
            "duration_hint": 3.0,
            "content": [],
        }
        code = scene_compile.build_stage_code_manim(stage, "manimgl", primitives)
        assert "TODO: No content allocated" in code
        assert "pass" in code

    def test_multiple_mobjects(self, primitives):
        stage = {
            "id": "visual",
            "zone": "main_visual",
            "type": "visual",
            "duration_hint": 4.0,
            "content": [
                {"type": "formula", "latex": "E=mc^2"},
                {"type": "visual", "primitive": "Circle"},
            ],
        }
        code = scene_compile.build_stage_code_manim(stage, "manimgl", primitives)
        assert "Tex(R" in code
        assert "Circle()" in code


class TestBuildStageCodeMC:
    def test_basic_stage(self, primitives):
        stage = {
            "id": "statement",
            "zone": "title",
            "type": "text",
            "duration_hint": 2.0,
            "content": [{"type": "text", "text": "Title"}],
        }
        code = scene_compile.build_stage_code_mc(stage, primitives)
        assert "const statement_ref = createRef<Txt>()" in code
        assert 'view.add(<Txt ref={statement_ref}' in code
        assert "yield* waitFor(2.0)" in code

    def test_empty_stage(self, primitives):
        stage = {
            "id": "example",
            "zone": "main_visual",
            "type": "visual",
            "duration_hint": 3.0,
            "content": [],
        }
        code = scene_compile.build_stage_code_mc(stage, primitives)
        assert "TODO: No content allocated" in code
        assert "yield* waitFor(3.0)" in code

    def test_formula_stage(self, primitives):
        stage = {
            "id": "visual",
            "zone": "main_visual",
            "type": "visual",
            "duration_hint": 4.0,
            "content": [{"type": "formula", "latex": "\\pi"}],
        }
        code = scene_compile.build_stage_code_mc(stage, primitives)
        assert "createRef<Latex>()" in code
        assert 'tex="\\pi"' in code

    def test_unmapped_primitive_todo(self, primitives):
        stage = {
            "id": "visual",
            "zone": "main_visual",
            "type": "visual",
            "duration_hint": 4.0,
            "content": [{"type": "visual", "primitive": "Axes"}],
        }
        code = scene_compile.build_stage_code_mc(stage, primitives)
        assert "TODO: Primitive \"Axes\" is not mapped for Motion Canvas" in code


class TestRenderScene:
    def test_render_manimgl(self, primitives):
        layout = {
            "layout_profile": "lecture_3zones",
            "narrative_profile": "definition_reveal",
            "stages": [
                {
                    "id": "statement",
                    "zone": "title",
                    "type": "text",
                    "duration_hint": 2.0,
                    "content": [{"type": "text", "text": "Hello"}],
                }
            ],
        }
        source = scene_compile.render_scene(layout, "manimgl", primitives)
        assert "from manimlib import *" in source
        assert 'LAYOUT_PROFILE = "lecture_3zones"' in source
        assert "class AutoScene(NarrativeScene)" in source
        assert 'self.stage("statement"' in source

    def test_render_manim(self, primitives):
        layout = {
            "layout_profile": "lecture_3zones",
            "narrative_profile": "definition_reveal",
            "stages": [
                {
                    "id": "statement",
                    "zone": "title",
                    "type": "text",
                    "duration_hint": 2.0,
                    "content": [{"type": "text", "text": "Hello"}],
                }
            ],
        }
        source = scene_compile.render_scene(layout, "manim", primitives)
        assert "from manim import *" in source
        assert "from templates.scene_base import MaCodeScene" in source
        assert 'MathTex(r' in source or "Text(" in source

    def test_render_motion_canvas(self, primitives):
        layout = {
            "layout_profile": "lecture_3zones",
            "narrative_profile": "definition_reveal",
            "stages": [
                {
                    "id": "statement",
                    "zone": "title",
                    "type": "text",
                    "duration_hint": 2.0,
                    "content": [{"type": "text", "text": "Hello"}],
                }
            ],
        }
        source = scene_compile.render_scene(layout, "motion_canvas", primitives)
        assert "import {makeScene2D}" in source
        assert "export default makeScene2D(function* (view)" in source
        assert "createRef<Txt>()" in source
        assert "yield* waitFor(2.0)" in source


class TestYamlParser:
    def test_parse_simple_dict(self):
        text = "foo: bar\nnum: 42\n"
        result = scene_compile._parse_yaml_simple(text)
        assert result == {"foo": "bar", "num": 42}

    def test_parse_inline_list(self):
        text = "canvas: [1920, 1080]\n"
        result = scene_compile._parse_yaml_simple(text)
        assert result == {"canvas": [1920, 1080]}

    def test_parse_nested_list_of_dicts(self):
        text = (
            "stages:\n"
            "  - id: statement\n"
            "    zone: title\n"
            "  - id: visual\n"
            "    zone: main_visual\n"
        )
        result = scene_compile._parse_yaml_simple(text)
        assert result["stages"][0]["id"] == "statement"
        assert result["stages"][1]["zone"] == "main_visual"

    def test_parse_empty_list(self):
        text = "content: []\n"
        result = scene_compile._parse_yaml_simple(text)
        assert result == {"content": []}

    def test_parse_real_layout_compile_output(self, primitives):
        # Integration: parse actual layout-compile output
        import importlib.util

        lc_spec = importlib.util.spec_from_file_location(
            "layout_compile", os.path.join(BIN_DIR, "layout-compile.py")
        )
        lc = importlib.util.module_from_spec(lc_spec)
        sys.modules["layout_compile"] = lc
        lc_spec.loader.exec_module(lc)

        manifest = {
            "content": [
                {"type": "text", "text": "Title", "importance": "high"},
                {"type": "visual", "primitive": "Circle", "importance": "high"},
            ],
            "layout_profile": "lecture_3zones",
            "narrative_profile": "definition_reveal",
        }
        manifest_path = os.path.join(tempfile.gettempdir(), "test_manifest.json")
        with open(manifest_path, "w") as f:
            json.dump(manifest, f)
        output_path = manifest_path.replace(".json", ".yaml")
        lc.main([manifest_path, "--output", output_path])

        with open(output_path, encoding="utf-8") as f:
            yaml_text = f.read()
        parsed = scene_compile._parse_yaml_simple(yaml_text)
        assert parsed["layout_profile"] == "lecture_3zones"
        assert isinstance(parsed["stages"], list)
        assert len(parsed["stages"]) == 4

        os.unlink(manifest_path)
        os.unlink(output_path)


class TestCLI:
    def test_cli_success(self, primitives):
        layout = {
            "layout_profile": "lecture_3zones",
            "narrative_profile": "definition_reveal",
            "stages": [
                {
                    "id": "statement",
                    "zone": "title",
                    "type": "text",
                    "duration_hint": 2.0,
                    "content": [{"type": "text", "text": "Hello"}],
                }
            ],
        }
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            f.write(json.dumps(layout))
            layout_path = f.name

        output_path = layout_path.replace(".yaml", "_out.py")
        ret = scene_compile.main([layout_path, "--engine", "manimgl", "--output", output_path])
        assert ret == 0
        assert os.path.exists(output_path)
        with open(output_path, encoding="utf-8") as f:
            source = f.read()
        assert "class AutoScene" in source
        os.unlink(layout_path)
        os.unlink(output_path)

    def test_cli_missing_layout(self):
        ret = scene_compile.main(["/nonexistent/layout.yaml", "--engine", "manimgl"])
        assert ret == 1

    def test_cli_unsupported_engine(self, primitives):
        layout = {
            "layout_profile": "lecture_3zones",
            "narrative_profile": "definition_reveal",
            "stages": [],
        }
        with pytest.raises(ValueError):
            scene_compile.render_scene(layout, "unknown_engine", primitives)
