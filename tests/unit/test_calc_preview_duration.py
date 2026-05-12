"""Unit tests for bin/calc-preview-duration.py.

Covers:
  - Explicit duration field
  - Fallback to segments time_range
  - Threshold logic (> threshold → max_preview)
  - Missing/invalid file handling
"""

import importlib.util
import json
import os
import sys
import tempfile
from unittest import mock

import pytest

BIN_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "bin")

spec = importlib.util.spec_from_file_location(
    "calc_preview_duration", os.path.join(BIN_DIR, "calc-preview-duration.py")
)
calc_preview_duration = importlib.util.module_from_spec(spec)
sys.modules["calc_preview_duration"] = calc_preview_duration
spec.loader.exec_module(calc_preview_duration)


def _make_manifest(data: dict) -> str:
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        json.dump(data, f)
        return f.name


class TestGetDuration:
    def test_explicit_duration(self):
        path = _make_manifest({"duration": 5.0})
        assert calc_preview_duration.get_duration(path) == 5.0

    def test_explicit_duration_zero_fallback_to_segments(self):
        path = _make_manifest({
            "duration": 0,
            "segments": [{"time_range": [0, 7.5]}],
        })
        assert calc_preview_duration.get_duration(path) == 7.5

    def test_fallback_to_segments(self):
        path = _make_manifest({
            "segments": [
                {"time_range": [0, 3.0]},
                {"time_range": [3.0, 8.5]},
            ],
        })
        assert calc_preview_duration.get_duration(path) == 8.5

    def test_no_duration_no_segments(self):
        path = _make_manifest({})
        assert calc_preview_duration.get_duration(path) == 0.0

    def test_empty_segments(self):
        path = _make_manifest({"segments": []})
        assert calc_preview_duration.get_duration(path) == 0.0


class TestCalcPreviewDuration:
    def test_below_threshold_returns_total(self):
        path = _make_manifest({"duration": 5.0})
        result = calc_preview_duration.calc_preview_duration(path, threshold=10, max_preview=3)
        assert result == 5.0

    def test_above_threshold_returns_max_preview(self):
        path = _make_manifest({"duration": 15.0})
        result = calc_preview_duration.calc_preview_duration(path, threshold=10, max_preview=3)
        assert result == 3.0

    def test_exact_threshold_returns_total(self):
        path = _make_manifest({"duration": 10.0})
        result = calc_preview_duration.calc_preview_duration(path, threshold=10, max_preview=3)
        # 10 is NOT > 10, so return total
        assert result == 10.0

    def test_custom_threshold_and_max(self):
        path = _make_manifest({"duration": 20.0})
        result = calc_preview_duration.calc_preview_duration(path, threshold=5, max_preview=2)
        assert result == 2.0


class TestMain:
    def test_cli_output(self, capsys):
        path = _make_manifest({"duration": 15.0})
        with mock.patch.object(sys, "argv", ["calc-preview-duration.py", path]):
            calc_preview_duration.main()
        captured = capsys.readouterr()
        assert captured.out.strip() == "3.0"

    def test_cli_with_options(self, capsys):
        path = _make_manifest({"duration": 20.0})
        with mock.patch.object(
            sys, "argv",
            ["calc-preview-duration.py", path, "--threshold", "5", "--max-preview", "2"],
        ):
            calc_preview_duration.main()
        captured = capsys.readouterr()
        assert captured.out.strip() == "2.0"

    def test_cli_missing_file(self, capsys):
        with mock.patch.object(
            sys, "argv", ["calc-preview-duration.py", "/tmp/nonexistent_manifest.json"]
        ):
            with pytest.raises(SystemExit) as exc_info:
                calc_preview_duration.main()
            assert exc_info.value.code == 1
