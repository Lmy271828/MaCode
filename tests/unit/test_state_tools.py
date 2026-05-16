#!/usr/bin/env python3
"""Unit tests for bin/state-write.py, bin/progress-write.py, bin/state-read.py."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))


def run_script(name: str, args: list[str], cwd: str | None = None) -> subprocess.CompletedProcess:
    """Run a bin/ script with given args and return CompletedProcess."""
    script = os.path.join(PROJECT_ROOT, "bin", name)
    cmd = [sys.executable, script, *args]
    return subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        cwd=cwd or PROJECT_ROOT,
    )


class TestStateWrite(unittest.TestCase):
    """Tests for state-write.py"""

    def setUp(self) -> None:
        self.tmpdir = tempfile.mkdtemp()
        self.state_dir = os.path.join(self.tmpdir, "state")
        os.makedirs(self.state_dir, exist_ok=True)

    def tearDown(self) -> None:
        import shutil
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def _load_state(self) -> dict:
        path = os.path.join(self.state_dir, "state.json")
        with open(path) as f:
            return json.load(f)

    def test_basic_running(self):
        """Should create state.json with version, tool, status."""
        result = run_script("state-write.py", [self.state_dir, "running", "--tool", "test-tool"])
        self.assertEqual(result.returncode, 0, result.stderr)
        state = self._load_state()
        self.assertEqual(state["version"], "1.1")
        self.assertEqual(state["tool"], "test-tool")
        self.assertEqual(state["status"], "running")
        self.assertIn("startedAt", state)

    def test_completed_with_exit_code(self):
        """Should set exitCode and endedAt on completed."""
        result = run_script(
            "state-write.py",
            [self.state_dir, "running", "--tool", "render.sh"],
        )
        self.assertEqual(result.returncode, 0)
        result = run_script(
            "state-write.py",
            [self.state_dir, "completed", "0", "--tool", "render.sh"],
        )
        self.assertEqual(result.returncode, 0)
        state = self._load_state()
        self.assertEqual(state["status"], "completed")
        self.assertEqual(state["exitCode"], 0)
        self.assertIn("endedAt", state)
        self.assertIn("durationSec", state)
        self.assertEqual(state["version"], "1.1")

    def test_outputs(self):
        """Should parse and write outputs JSON."""
        result = run_script(
            "state-write.py",
            [self.state_dir, "completed", "0", "--outputs", '{"framesRendered":90}'],
        )
        self.assertEqual(result.returncode, 0)
        state = self._load_state()
        self.assertEqual(state["outputs"]["framesRendered"], 90)

    def test_error_message(self):
        """Should write error field on failed status."""
        result = run_script(
            "state-write.py",
            [self.state_dir, "failed", "1", "--error", "Something broke"],
        )
        self.assertEqual(result.returncode, 0)
        state = self._load_state()
        self.assertEqual(state["error"], "Something broke")

    def test_merge_started_at(self):
        """Should preserve existing startedAt when updating status."""
        run_script("state-write.py", [self.state_dir, "running", "--tool", "t"])
        first = self._load_state()
        started = first["startedAt"]

        run_script("state-write.py", [self.state_dir, "completed", "0"])
        second = self._load_state()
        self.assertEqual(second["startedAt"], started)
        self.assertEqual(second["tool"], "t")

    def test_merge_outputs(self):
        """Should merge new outputs into existing outputs."""
        run_script(
            "state-write.py",
            [self.state_dir, "running", "--outputs", '{"port":8080}'],
        )
        run_script(
            "state-write.py",
            [self.state_dir, "completed", "0", "--outputs", '{"framesRendered":30}'],
        )
        state = self._load_state()
        self.assertEqual(state["outputs"]["port"], 8080)
        self.assertEqual(state["outputs"]["framesRendered"], 30)

    def test_invalid_outputs_json(self):
        """Should return non-zero for invalid JSON in --outputs."""
        result = run_script(
            "state-write.py",
            [self.state_dir, "running", "--outputs", "not-json"],
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("invalid", result.stderr)

    def test_timeout_status(self):
        """Should handle timeout status correctly."""
        result = run_script(
            "state-write.py",
            [self.state_dir, "timeout", "124", "--error", "Deadline exceeded"],
        )
        self.assertEqual(result.returncode, 0)
        state = self._load_state()
        self.assertEqual(state["status"], "timeout")
        self.assertEqual(state["exitCode"], 124)
        self.assertEqual(state["error"], "Deadline exceeded")

    def test_task_id(self):
        """Should write taskId when provided."""
        result = run_script(
            "state-write.py",
            [self.state_dir, "running", "--task-id", "my-task-123"],
        )
        self.assertEqual(result.returncode, 0)
        state = self._load_state()
        self.assertEqual(state["taskId"], "my-task-123")

    def test_explicit_timestamps(self):
        """Should accept explicit started-at and ended-at."""
        result = run_script(
            "state-write.py",
            [
                self.state_dir,
                "completed",
                "0",
                "--started-at",
                "2026-05-01T12:00:00Z",
                "--ended-at",
                "2026-05-01T12:00:05Z",
            ],
        )
        self.assertEqual(result.returncode, 0)
        state = self._load_state()
        self.assertEqual(state["startedAt"], "2026-05-01T12:00:00Z")
        self.assertEqual(state["endedAt"], "2026-05-01T12:00:05Z")
        self.assertEqual(state["durationSec"], 5.0)
        self.assertEqual(state["version"], "1.1")

    def test_clear_error_on_success(self):
        """Should clear error field when transitioning to completed."""
        run_script(
            "state-write.py",
            [self.state_dir, "failed", "1", "--error", "Oops"],
        )
        run_script("state-write.py", [self.state_dir, "completed", "0"])
        state = self._load_state()
        self.assertNotIn("error", state)


class TestProgressWrite(unittest.TestCase):
    """Tests for progress-write.py"""

    def setUp(self) -> None:
        self.tmpdir = tempfile.mkdtemp()
        self.progress_file = os.path.join(self.tmpdir, "progress.jsonl")

    def tearDown(self) -> None:
        import shutil
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_basic_append(self):
        """Should append a JSONL record."""
        result = run_script(
            "progress-write.py",
            [self.progress_file, "init", "running", "starting"],
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        with open(self.progress_file) as f:
            lines = f.readlines()
        self.assertEqual(len(lines), 1)
        record = json.loads(lines[0])
        self.assertEqual(record["phase"], "init")
        self.assertEqual(record["status"], "running")
        self.assertEqual(record["message"], "starting")
        self.assertIn("timestamp", record)

    def test_multiple_appends(self):
        """Should append multiple records in order."""
        run_script("progress-write.py", [self.progress_file, "init", "running"])
        run_script("progress-write.py", [self.progress_file, "render", "completed"])
        with open(self.progress_file) as f:
            lines = f.readlines()
        self.assertEqual(len(lines), 2)
        self.assertEqual(json.loads(lines[0])["phase"], "init")
        self.assertEqual(json.loads(lines[1])["phase"], "render")

    def test_no_message(self):
        """Should omit message field when not provided."""
        result = run_script(
            "progress-write.py", [self.progress_file, "render", "running"]
        )
        self.assertEqual(result.returncode, 0)
        with open(self.progress_file) as f:
            record = json.loads(f.read())
        self.assertNotIn("message", record)

    def test_creates_directory(self):
        """Should create parent directory if missing."""
        nested = os.path.join(self.tmpdir, "deep", "path", "progress.jsonl")
        result = run_script("progress-write.py", [nested, "init", "running"])
        self.assertEqual(result.returncode, 0)
        self.assertTrue(os.path.exists(nested))


class TestStateRead(unittest.TestCase):
    """Tests for state-read.py"""

    def setUp(self) -> None:
        self.tmpdir = tempfile.mkdtemp()
        self.state_dir = os.path.join(self.tmpdir, "state")
        os.makedirs(self.state_dir, exist_ok=True)
        state = {
            "version": "1.1",
            "tool": "render.sh",
            "status": "completed",
            "exitCode": 0,
            "outputs": {"framesRendered": 90, "port": 8080},
        }
        with open(os.path.join(self.state_dir, "state.json"), "w") as f:
            json.dump(state, f)

    def tearDown(self) -> None:
        import shutil
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_read_full(self):
        """Should print full JSON when no filter."""
        result = run_script("state-read.py", [self.state_dir])
        self.assertEqual(result.returncode, 0)
        data = json.loads(result.stdout)
        self.assertEqual(data["status"], "completed")

    def test_read_field(self):
        """Should extract a top-level field."""
        result = run_script("state-read.py", [self.state_dir, "--field", "status"])
        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stdout.strip(), "completed")

    def test_read_jq_path(self):
        """Should resolve simple jq path."""
        result = run_script(
            "state-read.py", [self.state_dir, "--jq", ".outputs.framesRendered"]
        )
        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stdout.strip(), "90")

    def test_read_jq_missing(self):
        """Should fail on missing jq path."""
        result = run_script(
            "state-read.py", [self.state_dir, "--jq", ".outputs.missing"]
        )
        self.assertNotEqual(result.returncode, 0)

    def test_missing_state(self):
        """Should fail when state.json does not exist."""
        empty_dir = os.path.join(self.tmpdir, "empty")
        os.makedirs(empty_dir, exist_ok=True)
        result = run_script("state-read.py", [empty_dir])
        self.assertNotEqual(result.returncode, 0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
