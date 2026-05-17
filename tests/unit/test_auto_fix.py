"""Unit tests for bin/auto-fix.py.

Covers:
  - collect_fixable_issues: filtering by fixable + confidence >= 0.8
  - apply_patches: file modification with backup
  - apply_patches dry_run: no file changes
  - rollback_patches: restore from .autofix.bak
  - load_strategy: dynamic import of adjust_wait
  - main: full loop — detect → fix → verify → pass
"""

import importlib.util
import json
import os
import subprocess
import sys
import tempfile
from unittest import mock

BIN_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "bin")

spec = importlib.util.spec_from_file_location("auto_fix", os.path.join(BIN_DIR, "auto-fix.py"))
auto_fix = importlib.util.module_from_spec(spec)
sys.modules["auto_fix"] = auto_fix
spec.loader.exec_module(auto_fix)


def _make_report(status: str, issues: list[dict]) -> dict:
    return {
        "scene": "test",
        "status": status,
        "segments": [{"id": "main", "status": status, "issues": issues}],
    }


def _make_duration_issue(declared: float, computed: float) -> dict:
    return {
        "type": "duration_mismatch",
        "severity": "warning",
        "declared": declared,
        "computed": computed,
        "suggested_lines": [3, 6],
        "fixable": True,
        "fix_confidence": 0.9,
        "fix": {
            "strategy": "adjust_wait",
            "action": "modify_wait_duration",
            "params": {"target_duration": declared},
        },
    }


class TestCollectFixableIssues:
    def test_filters_by_confidence(self):
        report = _make_report(
            "warning",
            [
                {
                    "type": "A",
                    "fixable": True,
                    "fix_confidence": 0.9,
                    "fix": {"strategy": "adjust_wait"},
                },
                {
                    "type": "B",
                    "fixable": True,
                    "fix_confidence": 0.5,
                    "fix": {"strategy": "adjust_wait"},
                },
                {"type": "C", "fixable": False, "fix_confidence": 0.9},
            ],
        )
        result = auto_fix.collect_fixable_issues(report)
        assert len(result) == 1
        assert result[0]["type"] == "A"

    def test_sorts_by_confidence_descending(self):
        report = _make_report(
            "warning",
            [
                {
                    "type": "low",
                    "fixable": True,
                    "fix_confidence": 0.8,
                    "fix": {"strategy": "adjust_wait"},
                },
                {
                    "type": "high",
                    "fixable": True,
                    "fix_confidence": 0.95,
                    "fix": {"strategy": "adjust_wait"},
                },
            ],
        )
        result = auto_fix.collect_fixable_issues(report)
        assert result[0]["type"] == "high"
        assert result[1]["type"] == "low"


class TestApplyPatches:
    def test_modifies_file_and_creates_backup(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
            f.write("line1\nline2\nline3\n")
            path = f.name

        patch = {
            "file": path,
            "line_start": 2,
            "line_end": 2,
            "old_text": "line2\n",
            "new_text": "modified\n",
        }
        auto_fix.apply_patches([patch])

        with open(path, encoding="utf-8") as f:
            content = f.read()
        assert "modified" in content
        assert os.path.isfile(path + ".autofix.bak")

        os.unlink(path)
        os.unlink(path + ".autofix.bak")

    def test_dry_run_does_not_modify(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
            f.write("line1\nline2\n")
            path = f.name

        patch = {
            "file": path,
            "line_start": 2,
            "line_end": 2,
            "old_text": "line2\n",
            "new_text": "modified\n",
        }
        auto_fix.apply_patches([patch], dry_run=True)

        with open(path, encoding="utf-8") as f:
            content = f.read()
        assert "modified" not in content
        assert not os.path.isfile(path + ".autofix.bak")

        os.unlink(path)


class TestRollbackPatches:
    def test_restores_from_backup(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
            f.write("original\n")
            path = f.name

        # Create backup
        import shutil

        shutil.copy2(path, path + ".autofix.bak")

        # Modify file
        with open(path, "w", encoding="utf-8") as f:
            f.write("changed\n")

        patch = {"file": path, "line_start": 1, "line_end": 1, "old_text": "", "new_text": ""}
        auto_fix.rollback_patches([patch])

        with open(path, encoding="utf-8") as f:
            content = f.read()
        assert content == "original\n"

        os.unlink(path)
        os.unlink(path + ".autofix.bak")


class TestLoadStrategy:
    def test_loads_adjust_wait(self):
        mod = auto_fix.load_strategy("adjust_wait")
        assert mod is not None
        assert hasattr(mod, "can_fix")
        assert hasattr(mod, "apply")

    def test_returns_none_for_unknown(self):
        mod = auto_fix.load_strategy("nonexistent")
        assert mod is None


class TestMain:
    def test_no_fixable_issues_exits_0(self):
        report = _make_report("pass", [])
        with tempfile.TemporaryDirectory() as d:
            with mock.patch("auto_fix.subprocess.run") as m:
                m.return_value = subprocess.CompletedProcess(
                    args=[],
                    returncode=0,
                    stdout=json.dumps(report),
                    stderr="",
                )
                with mock.patch.object(sys, "argv", ["auto-fix.py", d]):
                    code = auto_fix.main()
            assert code == 0

    def test_applies_fix_and_verifies(self):
        # Round 1: one fixable issue
        issue = _make_duration_issue(3.0, 4.0)
        report1 = _make_report("warning", [issue])
        # Round 2: all pass
        report2 = _make_report("pass", [])

        with tempfile.TemporaryDirectory() as d:
            scene_file = os.path.join(d, "scene.py")
            with open(scene_file, "w", encoding="utf-8") as f:
                f.write("from manim import *\n\nclass S(Scene):\n")
                f.write("    def construct(self):\n")
                f.write("        self.play(Create(Circle()), run_time=2.0)\n")
                f.write("        self.wait(2.0)\n")

            # Need a manifest.json for check-static to not fail early
            with open(os.path.join(d, "manifest.json"), "w", encoding="utf-8") as f:
                json.dump(
                    {
                        "engine": "manim",
                        "duration": 3,
                        "fps": 30,
                        "resolution": [1920, 1080],
                        "segments": [
                            {"id": "main", "time_range": [0.0, 3.0], "line_start": 3, "line_end": 6}
                        ],
                    },
                    f,
                )

            outputs = [report1, report2, report2]
            call_idx = [0]

            def fake_run(cmd, **kwargs):
                if any("check-static.py" in str(arg) for arg in cmd):
                    idx = call_idx[0]
                    call_idx[0] += 1
                    out = outputs[idx]
                    return subprocess.CompletedProcess(
                        args=cmd,
                        returncode=1 if out.get("status") != "pass" else 0,
                        stdout=json.dumps(out),
                        stderr="",
                    )
                return subprocess.CompletedProcess(args=cmd, returncode=0, stdout="", stderr="")

            with mock.patch("auto_fix.subprocess.run", side_effect=fake_run):
                with mock.patch.object(sys, "argv", ["auto-fix.py", d]):
                    code = auto_fix.main()

            assert code == 0
            with open(scene_file, encoding="utf-8") as f:
                content = f.read()
            assert "self.wait(1.0)" in content

    def test_dry_run_does_not_modify(self):
        issue = _make_duration_issue(3.0, 4.0)
        report = _make_report("warning", [issue])

        with tempfile.TemporaryDirectory() as d:
            scene_file = os.path.join(d, "scene.py")
            with open(scene_file, "w", encoding="utf-8") as f:
                f.write("from manim import *\n\nclass S(Scene):\n")
                f.write("    def construct(self):\n")
                f.write("        self.wait(2.0)\n")

            with open(os.path.join(d, "manifest.json"), "w", encoding="utf-8") as f:
                json.dump(
                    {
                        "engine": "manim",
                        "duration": 3,
                        "fps": 30,
                        "resolution": [1920, 1080],
                        "segments": [
                            {"id": "main", "time_range": [0.0, 3.0], "line_start": 3, "line_end": 5}
                        ],
                    },
                    f,
                )

            def fake_run(cmd, **kwargs):
                if any("check-static.py" in str(arg) for arg in cmd):
                    return subprocess.CompletedProcess(
                        args=cmd,
                        returncode=1,
                        stdout=json.dumps(report),
                        stderr="",
                    )
                return subprocess.CompletedProcess(args=cmd, returncode=0, stdout="", stderr="")

            with mock.patch("auto_fix.subprocess.run", side_effect=fake_run):
                with mock.patch.object(sys, "argv", ["auto-fix.py", d, "--dry-run"]):
                    code = auto_fix.main()

            assert code == 1  # issue remains
            with open(scene_file, encoding="utf-8") as f:
                content = f.read()
            assert "self.wait(2.0)" in content  # unchanged
