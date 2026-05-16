#!/usr/bin/env python3
"""pipeline/render-scene.py
Thin entry — delegates to ``pipeline._render.orchestrator``.

CLI: ``render-scene.py <scene_dir> [--json] [--fps N] ...``
"""

from __future__ import annotations

import os
import sys

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from pipeline._render.orchestrator import main as orchestrator_main

if __name__ == "__main__":
    orchestrator_main()
