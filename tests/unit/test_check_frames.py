"""Unit tests for bin/checks/_frame_utils.py.

Covers:
  - find_frame: frame file discovery with various naming conventions
  - get_composite_offsets: time offset calculation from manifest
"""

import importlib.util
import json
import os
import sys
import tempfile

BIN_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "bin")

# Load shared frame utilities directly from the extracted module
spec = importlib.util.spec_from_file_location(
    "checks._frame_utils", os.path.join(BIN_DIR, "checks", "_frame_utils.py")
)
checks_frame_utils = importlib.util.module_from_spec(spec)
sys.modules["checks._frame_utils"] = checks_frame_utils
spec.loader.exec_module(checks_frame_utils)


class TestFindFrame:
    def test_find_frame_0001_format(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            frames_dir = os.path.join(tmpdir, "frames")
            os.makedirs(frames_dir)
            open(os.path.join(frames_dir, "frame_0001.png"), "w").close()
            result = checks_frame_utils.find_frame(tmpdir, 1)
            assert result is not None
            assert "frame_0001.png" in result

    def test_find_frame_00001_format(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            frames_dir = os.path.join(tmpdir, "frames")
            os.makedirs(frames_dir)
            open(os.path.join(frames_dir, "frame_00001.png"), "w").close()
            result = checks_frame_utils.find_frame(tmpdir, 1)
            assert result is not None

    def test_find_frame_bare_number(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            frames_dir = os.path.join(tmpdir, "frames")
            os.makedirs(frames_dir)
            open(os.path.join(frames_dir, "0001.png"), "w").close()
            result = checks_frame_utils.find_frame(tmpdir, 1)
            assert result is not None

    def test_find_frame_missing(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            frames_dir = os.path.join(tmpdir, "frames")
            os.makedirs(frames_dir)
            result = checks_frame_utils.find_frame(tmpdir, 99)
            assert result is None


class TestGetCompositeOffsets:
    def test_simple_segments(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            seg1_dir = os.path.join(tmpdir, "seg1")
            seg2_dir = os.path.join(tmpdir, "seg2")
            os.makedirs(seg1_dir)
            os.makedirs(seg2_dir)

            for d, dur in [(seg1_dir, 2.0), (seg2_dir, 3.0)]:
                with open(os.path.join(d, "manifest.json"), "w") as f:
                    json.dump({"duration": dur}, f)

            segments = [
                {"id": "s1", "scene_dir": "seg1"},
                {"id": "s2", "scene_dir": "seg2"},
            ]
            offsets = checks_frame_utils.get_composite_offsets(tmpdir, segments)
            assert offsets == [0.0, 2.0]

    def test_with_transition(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            seg1_dir = os.path.join(tmpdir, "seg1")
            seg2_dir = os.path.join(tmpdir, "seg2")
            os.makedirs(seg1_dir)
            os.makedirs(seg2_dir)

            for d, dur in [(seg1_dir, 2.0), (seg2_dir, 3.0)]:
                with open(os.path.join(d, "manifest.json"), "w") as f:
                    json.dump({"duration": dur}, f)

            segments = [
                {"id": "s1", "scene_dir": "seg1", "transition": {"duration": 0.5}},
                {"id": "s2", "scene_dir": "seg2"},
            ]
            offsets = checks_frame_utils.get_composite_offsets(tmpdir, segments)
            # First segment starts at 0, second at 2.0 - 0.5 = 1.5
            assert offsets == [0.0, 1.5]
