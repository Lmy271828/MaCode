"""Unit tests for bin/layout-compile.py.

Covers:
  - Profile loading
  - Content allocation algorithm
  - Constraint validation
  - CLI exit codes
  - YAML output format
"""

import importlib.util
import json
import os
import sys
import tempfile

import pytest

BIN_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "bin")
PROJECT_ROOT = os.path.join(BIN_DIR, "..")

spec = importlib.util.spec_from_file_location(
    "layout_compile", os.path.join(BIN_DIR, "layout-compile.py")
)
layout_compile = importlib.util.module_from_spec(spec)
sys.modules["layout_compile"] = layout_compile
spec.loader.exec_module(layout_compile)


def _make_manifest(data: dict) -> str:
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        json.dump(data, f)
        return f.name


def _read_yaml(path: str) -> dict:
    """Read YAML using scene-compile's parser for consistency."""
    spec2 = importlib.util.spec_from_file_location(
        "scene_compile", os.path.join(BIN_DIR, "scene-compile.py")
    )
    scene_compile = importlib.util.module_from_spec(spec2)
    sys.modules["scene_compile"] = scene_compile
    spec2.loader.exec_module(scene_compile)
    with open(path, encoding="utf-8") as f:
        return scene_compile._parse_yaml_simple(f.read())


class TestLoadProfiles:
    def test_load_layout_profile(self):
        layout = layout_compile.load_layout_profile("lecture_3zones")
        assert layout["name"] == "lecture_3zones"
        assert "zones" in layout
        assert "constraints" in layout

    def test_load_narrative_profile(self):
        narrative = layout_compile.load_narrative_profile("definition_reveal")
        assert narrative["name"] == "definition_reveal"
        assert len(narrative["stages"]) == 4

    def test_missing_layout_profile_raises(self):
        with pytest.raises(FileNotFoundError):
            layout_compile.load_layout_profile("nonexistent")

    def test_missing_narrative_profile_raises(self):
        with pytest.raises(FileNotFoundError):
            layout_compile.load_narrative_profile("nonexistent")


class TestAllocateContent:
    def test_basic_allocation(self):
        manifest = {
            "content": [
                {"type": "text", "text": "Title", "importance": "high"},
                {"type": "visual", "primitive": "Circle", "importance": "high"},
                {"type": "text", "text": "Note", "importance": "medium"},
            ],
            "layout_profile": "lecture_3zones",
            "narrative_profile": "definition_reveal",
        }
        layout = layout_compile.load_layout_profile("lecture_3zones")
        narrative = layout_compile.load_narrative_profile("definition_reveal")
        stages, errors = layout_compile.allocate_content(
            manifest["content"], narrative, layout
        )
        assert not errors
        assert len(stages) == 4
        # statement stage gets title text (max 2, so both Title and Note fit)
        assert stages[0]["id"] == "statement"
        assert len(stages[0]["content"]) == 2
        assert stages[0]["content"][0]["text"] == "Title"
        # visual stage gets Circle
        assert stages[1]["id"] == "visual"
        assert len(stages[1]["content"]) == 1
        assert stages[1]["content"][0]["primitive"] == "Circle"

    def test_importance_sorting(self):
        manifest = {
            "content": [
                {"type": "text", "text": "Low", "importance": "low"},
                {"type": "text", "text": "High", "importance": "high"},
                {"type": "text", "text": "Medium", "importance": "medium"},
                {"type": "visual", "primitive": "Circle", "importance": "high"},
            ],
            "layout_profile": "lecture_3zones",
            "narrative_profile": "definition_reveal",
        }
        layout = layout_compile.load_layout_profile("lecture_3zones")
        narrative = layout_compile.load_narrative_profile("definition_reveal")
        stages, errors = layout_compile.allocate_content(
            manifest["content"], narrative, layout
        )
        assert not errors
        title_content = stages[0]["content"]
        assert len(title_content) == 2  # max_objects for title
        # High should come first
        assert title_content[0]["text"] == "High"
        assert title_content[1]["text"] == "Medium"

    def test_text_stage_accepts_formula(self):
        manifest = {
            "content": [
                {"type": "formula", "latex": "E=mc^2", "importance": "high"},
                {"type": "visual", "primitive": "Circle", "importance": "high"},
            ],
            "layout_profile": "lecture_3zones",
            "narrative_profile": "definition_reveal",
        }
        layout = layout_compile.load_layout_profile("lecture_3zones")
        narrative = layout_compile.load_narrative_profile("definition_reveal")
        stages, errors = layout_compile.allocate_content(
            manifest["content"], narrative, layout
        )
        assert not errors
        # formula should go to text stage (statement)
        assert stages[0]["content"][0]["type"] == "formula"

    def test_zone_max_objects_respected(self):
        # title zone max_objects = 2
        manifest = {
            "content": [
                {"type": "text", "text": "A", "importance": "high"},
                {"type": "text", "text": "B", "importance": "high"},
                {"type": "text", "text": "C", "importance": "high"},
                {"type": "visual", "primitive": "Circle", "importance": "high"},
            ],
            "layout_profile": "lecture_3zones",
            "narrative_profile": "definition_reveal",
        }
        layout = layout_compile.load_layout_profile("lecture_3zones")
        narrative = layout_compile.load_narrative_profile("definition_reveal")
        stages, errors = layout_compile.allocate_content(
            manifest["content"], narrative, layout
        )
        assert not errors
        # title gets 2, annotation gets 1 (text)
        assert len(stages[0]["content"]) == 2  # title

    def test_empty_content(self):
        # Empty content triggers primary zone violation, so we test stage emptiness
        # by providing a visual that fills the primary zone but leaving text stages empty.
        manifest = {
            "content": [
                {"type": "visual", "primitive": "Circle", "importance": "high"},
            ],
            "layout_profile": "lecture_3zones",
            "narrative_profile": "definition_reveal",
        }
        layout = layout_compile.load_layout_profile("lecture_3zones")
        narrative = layout_compile.load_narrative_profile("definition_reveal")
        stages, errors = layout_compile.allocate_content(
            manifest["content"], narrative, layout
        )
        assert not errors
        # text stages should be empty
        assert stages[0]["content"] == []  # statement
        assert stages[2]["content"] == []  # annotation
        # visual stage should have the Circle
        assert stages[1]["content"][0]["primitive"] == "Circle"

    def test_unmatched_content_remains_in_pool(self):
        # Provide visual for primary zone but extra text that won't fit
        manifest = {
            "content": [
                {"type": "text", "text": "Title", "importance": "high"},
                {"type": "text", "text": "Note", "importance": "high"},
                {"type": "text", "text": "Extra", "importance": "high"},
                {"type": "visual", "primitive": "Circle", "importance": "high"},
            ],
            "layout_profile": "lecture_3zones",
            "narrative_profile": "definition_reveal",
        }
        layout = layout_compile.load_layout_profile("lecture_3zones")
        narrative = layout_compile.load_narrative_profile("definition_reveal")
        stages, errors = layout_compile.allocate_content(
            manifest["content"], narrative, layout
        )
        assert not errors
        # title gets 2 text items (max), annotation gets 1
        assert len(stages[0]["content"]) == 2
        assert len(stages[2]["content"]) == 1
        # Extra text remains unassigned (no more text stages)
        assert stages[3]["content"] == []  # caption stage might get text or not
        # But importantly, visual stage gets the Circle
        assert stages[1]["content"][0]["primitive"] == "Circle"


class TestConstraintValidation:
    def test_max_objects_violation(self):
        # max_objects is enforced during allocation, so overflow cannot happen.
        # This test verifies the limiting behavior.
        layout = layout_compile.load_layout_profile("lecture_3zones")
        narrative = layout_compile.load_narrative_profile("definition_reveal")
        content = [
            {"type": "text", "text": "A", "importance": "high"},
            {"type": "text", "text": "B", "importance": "high"},
            {"type": "text", "text": "C", "importance": "high"},
            {"type": "visual", "primitive": "Circle", "importance": "high"},
        ]
        stages, errors = layout_compile.allocate_content(content, narrative, layout)
        # No error because algorithm limits allocation to max_objects
        assert not errors
        # title limited to 2
        assert len(stages[0]["content"]) == 2

    def test_primary_zone_no_visual_error(self):
        layout = layout_compile.load_layout_profile("lecture_3zones")
        narrative = layout_compile.load_narrative_profile("definition_reveal")
        content = [
            {"type": "text", "text": "Title", "importance": "high"},
            {"type": "text", "text": "Note", "importance": "high"},
        ]
        stages, errors = layout_compile.allocate_content(content, narrative, layout)
        assert errors
        assert any("Primary zone" in e for e in errors)

    def test_max_text_chars_error(self):
        layout = layout_compile.load_layout_profile("lecture_3zones")
        narrative = layout_compile.load_narrative_profile("definition_reveal")
        long_text = "x" * 200
        content = [
            {"type": "text", "text": long_text, "importance": "high"},
            {"type": "visual", "primitive": "Circle", "importance": "high"},
        ]
        stages, errors = layout_compile.allocate_content(content, narrative, layout)
        assert errors
        assert any("text characters" in e for e in errors)

    def test_suggestions_generated(self):
        layout = layout_compile.load_layout_profile("lecture_3zones")
        errors = ["Zone 'title': max_objects=2, allocated=3"]
        suggestions = layout_compile.generate_suggestions(errors, layout)
        assert len(suggestions) == 1
        assert "Move excess objects" in suggestions[0]


class TestCLI:
    def test_cli_success(self):
        manifest = {
            "title": "Test",
            "content": [
                {"type": "text", "text": "Hello", "importance": "high"},
                {"type": "visual", "primitive": "Circle", "importance": "high"},
            ],
            "layout_profile": "lecture_3zones",
            "narrative_profile": "definition_reveal",
        }
        manifest_path = _make_manifest(manifest)
        output_path = manifest_path.replace(".json", "_layout.yaml")
        ret = layout_compile.main([manifest_path, "--output", output_path])
        assert ret == 0
        assert os.path.exists(output_path)
        data = _read_yaml(output_path)
        assert data["layout_profile"] == "lecture_3zones"
        assert len(data["stages"]) == 4
        os.unlink(manifest_path)
        os.unlink(output_path)

    def test_cli_missing_manifest(self):
        ret = layout_compile.main(["/nonexistent/manifest.json"])
        assert ret == 1

    def test_cli_constraint_error(self):
        manifest = {
            "title": "Test",
            "content": [
                {"type": "text", "text": "x" * 200, "importance": "high"},
            ],
            "layout_profile": "lecture_3zones",
            "narrative_profile": "definition_reveal",
        }
        manifest_path = _make_manifest(manifest)
        ret = layout_compile.main([manifest_path])
        assert ret == 1
        os.unlink(manifest_path)

    def test_yaml_output_format(self):
        manifest = {
            "title": "Test",
            "content": [
                {"type": "text", "text": "Hello", "importance": "high"},
                {"type": "visual", "primitive": "Circle", "importance": "high"},
            ],
            "layout_profile": "lecture_3zones",
            "narrative_profile": "definition_reveal",
        }
        manifest_path = _make_manifest(manifest)
        output_path = manifest_path.replace(".json", "_layout.yaml")
        layout_compile.main([manifest_path, "--output", output_path])
        with open(output_path, encoding="utf-8") as f:
            text = f.read()
        assert "layout_profile: lecture_3zones" in text
        assert "stages:" in text
        assert "content: []" in text or "- type:" in text
        os.unlink(manifest_path)
        os.unlink(output_path)
