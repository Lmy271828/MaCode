"""Unit tests for bin/api-gate.py.

Covers:
  - _path_to_module: path normalization, dynamic paths, edge cases
  - check_scene_content: blacklist import detection
  - check_sandbox: dangerous call detection
  - check_syntax_gate: raw syntax pattern detection
  - load_blacklist: JSON and Markdown parsing
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


class TestCheckSandbox:
    def test_detects_subprocess(self):
        v = api_gate.check_sandbox("import subprocess\n")
        assert any("subprocess" in x for x in v)

    def test_detects_os_system(self):
        v = api_gate.check_sandbox("os.system('rm -rf /')\n")
        assert any("os.system" in x for x in v)

    def test_detects_socket(self):
        v = api_gate.check_sandbox("import socket\n")
        assert any("socket" in x for x in v)

    def test_detects_shutil_rmtree(self):
        v = api_gate.check_sandbox("shutil.rmtree('/tmp')\n")
        assert any("shutil.rmtree" in x for x in v)

    def test_allows_safe_code(self):
        v = api_gate.check_sandbox("import numpy as np\n")
        assert len(v) == 0


class TestCheckSyntaxGate:
    def test_detects_handwritten_ffmpeg_vf(self):
        code = 'cmd = "ffmpeg -i in.mp4 -vf \\"blur\\" out.mp4"\n'
        v = api_gate.check_syntax_gate(code, "scene.py")
        assert any("ffmpeg" in d for d, _, _ in v)

    def test_detects_latex_cases(self):
        code = r"eq = r'\begin{cases} x \\ y \end{cases}'"
        v = api_gate.check_syntax_gate(code, "scene.py")
        assert any("LaTeX cases" in d for d, _, _ in v)

    def test_detects_glsl_code(self):
        code = "shader = 'gl_Position = vec4(1.0);'\n"
        v = api_gate.check_syntax_gate(code, "scene.py")
        assert any("GLSL" in d for d, _, _ in v)

    def test_allows_safe_code(self):
        code = "import numpy as np\n"
        v = api_gate.check_syntax_gate(code, "scene.py")
        assert len(v) == 0


class TestLoadBlacklist:
    def test_json_sourcemap(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            os.chdir(tmpdir)
            os.makedirs(".agent/context", exist_ok=True)
            data = {"blacklist": [{"path_raw": "manimlib/"}, {"path_raw": "mobject/types/"}]}
            with open(".agent/context/manim_sourcemap.json", "w") as f:
                json.dump(data, f)

            sm_path = os.path.join(tmpdir, "engines", "manim", "SOURCEMAP.md")
            os.makedirs(os.path.dirname(sm_path), exist_ok=True)
            open(sm_path, "w").close()

            result = api_gate.load_blacklist(sm_path)
            modules = [m for _, m in result]
            assert "manimlib" in modules
            assert "mobject.types" in modules

    def test_markdown_fallback(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            sm_path = os.path.join(tmpdir, "SOURCEMAP.md")
            with open(sm_path, "w") as f:
                f.write("## BLACKLIST: forbidden\n")
                f.write("| 标识 | 路径/命令 | 说明 |\n")
                f.write("|---|---|---|\n")
                f.write("| bad | `manimlib/` | old api |\n")
                f.write("| bad | `mobject/types/` | internal |\n")

            with mock.patch("os.path.exists", return_value=False):
                result = api_gate.load_blacklist(sm_path)
            modules = [m for _, m in result]
            assert "manimlib" in modules
            assert "mobject.types" in modules

    def test_missing_sourcemap_exits(self):
        with pytest.raises(SystemExit) as exc_info:
            api_gate.load_blacklist("/nonexistent/SOURCEMAP.md")
        assert exc_info.value.code == 2


class TestMain:
    def test_clean_scene_exits_0(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            scene = os.path.join(tmpdir, "scene.py")
            with open(scene, "w") as f:
                f.write("import numpy as np\n")
            sm = os.path.join(tmpdir, "SOURCEMAP.md")
            with open(sm, "w") as f:
                f.write("## BLACKLIST\n")

            with mock.patch.object(sys, "argv", ["api-gate.py", scene, sm]):
                with pytest.raises(SystemExit) as exc_info:
                    api_gate.main()
                assert exc_info.value.code == 0

    def test_violation_scene_exits_1(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            scene = os.path.join(tmpdir, "scene.py")
            with open(scene, "w") as f:
                f.write("import subprocess\n")
            sm = os.path.join(tmpdir, "SOURCEMAP.md")
            with open(sm, "w") as f:
                f.write("## BLACKLIST\n")

            with mock.patch.object(sys, "argv", ["api-gate.py", scene, sm]):
                with pytest.raises(SystemExit) as exc_info:
                    api_gate.main()
                assert exc_info.value.code == 1

    def test_missing_scene_exits_2(self):
        sm = os.path.join(tempfile.gettempdir(), "SOURCEMAP.md")
        with open(sm, "w") as f:
            f.write("## BLACKLIST\n")

        with mock.patch.object(sys, "argv", ["api-gate.py", "/nonexistent/scene.py", sm]):
            with pytest.raises(SystemExit) as exc_info:
                api_gate.main()
            assert exc_info.value.code == 2
