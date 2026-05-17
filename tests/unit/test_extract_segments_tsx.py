"""Unit tests for extract_segments_from_source with .tsx files."""

import importlib.util
import os
import sys
import tempfile

BIN_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "bin")

spec = importlib.util.spec_from_file_location(
    "checks._utils", os.path.join(BIN_DIR, "checks", "_utils.py")
)
checks_utils = importlib.util.module_from_spec(spec)
sys.modules["checks._utils"] = checks_utils
spec.loader.exec_module(checks_utils)


class TestExtractSegmentsTSX:
    def test_single_segment_tsx(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".tsx", delete=False) as f:
            f.write("import {makeScene2D} from '@motion-canvas/2d';\n")
            f.write("// @segment:intro\n")
            f.write("// @time:0.0-2.5s\n")
            f.write("// @keyframes:[0.0, 1.5, 2.5]\n")
            f.write("// @description:Title card\n")
            f.write("// @checks:[no_overlap, readable]\n")
            f.write("export default makeScene2D(function* (view) {\n")
            f.write("  yield* waitFor(2.5);\n")
            f.write("});\n")
            path = f.name

        try:
            segments = checks_utils.extract_segments_from_source(path)
            assert len(segments) == 1
            seg = segments[0]
            assert seg["id"] == "intro"
            assert seg["time_range"] == [0.0, 2.5]
            assert seg["keyframes"] == [0.0, 1.5, 2.5]
            assert seg["description"] == "Title card"
            assert seg["checks"] == ["no_overlap", "readable"]
            assert seg["file"] == os.path.basename(path)
        finally:
            os.unlink(path)

    def test_multiple_segments_tsx(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".tsx", delete=False) as f:
            f.write("// @segment:intro\n")
            f.write("// @time:0.0-1.0s\n")
            f.write("export default function() {}\n")
            f.write("\n")
            f.write("// @segment:main\n")
            f.write("// @time:1.0-5.0s\n")
            f.write("export default function() {}\n")
            path = f.name

        try:
            segments = checks_utils.extract_segments_from_source(path)
            assert len(segments) == 2
            assert segments[0]["id"] == "intro"
            assert segments[1]["id"] == "main"
        finally:
            os.unlink(path)

    def test_no_segments_tsx(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".tsx", delete=False) as f:
            f.write("export default function() {\n")
            f.write("  return null;\n")
            f.write("}\n")
            path = f.name

        try:
            segments = checks_utils.extract_segments_from_source(path)
            assert len(segments) == 0
        finally:
            os.unlink(path)
