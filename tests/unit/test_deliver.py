"""Unit tests for pipeline/deliver.py.

Covers:
  - Successful delivery with manifest generation
  - SHA-256 computation
  - State.json reading
  - Engine version reading
  - Frame counting
  - Missing source handling
"""

from __future__ import annotations

import importlib.util
import json
import os
import sys
import tempfile

BIN_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "bin")
PIPELINE_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "pipeline")
PROJECT_ROOT = os.path.dirname(PIPELINE_DIR)

# Load deliver.py as a module
loader = importlib.machinery.SourceFileLoader("deliver", os.path.join(PIPELINE_DIR, "deliver.py"))
deliver = importlib.util.module_from_spec(importlib.util.spec_from_loader("deliver", loader))
sys.modules["deliver"] = deliver
loader.exec_module(deliver)


class TestDeliverFunctions:
    def test_sha256_file(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
            f.write("hello world")
            path = f.name
        try:
            result = deliver.sha256_file(path)
            assert len(result) == 64
            assert all(c in "0123456789abcdef" for c in result)
        finally:
            os.unlink(path)

    def test_read_state_json_existing(self):
        with tempfile.TemporaryDirectory() as d:
            state = {"version": "1.0", "status": "completed"}
            with open(os.path.join(d, "state.json"), "w") as f:
                json.dump(state, f)
            result = deliver.read_state_json(d)
            assert result["version"] == "1.0"
            assert result["status"] == "completed"

    def test_read_state_json_missing(self):
        with tempfile.TemporaryDirectory() as d:
            result = deliver.read_state_json(d)
            assert result == {}

    def test_read_manifest_existing(self):
        with tempfile.TemporaryDirectory() as d:
            manifest = {"engine": "manim", "fps": 30}
            with open(os.path.join(d, "manifest.json"), "w") as f:
                json.dump(manifest, f)
            result = deliver.read_manifest(d)
            assert result["engine"] == "manim"

    def test_read_manifest_missing(self):
        with tempfile.TemporaryDirectory() as d:
            result = deliver.read_manifest(d)
            assert result == {}

    def test_count_frames(self):
        with tempfile.TemporaryDirectory() as d:
            open(os.path.join(d, "frame_0001.png"), "w").close()
            open(os.path.join(d, "frame_0002.png"), "w").close()
            open(os.path.join(d, "other.txt"), "w").close()
            assert deliver.count_frames(d) == 2

    def test_count_frames_missing_dir(self):
        assert deliver.count_frames("/nonexistent/path") == 0


class TestMain:
    def test_missing_source(self, capsys):
        with tempfile.TemporaryDirectory() as d:
            old_argv = sys.argv
            try:
                sys.argv = ["deliver.py", "test_scene", d, d]
                ret = deliver.main()
            finally:
                sys.argv = old_argv
            assert ret == 1
            captured = capsys.readouterr()
            assert "source not found" in captured.err

    def test_successful_delivery(self, capsys):
        with tempfile.TemporaryDirectory() as tmp:
            scene_dir = os.path.join(tmp, "scenes", "test_scene")
            tmp_dir = os.path.join(tmp, "tmp", "test_scene")
            out_dir = os.path.join(tmp, "output")
            os.makedirs(scene_dir)
            os.makedirs(tmp_dir)

            # Create source mp4 (minimal valid mp4 header)
            with open(os.path.join(tmp_dir, "final.mp4"), "wb") as f:
                f.write(b"\x00\x00\x00\x20ftypisom")

            # Create manifest
            manifest = {
                "engine": "manim",
                "fps": 30,
                "duration": 3.0,
                "resolution": [1920, 1080],
            }
            with open(os.path.join(scene_dir, "manifest.json"), "w") as f:
                json.dump(manifest, f)

            # Create state
            state = {"version": "1.0", "status": "completed", "startedAt": "2026-01-01T00:00:00Z"}
            with open(os.path.join(tmp_dir, "state.json"), "w") as f:
                json.dump(state, f)

            # Create frames
            frames_dir = os.path.join(tmp_dir, "frames")
            os.makedirs(frames_dir)
            open(os.path.join(frames_dir, "frame_0001.png"), "w").close()

            old_argv = sys.argv
            old_cwd = os.getcwd()
            try:
                os.chdir(tmp)
                sys.argv = ["deliver.py", "test_scene", tmp_dir, out_dir]
                ret = deliver.main()
            finally:
                sys.argv = old_argv
                os.chdir(old_cwd)

            assert ret == 0
            assert os.path.isfile(os.path.join(out_dir, "test_scene.mp4"))
            assert os.path.isfile(os.path.join(out_dir, "test_scene_manifest.json"))

            with open(os.path.join(out_dir, "test_scene_manifest.json")) as f:
                delivery_manifest = json.load(f)

            assert delivery_manifest["scene"] == "test_scene"
            assert delivery_manifest["engine"] == "manim"
            assert delivery_manifest["fps"] == 30
            assert delivery_manifest["frames_rendered"] == 1
            assert "sha256" in delivery_manifest
            assert len(delivery_manifest["sha256"]) == 64
