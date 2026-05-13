"""Unit tests for pipeline._render._paths shared helpers (S7-CLEAN-2)."""

from __future__ import annotations

import json
import os
import socket
import sys

import pytest

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if REPO not in sys.path:
    sys.path.insert(0, REPO)

from pipeline._render import _paths  # noqa: E402


def test_read_manifest_returns_dict(tmp_path):
    p = tmp_path / "manifest.json"
    p.write_text(json.dumps({"engine": "manim", "fps": 30}), encoding="utf-8")
    data = _paths.read_manifest(str(p))
    assert data["engine"] == "manim"
    assert data["fps"] == 30


def test_read_manifest_raises_on_missing(tmp_path):
    with pytest.raises(FileNotFoundError):
        _paths.read_manifest(str(tmp_path / "nope.json"))


def test_locate_scene_file_first_match(tmp_path):
    (tmp_path / "scene.py").write_text("# scene", encoding="utf-8")
    (tmp_path / "scene.tsx").write_text("// scene", encoding="utf-8")
    # First extension wins
    assert _paths.locate_scene_file(str(tmp_path), [".tsx", ".py"]).endswith("scene.tsx")
    assert _paths.locate_scene_file(str(tmp_path), [".py", ".tsx"]).endswith("scene.py")


def test_locate_scene_file_returns_empty_when_missing(tmp_path):
    assert _paths.locate_scene_file(str(tmp_path), [".py", ".tsx"]) == ""


def test_find_free_port_returns_in_range():
    port = _paths.find_free_port(50001, 50050)
    assert 50001 <= port <= 50050
    # Port should actually be available right after the call
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", port))


def test_find_free_port_raises_when_exhausted():
    # Reserve a single port, then ask for that port only.
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]
        s.listen(1)
        with pytest.raises(RuntimeError):
            _paths.find_free_port(port, port)


def test_scene_inherits_from_zoned(tmp_path):
    src = tmp_path / "scene.py"
    src.write_text(
        "from manim import Scene\nclass Foo(ZoneScene):\n    pass\n", encoding="utf-8"
    )
    assert _paths.scene_inherits_from(str(src), ["ZoneScene"]) is True


def test_scene_inherits_from_returns_false_on_syntax_error(tmp_path):
    src = tmp_path / "broken.py"
    src.write_text("def (((", encoding="utf-8")
    assert _paths.scene_inherits_from(str(src), ["ZoneScene"]) is False
