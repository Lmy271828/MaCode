"""Unit tests for pipeline._render.engine source-hash cache.

Covers:
  - _compute_source_hash: deterministic, changes when source changes
  - _check_source_hash: hit when hash matches and output exists
  - _check_source_hash: miss when hash mismatch or output missing
  - _write_source_hash: persists hash to .source_hash file
"""

import os
import sys
import tempfile

PIPELINE_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "pipeline")
sys.path.insert(0, PIPELINE_DIR)

from _render.engine import _check_source_hash, _compute_source_hash, _write_source_hash
from _render.validate import RenderContext


def _make_ctx(
    scene_dir: str, scene_file: str, output_dir: str, engine_mode: str = "batch"
) -> RenderContext:
    return RenderContext(
        scene_dir=scene_dir,
        scene_name="test_scene",
        scene_file=scene_file,
        manifest={},
        engine="manim",
        engine_conf={"mode": engine_mode, "scene_extensions": [".py"]},
        ext_list=[".py"],
        engine_mode=engine_mode,
        render_script_rel="",
        unified_mc_render=False,
        fps=30,
        duration=3.0,
        width=1920,
        height=1080,
        output_dir=output_dir,
        frames_dir=os.path.join(output_dir, "frames"),
        log_file=os.path.join(output_dir, "render.log"),
    )


class TestComputeSourceHash:
    def test_deterministic(self):
        with tempfile.TemporaryDirectory() as d:
            scene = os.path.join(d, "scene.py")
            manifest = os.path.join(d, "manifest.json")
            with open(scene, "w") as f:
                f.write("code")
            with open(manifest, "w") as f:
                f.write("{}")

            ctx = _make_ctx(d, scene, d)
            h1 = _compute_source_hash(ctx)
            h2 = _compute_source_hash(ctx)
            assert h1 == h2
            assert len(h1) == 16

    def test_changes_when_source_changes(self):
        with tempfile.TemporaryDirectory() as d:
            scene = os.path.join(d, "scene.py")
            manifest = os.path.join(d, "manifest.json")
            with open(manifest, "w") as f:
                f.write("{}")

            with open(scene, "w") as f:
                f.write("code v1")
            ctx = _make_ctx(d, scene, d)
            h1 = _compute_source_hash(ctx)

            with open(scene, "w") as f:
                f.write("code v2")
            h2 = _compute_source_hash(ctx)
            assert h1 != h2


class TestCheckSourceHash:
    def test_hit_when_hash_matches_and_output_exists(self):
        with tempfile.TemporaryDirectory() as d:
            scene = os.path.join(d, "scene.py")
            manifest = os.path.join(d, "manifest.json")
            output = os.path.join(d, "output")
            os.makedirs(output, exist_ok=True)
            with open(scene, "w") as f:
                f.write("code")
            with open(manifest, "w") as f:
                f.write("{}")
            # Create a non-empty final.mp4
            with open(os.path.join(output, "final.mp4"), "w") as f:
                f.write("mp4data")
            # Write hash
            ctx = _make_ctx(d, scene, output)
            _write_source_hash(ctx)

            assert _check_source_hash(ctx) is True

    def test_miss_when_hash_mismatch(self):
        with tempfile.TemporaryDirectory() as d:
            scene = os.path.join(d, "scene.py")
            manifest = os.path.join(d, "manifest.json")
            output = os.path.join(d, "output")
            os.makedirs(output, exist_ok=True)
            with open(scene, "w") as f:
                f.write("code")
            with open(manifest, "w") as f:
                f.write("{}")
            open(os.path.join(output, "final.mp4"), "a").close()

            ctx = _make_ctx(d, scene, output)
            _write_source_hash(ctx)

            # Change source
            with open(scene, "w") as f:
                f.write("changed code")
            assert _check_source_hash(ctx) is False

    def test_miss_when_output_missing(self):
        with tempfile.TemporaryDirectory() as d:
            scene = os.path.join(d, "scene.py")
            manifest = os.path.join(d, "manifest.json")
            output = os.path.join(d, "output")
            os.makedirs(output, exist_ok=True)
            with open(scene, "w") as f:
                f.write("code")
            with open(manifest, "w") as f:
                f.write("{}")

            ctx = _make_ctx(d, scene, output)
            _write_source_hash(ctx)
            # final.mp4 does not exist
            assert _check_source_hash(ctx) is False

    def test_hit_with_frames_dir_for_batch(self):
        with tempfile.TemporaryDirectory() as d:
            scene = os.path.join(d, "scene.py")
            manifest = os.path.join(d, "manifest.json")
            output = os.path.join(d, "output")
            frames = os.path.join(output, "frames")
            os.makedirs(frames, exist_ok=True)
            with open(scene, "w") as f:
                f.write("code")
            with open(manifest, "w") as f:
                f.write("{}")
            # No final.mp4, but frames dir has actual files
            with open(os.path.join(frames, "frame_0001.png"), "w") as f:
                f.write("pngdata")
            ctx = _make_ctx(d, scene, output, engine_mode="batch")
            _write_source_hash(ctx)
            assert _check_source_hash(ctx) is True

    def test_miss_when_frames_dir_empty(self):
        with tempfile.TemporaryDirectory() as d:
            scene = os.path.join(d, "scene.py")
            manifest = os.path.join(d, "manifest.json")
            output = os.path.join(d, "output")
            frames = os.path.join(output, "frames")
            os.makedirs(frames, exist_ok=True)
            with open(scene, "w") as f:
                f.write("code")
            with open(manifest, "w") as f:
                f.write("{}")
            ctx = _make_ctx(d, scene, output, engine_mode="batch")
            _write_source_hash(ctx)
            assert _check_source_hash(ctx) is False

    def test_miss_when_mp4_is_empty(self):
        with tempfile.TemporaryDirectory() as d:
            scene = os.path.join(d, "scene.py")
            manifest = os.path.join(d, "manifest.json")
            output = os.path.join(d, "output")
            os.makedirs(output, exist_ok=True)
            with open(scene, "w") as f:
                f.write("code")
            with open(manifest, "w") as f:
                f.write("{}")
            # Empty final.mp4 should not count as a valid artifact
            open(os.path.join(output, "final.mp4"), "a").close()
            ctx = _make_ctx(d, scene, output)
            _write_source_hash(ctx)
            assert _check_source_hash(ctx) is False

    def test_miss_for_interactive_without_raw_mp4(self):
        with tempfile.TemporaryDirectory() as d:
            scene = os.path.join(d, "scene.py")
            manifest = os.path.join(d, "manifest.json")
            output = os.path.join(d, "output")
            os.makedirs(output, exist_ok=True)
            with open(scene, "w") as f:
                f.write("code")
            with open(manifest, "w") as f:
                f.write("{}")

            ctx = _make_ctx(d, scene, output, engine_mode="interactive")
            _write_source_hash(ctx)
            # No raw.mp4 for interactive mode
            assert _check_source_hash(ctx) is False


class TestWriteSourceHash:
    def test_creates_hash_file(self):
        with tempfile.TemporaryDirectory() as d:
            scene = os.path.join(d, "scene.py")
            manifest = os.path.join(d, "manifest.json")
            output = os.path.join(d, "output")
            os.makedirs(output, exist_ok=True)
            with open(scene, "w") as f:
                f.write("code")
            with open(manifest, "w") as f:
                f.write("{}")

            ctx = _make_ctx(d, scene, output)
            _write_source_hash(ctx)

            hash_file = os.path.join(output, ".source_hash")
            assert os.path.isfile(hash_file)
            with open(hash_file) as f:
                content = f.read().strip()
            assert len(content) == 16
