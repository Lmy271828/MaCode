#!/usr/bin/env python3
"""pipeline/render-scene.py
Thin entry — delegates to ``pipeline._render.orchestrator``.

Rollback::
    MACODE_USE_LEGACY_RENDER=1  → loads ``pipeline/render_scene_legacy.py`` verbatim.

Concurrency::
    PRD excludes Multi-Agent claim/queue wiring; callers must serialize concurrent work if needed.

CLI unchanged: ``render-scene.py <scene_dir> [--json] [--fps N] ...``
"""

from __future__ import annotations

import os
import sys

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)


def main() -> None:
    if os.environ.get("MACODE_USE_LEGACY_RENDER") == "1":
        from pipeline import render_scene_legacy as legacy_mod

        legacy_mod.main()
        return

    from pipeline._render.orchestrator import main as orchestrator_main

    orchestrator_main()


if __name__ == "__main__":
    main()
