"""Unit tests for bin/extract-keyframes.py.

Covers:
  - get_duration: ffprobe parsing
  - extract_keyframes: default count, explicit times, manifest generation
  - main: CLI argument handling
"""

import importlib.util
import os
import sys
import tempfile
from unittest import mock

import pytest

BIN_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "bin")

spec = importlib.util.spec_from_file_location(
    "extract_keyframes", os.path.join(BIN_DIR, "extract-keyframes.py")
)
extract_keyframes = importlib.util.module_from_spec(spec)
sys.modules["extract_keyframes"] = extract_keyframes
spec.loader.exec_module(extract_keyframes)


class TestGetDuration:
    def test_parses_float(self):
        with mock.patch(
            "extract_keyframes.subprocess.run",
            return_value=mock.Mock(returncode=0, stdout="3.500\n", stderr=""),
        ):
            assert extract_keyframes.get_duration("fake.mp4") == 3.5

    def test_ffprobe_failure_raises(self):
        with mock.patch(
            "extract_keyframes.subprocess.run",
            return_value=mock.Mock(returncode=1, stdout="", stderr="error"),
        ):
            with pytest.raises(RuntimeError):
                extract_keyframes.get_duration("fake.mp4")


class TestExtractKeyframes:
    def test_explicit_times(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            mp4 = os.path.join(tmpdir, "fake.mp4")
            open(mp4, "a").close()
            out_dir = os.path.join(tmpdir, "frames")

            call_log = []

            def fake_run(cmd, **kwargs):
                call_log.append(cmd)
                # Simulate ffmpeg creating the output file
                if "ffmpeg" in cmd:
                    out = cmd[-1]
                    open(out, "a").close()
                return mock.Mock(returncode=0)

            with mock.patch("extract_keyframes.subprocess.run", side_effect=fake_run):
                manifest = extract_keyframes.extract_keyframes(mp4, out_dir, times=[0.0, 1.5])

            assert manifest["count"] == 2
            assert manifest["extracted"] == 2
            assert len(manifest["keyframes"]) == 2
            assert manifest["keyframes"][0]["time"] == 0.0
            assert manifest["keyframes"][1]["time"] == 1.5
            assert os.path.isfile(os.path.join(out_dir, "manifest.json"))

    def test_default_count_creates_evenly_spaced(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            mp4 = os.path.join(tmpdir, "fake.mp4")
            open(mp4, "a").close()
            out_dir = os.path.join(tmpdir, "frames")

            def fake_run(cmd, **kwargs):
                if "ffprobe" in cmd:
                    return mock.Mock(returncode=0, stdout="10.0\n")
                if "ffmpeg" in cmd:
                    out = cmd[-1]
                    open(out, "a").close()
                return mock.Mock(returncode=0)

            with mock.patch("extract_keyframes.subprocess.run", side_effect=fake_run):
                manifest = extract_keyframes.extract_keyframes(mp4, out_dir, count=3)

            assert manifest["count"] == 3
            times = [k["time"] for k in manifest["keyframes"]]
            assert times[0] == 0.0
            assert times[-1] == 10.0

    def test_ffmpeg_failure_graceful(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            mp4 = os.path.join(tmpdir, "fake.mp4")
            open(mp4, "a").close()
            out_dir = os.path.join(tmpdir, "frames")

            def fake_run(cmd, **kwargs):
                if "ffprobe" in cmd:
                    return mock.Mock(returncode=0, stdout="2.0\n")
                return mock.Mock(returncode=1)

            with mock.patch("extract_keyframes.subprocess.run", side_effect=fake_run):
                manifest = extract_keyframes.extract_keyframes(mp4, out_dir, count=2)

            assert manifest["extracted"] == 0


class TestMain:
    def test_missing_file_exits_2(self):
        with pytest.raises(SystemExit) as exc_info:
            extract_keyframes.main()
        assert exc_info.value.code == 2

    def test_successful_run(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            mp4 = os.path.join(tmpdir, "fake.mp4")
            open(mp4, "a").close()
            out_dir = os.path.join(tmpdir, "out")

            def fake_run(cmd, **kwargs):
                if "ffprobe" in cmd:
                    return mock.Mock(returncode=0, stdout="5.0\n")
                if "ffmpeg" in cmd:
                    out = cmd[cmd.index("-vframes") + 2]
                    open(out, "a").close()
                return mock.Mock(returncode=0)

            with mock.patch("extract_keyframes.subprocess.run", side_effect=fake_run):
                with mock.patch.object(
                    sys, "argv", ["extract-keyframes.py", mp4, "-o", out_dir, "--count", "2"]
                ):
                    code = extract_keyframes.main()
                    assert code == 0
