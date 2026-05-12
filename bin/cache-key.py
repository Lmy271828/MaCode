#!/usr/bin/env python3
"""bin/cache-key.py
Compute a deterministic cache key for a scene directory.

Engine-agnostic algorithm:
  1. Hash manifest.json
  2. Hash every non-hidden file in the scene directory (excluding editor backups, logs, caches)
  3. Hash one-level-deep subdirectories (e.g. assets/ or utils/) but skip known output/vendor dirs
  4. Hash shader source dependencies declared in manifest.shaders

Output: hex cache key (stdout)
Exit: 0 on success, 1 on error
"""

import hashlib
import json
import os
import sys

# Files/dirs to exclude from cache key computation
_EXCLUDE_SUFFIXES = frozenset({".log", ".tmp", ".swp", ".swo", ".bak", "~"})
_EXCLUDE_DIRS = frozenset({".git", "__pycache__", ".pytest_cache", "node_modules", ".venv", ".agent"})
_EXCLUDE_NAMES = frozenset({".cache_path", ".DS_Store", "Thumbs.db"})


def sha256_file(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def sha256_str(s: str) -> str:
    return hashlib.sha256(s.encode()).hexdigest()


def is_excluded_file(name: str) -> bool:
    """Exclude hidden files, editor backups, and known noise files."""
    if name.startswith(".") or name.startswith("_"):
        return True
    if name in _EXCLUDE_NAMES:
        return True
    if any(name.endswith(suffix) for suffix in _EXCLUDE_SUFFIXES):
        return True
    return False


def collect_scene_inputs(scene_dir: str) -> list:
    """
    Collect all files in the scene directory that affect rendering output.
    Includes:
      - Top-level non-hidden files (not just scene.*)
      - One-level-deep files in subdirs (e.g. assets/, utils/)
    Excludes:
      - Hidden files, editor backups, logs
      - Known cache/vendor directories (node_modules, __pycache__, etc.)
    """
    files = []
    try:
        entries = sorted(os.listdir(scene_dir))
    except OSError:
        return files

    for name in entries:
        if is_excluded_file(name):
            continue
        fpath = os.path.join(scene_dir, name)
        if os.path.isfile(fpath):
            files.append(fpath)
        elif os.path.isdir(fpath) and name not in _EXCLUDE_DIRS:
            # Include one-level-deep files from subdirectories
            try:
                sub_entries = sorted(os.listdir(fpath))
            except OSError:
                continue
            for subname in sub_entries:
                if is_excluded_file(subname):
                    continue
                subpath = os.path.join(fpath, subname)
                if os.path.isfile(subpath):
                    files.append(subpath)
    return files


def collect_shader_files(project_root: str, shader_ids: list) -> list:
    """Find shader source files that affect rendering (exclude pre-rendered frames)."""
    files = []
    for sid in sorted(shader_ids):
        shader_dir = os.path.join(project_root, "assets", "shaders", sid)
        if not os.path.isdir(shader_dir):
            continue
        for name in sorted(os.listdir(shader_dir)):
            if name.endswith((".glsl", ".json", ".py", ".ts", ".tsx", ".js", ".mjs")):
                fpath = os.path.join(shader_dir, name)
                if os.path.isfile(fpath):
                    files.append(fpath)
    return files


def compute_cache_key(scene_dir: str) -> str:
    scene_dir = os.path.abspath(scene_dir)
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    manifest_path = os.path.join(scene_dir, "manifest.json")
    if not os.path.isfile(manifest_path):
        print("Error: manifest.json not found", file=sys.stderr)
        sys.exit(1)

    # Try macode-hash first (AST-based recursive import scanning)
    macode_hash_path = os.path.join(project_root, "bin", "macode-hash")
    if os.path.isfile(macode_hash_path) and os.access(macode_hash_path, os.X_OK):
        try:
            import subprocess
            result = subprocess.run(
                [sys.executable, macode_hash_path, scene_dir],
                capture_output=True, text=True, timeout=30,
            )
            if result.returncode == 0:
                hash_str = result.stdout.strip()
                if hash_str and len(hash_str) == 32:
                    return hash_str
        except Exception:
            pass  # Fall back to file-level algorithm

    # Read manifest for shader dependencies
    try:
        with open(manifest_path, encoding="utf-8") as f:
            manifest = json.load(f)
    except json.JSONDecodeError as e:
        print(f"Error: invalid manifest.json: {e}", file=sys.stderr)
        sys.exit(1)

    # Build ordered list of input hashes
    hashes = []

    # 1. Manifest hash
    hashes.append(sha256_file(manifest_path))

    # 2. All scene input files (engine-agnostic conservative scan)
    for fpath in collect_scene_inputs(scene_dir):
        hashes.append(sha256_file(fpath))

    # 3. Shader source dependencies
    shader_ids = manifest.get("shaders", [])
    if shader_ids:
        for fpath in collect_shader_files(project_root, shader_ids):
            hashes.append(sha256_file(fpath))
        # Include shader IDs as text (in case shader dir is missing, hash still changes)
        hashes.append(sha256_str("shaders:" + ",".join(sorted(shader_ids))))

    # Combine into final key (256-bit truncated to 128-bit is sufficient)
    combined = hashlib.sha256("\n".join(hashes).encode()).hexdigest()
    return combined[:32]


if __name__ == "__main__":
    if len(sys.argv) < 2 or sys.argv[1] in ("-h", "--help"):
        print("Usage: cache-key.py <scene_dir>")
        print("")
        print("Compute a deterministic cache key for a scene directory.")
        print("")
        print("Arguments:")
        print("  <scene_dir>    Scene directory path")
        print("")
        print("Output: hex cache key (stdout)")
        print("Exit: 0 on success, 1 on error")
        sys.exit(0 if len(sys.argv) >= 2 and sys.argv[1] in ("-h", "--help") else 1)

    key = compute_cache_key(sys.argv[1])
    print(key)
