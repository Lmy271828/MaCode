"""Unit tests for bin/fix_strategies/align_segment_comment.py."""

from __future__ import annotations

import json
import os
import sys
import tempfile

BIN_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "bin")
sys.path.insert(0, BIN_DIR)

from fix_strategies import align_segment_comment


def _make_issue(action: str, seg_id: str = "intro", lines=None) -> dict:
    return {
        "id": seg_id,
        "type": "manifest_missing",
        "message": f'Segment "{seg_id}" 存在于源码注释但不在 manifest.json 中',
        "suggested_lines": lines or [3, 5],
        "fix": {
            "strategy": "align_segment_comment",
            "action": action,
        },
        "fix_confidence": 0.9,
    }


class TestCanFix:
    def test_accepts_align_segment_comment(self):
        issue = _make_issue("add_to_manifest")
        ok, conf = align_segment_comment.can_fix(issue, "/tmp")
        assert ok is True
        assert conf == 0.9

    def test_rejects_other_strategy(self):
        issue = _make_issue("add_to_manifest")
        issue["fix"]["strategy"] = "adjust_wait"
        ok, conf = align_segment_comment.can_fix(issue, "/tmp")
        assert ok is False


class TestAddToManifest:
    def test_adds_segment_to_manifest(self):
        with tempfile.TemporaryDirectory() as d:
            manifest = {"engine": "manim", "duration": 3, "fps": 30}
            with open(os.path.join(d, "manifest.json"), "w", encoding="utf-8") as f:
                json.dump(manifest, f)

            issue = _make_issue("add_to_manifest", seg_id="intro", lines=[3, 5])
            result = align_segment_comment.apply(issue, d)

            assert result["success"] is True
            assert len(result["patches"]) == 1
            patch = result["patches"][0]
            assert patch["file"].endswith("manifest.json")

            # Apply patch
            with open(patch["file"], "w", encoding="utf-8") as f:
                f.write(patch["new_text"])

            with open(os.path.join(d, "manifest.json"), encoding="utf-8") as f:
                updated = json.load(f)
            assert any(s["id"] == "intro" for s in updated["segments"])

    def test_skips_duplicate_segment(self):
        with tempfile.TemporaryDirectory() as d:
            manifest = {"engine": "manim", "duration": 3, "fps": 30, "segments": [{"id": "intro"}]}
            with open(os.path.join(d, "manifest.json"), "w", encoding="utf-8") as f:
                json.dump(manifest, f)

            issue = _make_issue("add_to_manifest", seg_id="intro")
            result = align_segment_comment.apply(issue, d)
            assert result["success"] is False
            assert "already in manifest" in result["message"]


class TestAddSourceComment:
    def test_adds_python_comment(self):
        with tempfile.TemporaryDirectory() as d:
            scene = os.path.join(d, "scene.py")
            with open(scene, "w", encoding="utf-8") as f:
                f.write("from manim import *\n\nclass S(Scene):\n    pass\n")

            issue = _make_issue("add_source_comment", seg_id="main", lines=[3, 3])
            result = align_segment_comment.apply(issue, d)

            assert result["success"] is True
            patch = result["patches"][0]
            assert "# SEGMENT: main" in patch["new_text"]

    def test_adds_tsx_comment(self):
        with tempfile.TemporaryDirectory() as d:
            scene = os.path.join(d, "scene.tsx")
            with open(scene, "w", encoding="utf-8") as f:
                f.write(
                    "import {makeScene2D} from '@motion-canvas/2d';\n\nexport default makeScene2D(function* (view) {\n});\n"
                )

            issue = _make_issue("add_source_comment", seg_id="intro", lines=[2, 2])
            result = align_segment_comment.apply(issue, d)

            assert result["success"] is True
            patch = result["patches"][0]
            assert "// SEGMENT: intro" in patch["new_text"]


class TestUnknownAction:
    def test_returns_failure(self):
        issue = _make_issue("unknown_action")
        result = align_segment_comment.apply(issue, "/tmp")
        assert result["success"] is False
        assert "Unknown action" in result["message"]
