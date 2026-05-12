"""Unit tests for bin/copilot-feedback.py.

Uses mocking to avoid real terminal I/O.
Covers:
  - Normal feedback collection (Ctrl+F -> record -> exit 0)
  - Engine process already exited (immediate exit 0)
  - Missing arguments (exit 1)
"""

import importlib.util
import json
import os
import sys
import tempfile
from unittest import mock

import pytest

BIN_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "bin")

spec = importlib.util.spec_from_file_location("copilot_feedback", os.path.join(BIN_DIR, "copilot-feedback.py"))
copilot_feedback = importlib.util.module_from_spec(spec)
sys.modules["copilot_feedback"] = copilot_feedback
spec.loader.exec_module(copilot_feedback)


class FakeStdin:
    """Mock stdin supporting read(1), readline(), and fileno()."""

    def __init__(self, chars):
        self._chars = iter(chars)

    def read(self, n):
        buf = []
        for _ in range(n):
            try:
                buf.append(next(self._chars))
            except StopIteration:
                break
        return "".join(buf)

    def readline(self):
        buf = []
        for ch in self._chars:
            buf.append(ch)
            if ch == "\n":
                break
        return "".join(buf)

    def fileno(self):
        return 0


class TestCopilotFeedback:
    def test_records_feedback_on_ctrl_f(self):
        # Ctrl+F (\x06) followed by feedback text + newline
        stdin = FakeStdin("\x06bad animation\n")

        with tempfile.TemporaryDirectory() as tmpdir:
            os.chdir(tmpdir)
            os.makedirs(".agent/signals", exist_ok=True)

            frames_dir = os.path.join(tmpdir, "frames")
            os.makedirs(frames_dir)
            open(os.path.join(frames_dir, "frame_0001.png"), "w").close()

            with mock.patch("sys.stdin", stdin), \
                 mock.patch("termios.tcgetattr", return_value={"old": True}), \
                 mock.patch("tty.setcbreak"), \
                 mock.patch("termios.tcsetattr"), \
                 mock.patch("select.select", side_effect=[
                     ([stdin], [], []),   # 1st loop: input available
                     ([], [], []),        # 2nd loop: no input
                 ]), \
                 mock.patch("os.kill", side_effect=[None, None, ProcessLookupError]), \
                 mock.patch.object(sys, "argv", ["copilot-feedback.py", "test_scene", frames_dir, "99999"]):
                copilot_feedback.main()

            with open(".agent/signals/frame_feedback.jsonl", encoding="utf-8") as f:
                record = json.loads(f.readline())

            assert record["scene"] == "test_scene"
            assert record["frame"] == 1
            assert record["feedback"] == "bad animation"
            assert "timestamp" in record

    def test_exits_when_engine_already_gone(self):
        stdin = FakeStdin("")

        with tempfile.TemporaryDirectory() as tmpdir:
            os.chdir(tmpdir)
            os.makedirs(".agent/signals", exist_ok=True)

            with mock.patch("sys.stdin", stdin), \
                 mock.patch("termios.tcgetattr", return_value={"old": True}), \
                 mock.patch("tty.setcbreak"), \
                 mock.patch("termios.tcsetattr"), \
                 mock.patch("select.select", return_value=([], [], [])), \
                 mock.patch("os.kill", side_effect=ProcessLookupError), \
                 mock.patch.object(sys, "argv", ["copilot-feedback.py", "test_scene", "/tmp/frames", "99999"]):
                copilot_feedback.main()

            # No feedback file should be created
            assert not os.path.isfile(".agent/signals/frame_feedback.jsonl")

    def test_missing_args_exits(self):
        with mock.patch.object(sys, "argv", ["copilot-feedback.py"]):
            with pytest.raises(SystemExit) as exc_info:
                copilot_feedback.main()
            assert exc_info.value.code == 1

    def test_multiple_frames_counted_correctly(self):
        stdin = FakeStdin("\x06frame looks wrong\n")

        with tempfile.TemporaryDirectory() as tmpdir:
            os.chdir(tmpdir)
            os.makedirs(".agent/signals", exist_ok=True)

            frames_dir = os.path.join(tmpdir, "frames")
            os.makedirs(frames_dir)
            for i in range(5):
                open(os.path.join(frames_dir, f"frame_{i:04d}.png"), "w").close()

            with mock.patch("sys.stdin", stdin), \
                 mock.patch("termios.tcgetattr", return_value={"old": True}), \
                 mock.patch("tty.setcbreak"), \
                 mock.patch("termios.tcsetattr"), \
                 mock.patch("select.select", side_effect=[
                     ([stdin], [], []),
                     ([], [], []),
                 ]), \
                 mock.patch("os.kill", side_effect=[None, None, ProcessLookupError]), \
                 mock.patch.object(sys, "argv", ["copilot-feedback.py", "test_scene", frames_dir, "99999"]):
                copilot_feedback.main()

            with open(".agent/signals/frame_feedback.jsonl", encoding="utf-8") as f:
                record = json.loads(f.readline())

            assert record["frame"] == 5
