"""Unit tests for bin/api-gate.py.

Covers:
  - _path_to_module: path normalization, dynamic paths, edge cases
  - check_python_imports: blacklist import detection
  - load_blacklist: engines/{engine}/sourcemap.json only
  - main: CLI exit codes
"""

import importlib.util
import json
import os
import sys
import tempfile
from unittest import mock

import pytest

BIN_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "bin")

spec = importlib.util.spec_from_file_location("api_gate", os.path.join(BIN_DIR, "api-gate.py"))
api_gate = importlib.util.module_from_spec(spec)
sys.modules["api_gate"] = api_gate
spec.loader.exec_module(api_gate)


class TestPathToModule:
    def test_simple_path(self):
        assert api_gate._path_to_module("manimlib/") == "manimlib"

    def test_nested_path(self):
        assert api_gate._path_to_module("mobject/types/") == "mobject.types"

    def test_dynamic_path(self):
        assert api_gate._path_to_module('$(python -c "...")/_config/') == "_config"

    def test_dynamic_nested(self):
        assert api_gate._path_to_module('$(python -c "...")/mobject/types/') == "mobject.types"

    def test_quoted_path(self):
        assert api_gate._path_to_module('"manimlib"') == "manimlib"

    def test_hidden_path_returns_none(self):
        assert api_gate._path_to_module(".agent/tmp/") is None

    def test_node_modules_returns_none(self):
        assert api_gate._path_to_module("node_modules/foo/") is None

    def test_empty_returns_none(self):
        assert api_gate._path_to_module("") is None

    def test_dot_returns_none(self):
        assert api_gate._path_to_module(".") is None


class TestCheckPythonImports:
    def test_detects_blacklisted_import(self):
        code = "import manimlib\n"
        blacklist = [("manimlib/", "manimlib")]
        v = api_gate.check_python_imports(code, blacklist)
        assert len(v) == 1
        assert "manimlib" in v[0]

    def test_detects_from_import(self):
        code = "from manimlib import Scene\n"
        blacklist = [("manimlib/", "manimlib")]
        v = api_gate.check_python_imports(code, blacklist)
        assert len(v) == 1

    def test_detects_submodule_import(self):
        code = "import foo.manimlib.bar\n"
        blacklist = [("manimlib/", "manimlib")]
        v = api_gate.check_python_imports(code, blacklist)
        assert len(v) == 1

    def test_allows_whitelisted_import(self):
        code = "import numpy\n"
        blacklist = [("manimlib/", "manimlib")]
        v = api_gate.check_python_imports(code, blacklist)
        assert len(v) == 0

    def test_empty_blacklist_no_violations(self):
        code = "import anything\n"
        v = api_gate.check_python_imports(code, [])
        assert len(v) == 0


class TestLoadBlacklist:
    def test_loads_from_sourcemap_json(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            jp = os.path.join(tmpdir, "engines", "manim", "sourcemap.json")
            os.makedirs(os.path.dirname(jp), exist_ok=True)
            data = {"blacklist": [{"path_raw": "manimlib/"}, {"path_raw": "mobject/types/"}]}
            with open(jp, "w", encoding="utf-8") as f:
                json.dump(data, f)

            result = api_gate.load_blacklist(jp)
            modules = [m for _, m in result]
            assert "manimlib" in modules
            assert "mobject.types" in modules

    def test_engine_mismatch_exit_2(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            jp = os.path.join(tmpdir, "engines", "manim", "sourcemap.json")
            os.makedirs(os.path.dirname(jp), exist_ok=True)
            with open(jp, "w", encoding="utf-8") as f:
                json.dump({"blacklist": []}, f)
            with pytest.raises(SystemExit) as exc_info:
                api_gate.load_blacklist(jp, engine_cli="manimgl")
            assert exc_info.value.code == 2

    def test_path_not_inferable_without_engine_exit_2(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            jp = os.path.join(tmpdir, "sourcemap.json")
            open(jp, "w", encoding="utf-8").write("{}")
            with pytest.raises(SystemExit) as exc_info:
                api_gate.load_blacklist(jp)
            assert exc_info.value.code == 2

    def test_non_inferable_ok_with_matching_engine_cli(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            jp = os.path.join(tmpdir, "sourcemap.json")
            with open(jp, "w", encoding="utf-8") as f:
                json.dump({"blacklist": [{"path_raw": "badpkg/"}]}, f)
            result = api_gate.load_blacklist(jp, engine_cli="manim")
            assert any(m == "badpkg" for _, m in result)

    def test_missing_sourcemap_exits(self):
        with pytest.raises(SystemExit) as exc_info:
            api_gate.load_blacklist("/nonexistent/engines/manim/sourcemap.json")
        assert exc_info.value.code == 2


class TestMain:
    def _write_sourcemap(self, tmpdir, engine="manim", blacklist=None):
        jp = os.path.join(tmpdir, "engines", engine, "sourcemap.json")
        os.makedirs(os.path.dirname(jp), exist_ok=True)
        with open(jp, "w", encoding="utf-8") as f:
            json.dump({"blacklist": blacklist or []}, f)
        return jp

    def test_clean_scene_exits_0(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            scene = os.path.join(tmpdir, "scene.py")
            with open(scene, "w", encoding="utf-8") as f:
                f.write("import numpy as np\n")
            sm = self._write_sourcemap(tmpdir)
            with mock.patch.object(sys, "argv", ["api-gate.py", scene, sm]):
                with pytest.raises(SystemExit) as exc_info:
                    api_gate.main()
                assert exc_info.value.code == 0

    def test_violation_scene_exits_1(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            scene = os.path.join(tmpdir, "scene.py")
            with open(scene, "w", encoding="utf-8") as f:
                f.write("import manimlib\n")
            sm = self._write_sourcemap(tmpdir, blacklist=[{"path_raw": "manimlib"}])
            with mock.patch.object(sys, "argv", ["api-gate.py", scene, sm]):
                with pytest.raises(SystemExit) as exc_info:
                    api_gate.main()
                assert exc_info.value.code == 1

    def test_missing_scene_exits_2(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            sm = self._write_sourcemap(tmpdir)
            with mock.patch.object(sys, "argv", ["api-gate.py", "/nonexistent/scene.py", sm]):
                with pytest.raises(SystemExit) as exc_info:
                    api_gate.main()
                assert exc_info.value.code == 2
