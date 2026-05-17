"""Unit tests for bin/patch-manifest.py.

Covers:
  - Atomic patch (duration, fps, resolution)
  - Backup and restore
  - Invalid file handling
  - Resolution single-line preservation
"""

import importlib.util
import json
import os
import sys
import tempfile
from pathlib import Path
from unittest import mock

import pytest

BIN_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "bin")

spec = importlib.util.spec_from_file_location(
    "patch_manifest", os.path.join(BIN_DIR, "patch-manifest.py")
)
patch_manifest = importlib.util.module_from_spec(spec)
sys.modules["patch_manifest"] = patch_manifest
spec.loader.exec_module(patch_manifest)


def _make_manifest(data: dict) -> str:
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        json.dump(data, f)
        return f.name


def _read_manifest(path: str) -> dict:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


class TestPatchManifest:
    def test_patch_duration(self):
        path = _make_manifest({"duration": 10, "fps": 30})
        data = patch_manifest.patch_manifest(path, duration=3.0)
        assert data["duration"] == 3.0
        assert data["fps"] == 30  # unchanged

    def test_patch_fps(self):
        path = _make_manifest({"duration": 10, "fps": 30})
        data = patch_manifest.patch_manifest(path, fps=10)
        assert data["fps"] == 10
        assert data["duration"] == 10  # unchanged

    def test_patch_resolution(self):
        path = _make_manifest({"duration": 10, "resolution": [1920, 1080]})
        data = patch_manifest.patch_manifest(path, resolution=(640, 360))
        assert data["resolution"] == [640, 360]

    def test_patch_all(self):
        path = _make_manifest({"duration": 10, "fps": 30, "resolution": [1920, 1080]})
        data = patch_manifest.patch_manifest(path, duration=3.0, fps=10, resolution=(640, 360))
        assert data["duration"] == 3.0
        assert data["fps"] == 10
        assert data["resolution"] == [640, 360]


class TestWriteManifestAtomic:
    def test_atomic_write(self):
        path = _make_manifest({"duration": 10})
        patch_manifest.write_manifest_atomic(path, {"duration": 5, "fps": 10})
        data = _read_manifest(path)
        assert data["duration"] == 5
        assert data["fps"] == 10

    def test_resolution_single_line(self):
        path = _make_manifest({"duration": 10, "resolution": [1920, 1080]})
        patch_manifest.write_manifest_atomic(path, {"duration": 10, "resolution": [640, 360]})
        with open(path, encoding="utf-8") as f:
            raw = f.read()
        # Resolution should be on a single line
        assert '"resolution": [640, 360]' in raw


class TestBackupRestore:
    def test_backup_and_restore(self):
        path = _make_manifest({"duration": 10, "fps": 30})
        backup = path + ".bak"

        patch_manifest.backup_manifest(path, backup)
        assert Path(backup).is_file()

        # Modify original
        patch_manifest.write_manifest_atomic(path, {"duration": 3, "fps": 10})

        # Restore
        patch_manifest.restore_manifest(path, backup)
        data = _read_manifest(path)
        assert data["duration"] == 10
        assert data["fps"] == 30

    def test_restore_missing_backup(self):
        path = _make_manifest({"duration": 10})
        with pytest.raises(SystemExit):
            patch_manifest.restore_manifest(path, "/tmp/nonexistent_backup.json")


class TestMain:
    def test_cli_patch(self, capsys):
        path = _make_manifest({"duration": 10, "fps": 30})
        with mock.patch.object(
            sys,
            "argv",
            [
                "patch-manifest.py",
                path,
                "--duration",
                "3",
                "--fps",
                "10",
                "--resolution",
                "640x360",
            ],
        ):
            patch_manifest.main()
        data = _read_manifest(path)
        assert data["duration"] == 3.0
        assert data["fps"] == 10
        assert data["resolution"] == [640, 360]

    def test_cli_backup_and_restore(self, capsys):
        path = _make_manifest({"duration": 10})
        backup = path + ".bak"

        # Patch with backup
        with mock.patch.object(
            sys,
            "argv",
            ["patch-manifest.py", path, "--backup", backup, "--duration", "3"],
        ):
            patch_manifest.main()

        # Restore
        with mock.patch.object(
            sys,
            "argv",
            ["patch-manifest.py", path, "--restore", backup],
        ):
            patch_manifest.main()

        data = _read_manifest(path)
        assert data["duration"] == 10

    def test_cli_missing_file(self):
        with mock.patch.object(
            sys, "argv", ["patch-manifest.py", "/tmp/nonexistent_manifest.json", "--duration", "3"]
        ):
            with pytest.raises(SystemExit) as exc_info:
                patch_manifest.main()
            assert exc_info.value.code == 1

    def test_cli_invalid_resolution(self):
        path = _make_manifest({"duration": 10})
        with mock.patch.object(
            sys,
            "argv",
            ["patch-manifest.py", path, "--resolution", "invalid"],
        ):
            with pytest.raises(SystemExit) as exc_info:
                patch_manifest.main()
            assert exc_info.value.code == 1
