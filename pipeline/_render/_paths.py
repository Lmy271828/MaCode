"""Path / manifest helpers shared by orchestrator + composite.

These are pure functions with no side effects on global state. They were
duplicated across ``orchestrator.py``, ``composite-render.py``, and
``deliver.py``; consolidating here is step 1 of S7-CLEAN-2.
"""

from __future__ import annotations

import ast
import json
import os
import random
import socket

_HERE = os.path.dirname(os.path.abspath(__file__))
_PIPELINE_DIR = os.path.dirname(_HERE)
PROJECT_ROOT = os.path.dirname(_PIPELINE_DIR)


def get_project_root() -> str:
    return PROJECT_ROOT


def get_python() -> str:
    """Prefer project venv python, fall back to ``python3`` on PATH."""
    venv_python = os.path.join(PROJECT_ROOT, ".venv", "bin", "python")
    if os.path.isfile(venv_python) and os.access(venv_python, os.X_OK):
        return venv_python
    return "python3"


def read_manifest(manifest_path: str) -> dict:
    """Read ``manifest.json`` and return parsed dict."""
    with open(manifest_path, encoding="utf-8") as f:
        return json.load(f)


def find_free_port(port_min: int, port_max: int) -> int:
    """Atomically reserve a free TCP port in the inclusive range via ``bind()``."""
    ports = list(range(port_min, port_max + 1))
    random.shuffle(ports)
    for port in ports:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(0.2)
            try:
                s.bind(("127.0.0.1", port))
                return port
            except OSError:
                continue
    raise RuntimeError(f"No free port in range {port_min}-{port_max}")


def locate_scene_file(scene_dir: str, extensions: list[str]) -> str:
    """Return path to ``scene.<ext>`` for the first matching extension, else ''."""
    for ext in extensions:
        candidate = os.path.join(scene_dir, f"scene{ext}")
        if os.path.isfile(candidate):
            return candidate
    return ""


def scene_inherits_from(source_path: str, base_names: list[str]) -> bool:
    """Return True if any ``ClassDef`` in source_path inherits from one of base_names.

    Lightweight static check — does not import the scene module. Returns False on
    syntax errors so that downstream rendering can still fail loudly with engine
    diagnostics rather than crashing here.
    """
    try:
        with open(source_path, encoding="utf-8") as f:
            tree = ast.parse(f.read())
    except (SyntaxError, OSError):
        return False
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef):
            for base in node.bases:
                name = ""
                if isinstance(base, ast.Name):
                    name = base.id
                elif isinstance(base, ast.Attribute):
                    name = base.attr
                if name in base_names:
                    return True
    return False
