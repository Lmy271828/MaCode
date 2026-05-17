#!/usr/bin/env python3
"""bin/scene-init.py
Single-scene scaffolding tool.

Usage:
    scene-init.py <scene_path> --engine <engine_name>

Creates manifest.json + scene.py (or scene.tsx) from a minimal template.
"""

from __future__ import annotations

import argparse
import json
import os
import sys

DEFAULT_SCENE_PY = '''"""{scene_name} scene."""

from {import_stmt} import *


class {class_name}(Scene):
    def construct(self):
        # TODO: implement scene
        text = Text("{scene_name}", font_size=48)
        self.play(FadeIn(text), run_time=1.0)
        self.wait({wait_duration})
'''

DEFAULT_SCENE_TSX = '''import {{makeScene2D}} from '@motion-canvas/2d';
import {{Txt}} from '@motion-canvas/2d';
import {{createRef}} from '@motion-canvas/core';

/**
 * {scene_name} scene
 */
export default makeScene2D(function* (view) {{
  const text = createRef<Txt>();

  view.add(
    <Txt
      ref={{text}}
      text="{scene_name}"
      fontSize={{64}}
      fill="white"
    />
  );

  yield* text().scale(1.2, 0.5);
  yield* text().scale(1, 0.5);
}});
'''


def make_manifest(engine: str, duration: float) -> dict:
    base = {
        "engine": engine,
        "duration": duration,
        "fps": 30,
        "resolution": [1920, 1080],
        "assets": [],
        "dependencies": [],
        "meta": {
            "title": "",
            "author": "agent",
            "tags": [],
        },
    }
    if engine == "motion_canvas":
        base["template"] = "makeScene2D"
    else:
        base["template"] = "Scene"
    return base


def sanitize_class_name(name: str) -> str:
    """Convert a scene directory name to a valid Python class name."""
    return "".join(word.capitalize() for word in name.replace("-", "_").split("_") if word) + "Scene"


def compact_json(data: dict) -> str:
    """Compact JSON with short arrays kept on one line."""
    raw = json.dumps(data, indent=2, ensure_ascii=False)
    import re

    raw = re.sub(r'"resolution": \[\s*(\d+),\s*(\d+)\s*\]', r'"resolution": [\1, \2]', raw)
    raw = re.sub(r'"(assets|dependencies|tags)": \[\s*\]', r'"\1": []', raw)
    return raw


def init_scene(scene_path: str, engine: str, duration: float = 3.0) -> None:
    scene_path = os.path.normpath(scene_path)
    if os.path.exists(scene_path):
        print(f"Error: directory already exists: {scene_path}", file=sys.stderr)
        sys.exit(1)

    scene_name = os.path.basename(scene_path)
    os.makedirs(scene_path, exist_ok=True)

    manifest = make_manifest(engine, duration)
    manifest["meta"]["title"] = scene_name

    with open(os.path.join(scene_path, "manifest.json"), "w", encoding="utf-8") as f:
        f.write(compact_json(manifest) + "\n")

    if engine == "motion_canvas":
        content = DEFAULT_SCENE_TSX.format(scene_name=scene_name)
        filename = "scene.tsx"
    else:
        import_stmt = "manim" if engine == "manim" else "manimlib"
        content = DEFAULT_SCENE_PY.format(
            scene_name=scene_name,
            import_stmt=import_stmt,
            class_name=sanitize_class_name(scene_name),
            wait_duration=duration - 1.0,
        )
        filename = "scene.py"

    with open(os.path.join(scene_path, filename), "w", encoding="utf-8") as f:
        f.write(content)

    print(f"[init] Created single scene: {scene_path}")
    print(f"[init] Engine: {engine}")
    print(f"[init] Files: manifest.json, {filename}")


def main():
    parser = argparse.ArgumentParser(
        description="Single-scene scaffolding tool.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("scene_path", help="Path to new scene directory")
    parser.add_argument(
        "--engine",
        default="manim",
        choices=["manim", "manimgl", "motion_canvas"],
        help="Engine for the scene (default: manim)",
    )
    parser.add_argument(
        "--duration",
        type=float,
        default=3.0,
        help="Scene duration in seconds (default: 3.0)",
    )
    args = parser.parse_args()

    init_scene(args.scene_path, args.engine, args.duration)


if __name__ == "__main__":
    main()
