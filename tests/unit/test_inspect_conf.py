"""Unit tests for bin/inspect-conf.py.

Covers:
  - Missing file fallback
  - yaml.safe_load parsing
  - Partial field coverage
  - Integer type coercion
  - scene_extensions (list and flow / bracket string)
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
    with tempfile.NamedTemporaryFile(mode="w", suffix=".conf", delete=False, encoding="utf-8") as f:
        f.write(content)
        return f.name


# ---------------------------------------------------------------------------
# parse_engine_conf
# ---------------------------------------------------------------------------

class TestParseEngineConf:
    def test_missing_file_returns_defaults(self):
        result = inspect_conf.parse_engine_conf("/nonexistent/path/engine.conf")
        assert result == {"scene_extensions": [".py"], "mode": "batch"}

    def test_full_conf(self):
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

        try:
            result = inspect_conf.parse_engine_conf(conf)
        finally:
            os.unlink(conf)

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

    def test_flow_style_scene_extensions(self):
        conf = _make_conf("""
name: manim
mode: batch
scene_extensions: [.py]
render_script: engines/manim/scripts/render.sh
service_port_min: 3000
service_port_max: 4000
""")

        try:
            result = inspect_conf.parse_engine_conf(conf)
        finally:
            os.unlink(conf)

        assert result["scene_extensions"] == [".py"]
        assert result["mode"] == "batch"
        assert result["render_script"] == "engines/manim/scripts/render.sh"
        assert result["service_port_min"] == 3000
        assert result["service_port_max"] == 4000

    def test_partial_fields(self):
        conf = _make_conf("""
mode: interactive
scene_extensions:
  - .py
""")
        try:
            result = inspect_conf.parse_engine_conf(conf)
        finally:
            os.unlink(conf)

        assert result["mode"] == "interactive"
        assert result["scene_extensions"] == [".py"]
        assert "render_script" not in result
        assert "service_port_min" not in result

    def test_scene_extensions_multiline_yaml(self):
        conf = _make_conf("""
scene_extensions:
  - .glsl
  - .vert
  - .frag
""")
        try:
            result = inspect_conf.parse_engine_conf(conf)
        finally:
            os.unlink(conf)

        assert result["scene_extensions"] == [".glsl", ".vert", ".frag"]
        assert result["mode"] == "batch"

    def test_integer_field_string_rejected(self):
        conf = _make_conf("""
mode: batch
scene_extensions: [.py]
service_port_min: not_a_number
""")
        try:
            result = inspect_conf.parse_engine_conf(conf)
        finally:
            os.unlink(conf)

        assert "service_port_min" not in result

    def test_empty_scene_extensions_defaults_to_py(self):
        conf = _make_conf("""
mode: batch
""")
        try:
            result = inspect_conf.parse_engine_conf(conf)
        finally:
            os.unlink(conf)

        assert result["scene_extensions"] == [".py"]
        assert result["mode"] == "batch"

    def test_empty_file_uses_defaults_for_extensions(self):
        conf = _make_conf("")
        try:
            result = inspect_conf.parse_engine_conf(conf)
        finally:
            os.unlink(conf)

        assert result["scene_extensions"] == [".py"]
        assert result["mode"] == "batch"


# ---------------------------------------------------------------------------
# main / CLI
# ---------------------------------------------------------------------------

class TestMain:
    def test_main_prints_json(self, capsys):
        conf = _make_conf("mode: batch\nscene_extensions: [.py]\n")
        try:
            with mock.patch.object(sys, "argv", ["inspect-conf.py", conf]):
                inspect_conf.main()
        finally:
            os.unlink(conf)

        captured = capsys.readouterr()
        parsed = json.loads(captured.out)
        assert parsed["mode"] == "batch"
        assert parsed["scene_extensions"] == [".py"]

    def test_main_invalid_yaml_exits(self):
        conf = _make_conf("scene_extensions: [\n  - .py\n# bad indentation or broken")
        try:
            with mock.patch.object(sys, "argv", ["inspect-conf.py", conf]):
                with pytest.raises(SystemExit) as exc_info:
                    inspect_conf.main()
            assert exc_info.value.code == 1
        finally:
            os.unlink(conf)

    def test_main_missing_arg_exits(self):
        with mock.patch.object(sys, "argv", ["inspect-conf.py"]):
            with pytest.raises(SystemExit) as exc_info:
                inspect_conf.main()
            assert exc_info.value.code == 1
