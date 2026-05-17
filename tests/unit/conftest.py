"""Pytest fixtures and shared utilities for unit tests."""

import importlib.util
import json
import os
import sys
import tempfile

import pytest

# Allow importing bin/*.py modules (filenames with hyphens require importlib)
BIN_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "bin")
PROJECT_ROOT = os.path.join(os.path.dirname(__file__), "..", "..")
if BIN_DIR not in sys.path:
    sys.path.insert(0, BIN_DIR)


def _load_bin_module(name: str, filename: str):
    """Load a module from bin/ by its filename."""
    path = os.path.join(BIN_DIR, filename)
    if not os.path.isfile(path):
        raise FileNotFoundError(f"Module file not found: {path}")
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    # Ensure sys.modules contains the module so relative imports work if needed
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="session")
def bin_modules():
    """Lazy-loaded bin modules available to all tests."""

    class Modules:
        pass

    mods = Modules()
    return mods


@pytest.fixture
def tmp_scene_dir():
    """Create a temporary scene directory with a valid manifest.json.

    Yields the directory path. Automatically cleaned up after test.
    """
    with tempfile.TemporaryDirectory() as tmp:
        scene_dir = os.path.join(tmp, "test_scene")
        os.makedirs(scene_dir)
        manifest = {
            "version": "1.0",
            "engine": "manim",
            "fps": 30,
            "duration": 1.0,
        }
        with open(os.path.join(scene_dir, "manifest.json"), "w", encoding="utf-8") as f:
            json.dump(manifest, f)
        yield scene_dir


@pytest.fixture
def tmp_project_with_shaders(tmp_scene_dir):
    """Create a temporary project structure with scene + shader assets.

    Returns dict with keys: scene_dir, assets_dir, project_root.
    """
    project_root = os.path.join(tmp_scene_dir, "..", "project")
    assets_dir = os.path.join(project_root, "assets", "shaders")
    os.makedirs(assets_dir, exist_ok=True)

    # Update scene manifest to reference a shader
    manifest_path = os.path.join(tmp_scene_dir, "manifest.json")
    with open(manifest_path, encoding="utf-8") as f:
        manifest = json.load(f)
    manifest["shaders"] = ["test_shader"]
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f)

    # Create shader asset
    shader_dir = os.path.join(assets_dir, "test_shader")
    os.makedirs(shader_dir)
    with open(os.path.join(shader_dir, "main.glsl"), "w", encoding="utf-8") as f:
        f.write("void main() { gl_FragColor = vec4(1.0); }\n")
    with open(os.path.join(shader_dir, "manifest.json"), "w", encoding="utf-8") as f:
        json.dump({"name": "test_shader"}, f)

    return {
        "scene_dir": tmp_scene_dir,
        "assets_dir": assets_dir,
        "project_root": project_root,
    }


@pytest.fixture(autouse=True)
def _preserve_cwd():
    """Defensive: snapshot cwd before each test and restore after.

    Some legacy tests use ``os.chdir(tmpdir)`` without try/finally, leaving the
    process cwd pointing at a deleted directory. This fixture isolates that damage
    to the offending test only, so later tests don't blow up on ``os.getcwd()``.
    """
    try:
        orig = os.getcwd()
    except FileNotFoundError:
        orig = os.path.dirname(os.path.abspath(__file__))
        os.chdir(orig)
    try:
        yield
    finally:
        try:
            os.chdir(orig)
        except (FileNotFoundError, OSError):
            pass
