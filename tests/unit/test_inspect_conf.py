"""Unit tests for bin/inspect-conf.py.

Covers:
  - Missing file fallback
  - yq parsing path (primary)
  - grep/awk fallback path
  - Partial field coverage
  - Integer type coercion
  - scene_extensions multiple formats
"""

import importlib.util
import json
import os
import sys
import tempfile
from unittest import mock

import pytest

BIN_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "bin")

spec = importlib.util.spec_from_file_location("inspect_conf", os.path.join(BIN_DIR, "inspect-conf.py"))
inspect_conf = importlib.util.module_from_spec(spec)
sys.modules["inspect_conf"] = inspect_conf
spec.loader.exec_module(inspect_conf)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_conf(content: str) -> str:
    with tempfile.NamedTemporaryFile(mode="w", suffix=".conf", delete=False) as f:
        f.write(content)
        return f.name


# ---------------------------------------------------------------------------
# parse_engine_conf
# ---------------------------------------------------------------------------

class TestParseEngineConf:
    def test_missing_file_returns_defaults(self):
        result = inspect_conf.parse_engine_conf("/nonexistent/path/engine.conf")
        assert result == {"scene_extensions": [".py"], "mode": "batch"}

    def test_yq_path_full_conf(self):
        conf = _make_conf("""
name: motion_canvas
mode: batch
scene_extensions:
  - .tsx
  - .ts
render_script: engines/mc/scripts/render.mjs
pre_render_script: engines/mc/scripts/pre.mjs
service_script: engines/mc/scripts/serve.mjs
inspect_script: engines/mc/scripts/inspect.sh
validate_script: engines/mc/scripts/validate.sh
sourcemap: engines/mc/SOURCEMAP.md
service_port_min: 4567
service_port_max: 5999
""")

        def fake_yq(cmd, **kwargs):
            # cmd = ['yq', '-r', query, path]
            query = cmd[2]
            stdout = ""
            if 'scene_extensions[]' in query:
                stdout = ".tsx\n.ts\n"
            elif query == '.mode // "batch"':
                stdout = "batch\n"
            elif query == '.render_script // ""':
                stdout = "engines/mc/scripts/render.mjs\n"
            elif query == '.pre_render_script // ""':
                stdout = "engines/mc/scripts/pre.mjs\n"
            elif query == '.service_script // ""':
                stdout = "engines/mc/scripts/serve.mjs\n"
            elif query == '.inspect_script // ""':
                stdout = "engines/mc/scripts/inspect.sh\n"
            elif query == '.validate_script // ""':
                stdout = "engines/mc/scripts/validate.sh\n"
            elif query == '.sourcemap // ""':
                stdout = "engines/mc/SOURCEMAP.md\n"
            elif query == '.service_port_min // ""':
                stdout = "4567\n"
            elif query == '.service_port_max // ""':
                stdout = "5999\n"
            return mock.Mock(returncode=0, stdout=stdout, stderr="")

        with mock.patch("subprocess.run", side_effect=fake_yq):
            result = inspect_conf.parse_engine_conf(conf)

        assert result["scene_extensions"] == [".tsx", ".ts"]
        assert result["mode"] == "batch"
        assert result["render_script"] == "engines/mc/scripts/render.mjs"
        assert result["pre_render_script"] == "engines/mc/scripts/pre.mjs"
        assert result["service_script"] == "engines/mc/scripts/serve.mjs"
        assert result["inspect_script"] == "engines/mc/scripts/inspect.sh"
        assert result["validate_script"] == "engines/mc/scripts/validate.sh"
        assert result["sourcemap"] == "engines/mc/SOURCEMAP.md"
        assert result["service_port_min"] == 4567
        assert result["service_port_max"] == 5999
        os.unlink(conf)

    def test_yq_unavailable_uses_grep_fallback(self):
        conf = _make_conf("""
name: manim
mode: batch
scene_extensions: [.py]
render_script: engines/manim/scripts/render.sh
service_port_min: 3000
service_port_max: 4000
""")

        def fake_subprocess(cmd, **kwargs):
            # yq calls raise FileNotFoundError; grep/awk calls succeed
            if cmd[0] == "yq":
                raise FileNotFoundError("yq not found")
            if cmd[0] == "grep":
                pattern = cmd[2]
                stdout = ""
                if "scene_extensions" in pattern:
                    stdout = "[.py]"
                elif "^mode:" in pattern:
                    stdout = "batch"
                elif "render_script" in pattern:
                    stdout = "engines/manim/scripts/render.sh"
                elif "service_port_min" in pattern:
                    stdout = "3000"
                elif "service_port_max" in pattern:
                    stdout = "4000"
                return mock.Mock(returncode=0, stdout=stdout, stderr="")
            if cmd[0] == "awk":
                return mock.Mock(returncode=1, stdout="", stderr="")
            return mock.Mock(returncode=1, stdout="", stderr="")

        with mock.patch("subprocess.run", side_effect=fake_subprocess):
            result = inspect_conf.parse_engine_conf(conf)

        assert result["scene_extensions"] == [".py"]
        assert result["mode"] == "batch"
        assert result["render_script"] == "engines/manim/scripts/render.sh"
        assert result["service_port_min"] == 3000
        assert result["service_port_max"] == 4000
        os.unlink(conf)

    def test_partial_fields(self):
        conf = _make_conf("""
mode: interactive
scene_extensions:
  - .py
""")

        def fake_yq(cmd, **kwargs):
            query = cmd[2]
            stdout = ""
            if 'scene_extensions[]' in query:
                stdout = ".py\n"
            elif query == '.mode // "batch"':
                stdout = "interactive\n"
            return mock.Mock(returncode=0, stdout=stdout, stderr="")

        with mock.patch("subprocess.run", side_effect=fake_yq):
            result = inspect_conf.parse_engine_conf(conf)

        assert result["mode"] == "interactive"
        assert result["scene_extensions"] == [".py"]
        assert "render_script" not in result
        assert "service_port_min" not in result
        os.unlink(conf)

    def test_scene_extensions_multiline_yaml(self):
        conf = _make_conf("""
scene_extensions:
  - .glsl
  - .vert
  - .frag
""")

        def fake_yq(cmd, **kwargs):
            if 'scene_extensions[]' in cmd[2]:
                return mock.Mock(returncode=0, stdout=".glsl\n.vert\n.frag\n", stderr="")
            return mock.Mock(returncode=0, stdout="", stderr="")

        with mock.patch("subprocess.run", side_effect=fake_yq):
            result = inspect_conf.parse_engine_conf(conf)

        assert result["scene_extensions"] == [".glsl", ".vert", ".frag"]
        os.unlink(conf)

    def test_grep_fallback_multiline_extensions(self):
        conf = _make_conf("""
scene_extensions:
  - .tsx
  - .mc
""")

        def fake_subprocess(cmd, **kwargs):
            if cmd[0] == "yq":
                raise FileNotFoundError("yq not found")
            if cmd[0] == "grep":
                return mock.Mock(returncode=1, stdout="", stderr="")
            if cmd[0] == "awk":
                return mock.Mock(returncode=0, stdout=".tsx\n.mc\n", stderr="")
            return mock.Mock(returncode=1, stdout="", stderr="")

        with mock.patch("subprocess.run", side_effect=fake_subprocess):
            result = inspect_conf.parse_engine_conf(conf)

        assert result["scene_extensions"] == [".tsx", ".mc"]
        os.unlink(conf)

    def test_integer_field_string_rejected(self):
        conf = _make_conf("""
mode: batch
scene_extensions: [.py]
service_port_min: not_a_number
""")

        def fake_yq(cmd, **kwargs):
            query = cmd[2]
            stdout = ""
            if 'scene_extensions[]' in query:
                stdout = ".py\n"
            elif query == '.mode // "batch"':
                stdout = "batch\n"
            elif 'service_port_min' in query:
                stdout = "not_a_number\n"
            return mock.Mock(returncode=0, stdout=stdout, stderr="")

        with mock.patch("subprocess.run", side_effect=fake_yq):
            result = inspect_conf.parse_engine_conf(conf)

        assert "service_port_min" not in result
        os.unlink(conf)

    def test_empty_scene_extensions_defaults_to_py(self):
        conf = _make_conf("""
mode: batch
""")

        def fake_yq(cmd, **kwargs):
            query = cmd[2]
            stdout = ""
            if 'scene_extensions[]' in query:
                stdout = ""
            elif query == '.mode // "batch"':
                stdout = "batch\n"
            return mock.Mock(returncode=0, stdout=stdout, stderr="")

        with mock.patch("subprocess.run", side_effect=fake_yq):
            result = inspect_conf.parse_engine_conf(conf)

        assert result["scene_extensions"] == [".py"]
        os.unlink(conf)


# ---------------------------------------------------------------------------
# main / CLI
# ---------------------------------------------------------------------------

class TestMain:
    def test_main_prints_json(self, capsys):
        conf = _make_conf("mode: batch\nscene_extensions: [.py]\n")

        def fake_yq(cmd, **kwargs):
            query = cmd[2]
            stdout = ""
            if 'scene_extensions[]' in query:
                stdout = ".py\n"
            elif query == '.mode // "batch"':
                stdout = "batch\n"
            return mock.Mock(returncode=0, stdout=stdout, stderr="")

        with mock.patch("subprocess.run", side_effect=fake_yq):
            with mock.patch.object(sys, "argv", ["inspect-conf.py", conf]):
                inspect_conf.main()

        captured = capsys.readouterr()
        parsed = json.loads(captured.out)
        assert parsed["mode"] == "batch"
        assert parsed["scene_extensions"] == [".py"]
        os.unlink(conf)

    def test_main_missing_arg_exits(self):
        with mock.patch.object(sys, "argv", ["inspect-conf.py"]):
            with pytest.raises(SystemExit) as exc_info:
                inspect_conf.main()
            assert exc_info.value.code == 1
