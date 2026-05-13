"""Unit tests for bin/macode-hash.

Covers:
  - Transitive import resolution
  - sys.path heuristic detection
  - Exclusion of external packages (e.g. numpy)
  - Hash determinism
  - Hash sensitivity to deep dependency changes
  - --deps-json output format
"""

from __future__ import annotations

import importlib.util
import json
import os
import sys
import tempfile

import pytest

BIN_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "bin")
PROJECT_ROOT = os.path.dirname(BIN_DIR)

# Load macode-hash as a module (no .py extension)
loader = importlib.machinery.SourceFileLoader("macode_hash", os.path.join(BIN_DIR, "macode-hash"))
macode_hash = importlib.util.module_from_spec(importlib.util.spec_from_loader("macode_hash", loader))
sys.modules["macode_hash"] = macode_hash
loader.exec_module(macode_hash)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _write_file(path: str, content: str) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)


# ---------------------------------------------------------------------------
# scan_import_dependencies
# ---------------------------------------------------------------------------


class TestScanImportDependencies:
    def test_transitive_resolution(self):
        """scene.py → a.py → b.py → c.py"""
        with tempfile.TemporaryDirectory() as root:
            src = os.path.join(root, "src")
            scene_dir = os.path.join(root, "scene")
            os.makedirs(src)
            os.makedirs(scene_dir)

            _write_file(os.path.join(src, "c.py"), "x = 1\n")
            _write_file(os.path.join(src, "b.py"), "from c import x\n")
            _write_file(os.path.join(src, "a.py"), "from b import x\n")
            _write_file(os.path.join(scene_dir, "scene.py"), "from a import x\n")

            deps = macode_hash.scan_import_dependencies(
                [os.path.join(scene_dir, "scene.py")],
                root,
                [src],
            )
            basenames = {os.path.basename(p) for p in deps}
            assert basenames == {"scene.py", "a.py", "b.py", "c.py"}

    def test_circular_import_handled(self):
        """Circular imports should not cause infinite recursion."""
        with tempfile.TemporaryDirectory() as root:
            src = os.path.join(root, "src")
            scene_dir = os.path.join(root, "scene")
            os.makedirs(src)
            os.makedirs(scene_dir)

            _write_file(os.path.join(src, "a.py"), "from b import y\n")
            _write_file(os.path.join(src, "b.py"), "from a import x\n")
            _write_file(os.path.join(scene_dir, "scene.py"), "from a import x\n")

            deps = macode_hash.scan_import_dependencies(
                [os.path.join(scene_dir, "scene.py")],
                root,
                [src],
            )
            basenames = {os.path.basename(p) for p in deps}
            assert basenames == {"scene.py", "a.py", "b.py"}

    def test_excludes_external_packages(self):
        """Standard library and third-party packages should not appear."""
        with tempfile.TemporaryDirectory() as root:
            scene_dir = os.path.join(root, "scene")
            os.makedirs(scene_dir)

            _write_file(
                os.path.join(scene_dir, "scene.py"),
                "import os\nimport sys\nimport json\nimport numpy\n",
            )

            deps = macode_hash.scan_import_dependencies(
                [os.path.join(scene_dir, "scene.py")],
                root,
                [],
            )
            basenames = {os.path.basename(p) for p in deps}
            # Only scene.py itself should be present
            assert basenames == {"scene.py"}

    def test_sys_path_append_detected(self):
        """sys.path.append should be detected and used for resolution."""
        with tempfile.TemporaryDirectory() as root:
            extra = os.path.join(root, "extra")
            scene_dir = os.path.join(root, "scene")
            os.makedirs(extra)
            os.makedirs(scene_dir)

            _write_file(os.path.join(extra, "mod.py"), "val = 42\n")
            _write_file(
                os.path.join(scene_dir, "scene.py"),
                f"import sys\nsys.path.append({extra!r})\nfrom mod import val\n",
            )

            deps = macode_hash.scan_import_dependencies(
                [os.path.join(scene_dir, "scene.py")],
                root,
                [],
            )
            basenames = {os.path.basename(p) for p in deps}
            assert "mod.py" in basenames

    def test_sys_path_insert_detected(self):
        """sys.path.insert should be detected and used for resolution."""
        with tempfile.TemporaryDirectory() as root:
            extra = os.path.join(root, "extra")
            scene_dir = os.path.join(root, "scene")
            os.makedirs(extra)
            os.makedirs(scene_dir)

            _write_file(os.path.join(extra, "mod.py"), "val = 42\n")
            _write_file(
                os.path.join(scene_dir, "scene.py"),
                f"import sys\nsys.path.insert(0, {extra!r})\nfrom mod import val\n",
            )

            deps = macode_hash.scan_import_dependencies(
                [os.path.join(scene_dir, "scene.py")],
                root,
                [],
            )
            basenames = {os.path.basename(p) for p in deps}
            assert "mod.py" in basenames

    def test_path_file_parent_detected(self):
        """Path(__file__).parent chains should be resolved."""
        with tempfile.TemporaryDirectory() as root:
            scene_dir = os.path.join(root, "scene")
            lib_dir = os.path.join(scene_dir, "lib")
            os.makedirs(lib_dir)

            _write_file(os.path.join(lib_dir, "helper.py"), "val = 42\n")
            _write_file(
                os.path.join(scene_dir, "scene.py"),
                "from pathlib import Path\n"
                "import sys\n"
                "sys.path.insert(0, str(Path(__file__).parent / 'lib'))\n"
                "from helper import val\n",
            )

            deps = macode_hash.scan_import_dependencies(
                [os.path.join(scene_dir, "scene.py")],
                root,
                [],
            )
            basenames = {os.path.basename(p) for p in deps}
            assert "helper.py" in basenames


# ---------------------------------------------------------------------------
# compute_hash
# ---------------------------------------------------------------------------


class TestComputeHash:
    def test_determinism(self):
        """Same directory should produce the same hash."""
        with tempfile.TemporaryDirectory() as root:
            scene_dir = os.path.join(root, "scene")
            os.makedirs(scene_dir)
            _write_file(
                os.path.join(scene_dir, "manifest.json"),
                json.dumps({"engine": "manim", "duration": 1, "fps": 1}),
            )
            _write_file(os.path.join(scene_dir, "scene.py"), "pass\n")

            h1, _ = macode_hash.compute_hash(scene_dir, root)
            h2, _ = macode_hash.compute_hash(scene_dir, root)
            assert h1 == h2
            assert len(h1) == 32

    def test_changes_when_scene_file_modified(self):
        """Modifying a scene file should change the hash."""
        with tempfile.TemporaryDirectory() as root:
            scene_dir = os.path.join(root, "scene")
            os.makedirs(scene_dir)
            _write_file(
                os.path.join(scene_dir, "manifest.json"),
                json.dumps({"engine": "manim", "duration": 1, "fps": 1}),
            )
            _write_file(os.path.join(scene_dir, "scene.py"), "pass\n")

            h1, _ = macode_hash.compute_hash(scene_dir, root)

            _write_file(os.path.join(scene_dir, "scene.py"), "x = 1\n")
            h2, _ = macode_hash.compute_hash(scene_dir, root)
            assert h1 != h2

    def test_changes_when_deep_dependency_modified(self):
        """Modifying a transitive dependency should change the hash."""
        with tempfile.TemporaryDirectory() as root:
            src = os.path.join(root, "engines", "manim", "src")
            scene_dir = os.path.join(root, "scene")
            os.makedirs(src)
            os.makedirs(scene_dir)

            _write_file(os.path.join(src, "deep.py"), "x = 1\n")
            _write_file(os.path.join(src, "mid.py"), "from deep import x\n")
            _write_file(
                os.path.join(scene_dir, "manifest.json"),
                json.dumps({"engine": "manim", "duration": 1, "fps": 1}),
            )
            _write_file(os.path.join(scene_dir, "scene.py"), "from mid import x\n")

            h1, deps1 = macode_hash.compute_hash(scene_dir, root)
            assert any("deep.py" in p for p in deps1)

            _write_file(os.path.join(src, "deep.py"), "x = 2\n")
            h2, _ = macode_hash.compute_hash(scene_dir, root)
            assert h1 != h2

    def test_missing_manifest_raises(self):
        """Missing manifest.json should raise FileNotFoundError."""
        with tempfile.TemporaryDirectory() as root:
            scene_dir = os.path.join(root, "scene")
            os.makedirs(scene_dir)
            with pytest.raises(FileNotFoundError):
                macode_hash.compute_hash(scene_dir, root)

    def test_deps_json_format(self, capsys):
        """--deps-json should output valid JSON with hash and dependencies."""
        with tempfile.TemporaryDirectory() as root:
            scene_dir = os.path.join(root, "scene")
            os.makedirs(scene_dir)
            _write_file(
                os.path.join(scene_dir, "manifest.json"),
                json.dumps({"engine": "manim", "duration": 1, "fps": 1}),
            )
            _write_file(os.path.join(scene_dir, "scene.py"), "pass\n")

            old_argv = sys.argv
            try:
                sys.argv = ["macode-hash", scene_dir, "--deps-json"]
                assert macode_hash.main() == 0
            finally:
                sys.argv = old_argv

            captured = capsys.readouterr()
            data = json.loads(captured.out)
            assert "hash" in data
            assert "dependencies" in data
            assert isinstance(data["hash"], str)
            assert isinstance(data["dependencies"], list)
            assert len(data["hash"]) == 32


# ---------------------------------------------------------------------------
# Integration with real project
# ---------------------------------------------------------------------------


class TestRealProjectIntegration:
    def test_test_layout_compiler_has_transitive_deps(self):
        """The real test_layout_compiler scene should resolve transitive engine deps."""
        scene_dir = os.path.join(
            PROJECT_ROOT, "tests", "fixtures", "scenes", "test_layout_compiler"
        )
        if not os.path.isdir(scene_dir):
            pytest.skip("test_layout_compiler fixture not found")

        hash_str, deps = macode_hash.compute_hash(scene_dir, PROJECT_ROOT)
        assert len(hash_str) == 32

        basenames = {os.path.basename(p) for p in deps}
        # Should include transitive dependencies from components.narrative_scene
        assert "narrative_scene.py" in basenames
        assert "zoned_scene.py" in basenames
        assert "layout_geometry.py" in basenames

        # numpy (manimlib) should NOT be in deps
        assert "numpy" not in basenames
        assert "__init__.py" not in basenames  # site-packages noise
