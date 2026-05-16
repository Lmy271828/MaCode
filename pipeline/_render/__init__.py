"""Internal render pipeline stages, callable from ``pipeline/render-scene.py``.

Public stages:

    from pipeline._render import lifecycle, validate, engine, encode
    from pipeline._render.validate import RenderContext, validate_scene
    from pipeline._render.engine import run as run_engine, EngineResult
    from pipeline._render.encode import run as run_encode, EncodeResult

Top-level CLI driver lives in ``orchestrator.py`` and is invoked by the
thin ``pipeline/render-scene.py``.
"""

from __future__ import annotations

from . import encode, engine, lifecycle, validate
from ._paths import (
    PROJECT_ROOT,
    find_free_port,
    get_project_root,
    get_python,
    locate_scene_file,
    read_manifest,
    scene_inherits_from,
)

__all__ = [
    "PROJECT_ROOT",
    "encode",
    "engine",
    "lifecycle",
    "validate",
    "find_free_port",
    "get_project_root",
    "get_python",
    "locate_scene_file",
    "read_manifest",
    "scene_inherits_from",
]
