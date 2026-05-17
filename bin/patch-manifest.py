#!/usr/bin/env python3
"""bin/patch-manifest.py
Atomically patch manifest.json with preview parameters.

Uses tmpfile + os.replace for atomic writes. Never leaves a partially
written manifest on disk.

Usage:
    patch-manifest.py <manifest.json> --duration 3 --fps 10 --resolution 640x360
    patch-manifest.py <manifest.json> --backup manifest.json.bak
    patch-manifest.py <manifest.json> --restore manifest.json.bak

Exit codes:
    0 - success
    1 - error
"""

import argparse
import json
import os
import re
import sys
import tempfile
from pathlib import Path


def patch_manifest(
    manifest_path: str,
    duration: float = None,
    fps: int = None,
    resolution: tuple = None,
) -> dict:
    """Apply patches and return the patched data."""
    with open(manifest_path, encoding="utf-8") as f:
        data = json.load(f)

    if duration is not None:
        data["duration"] = duration
    if fps is not None:
        data["fps"] = fps
    if resolution is not None:
        data["resolution"] = list(resolution)

    return data


def write_manifest_atomic(manifest_path: str, data: dict) -> None:
    """Write manifest atomically using tmpfile + os.replace."""
    raw = json.dumps(data, indent=2, ensure_ascii=False)
    # Ensure resolution stays on one line (for sed-based parsers)
    raw = re.sub(
        r'"resolution":\s*\[\s*(\d+),\s*(\d+)\s*\]',
        r'"resolution": [\1, \2]',
        raw,
    )
    raw += "\n"

    manifest = Path(manifest_path)
    fd, tmp_path = tempfile.mkstemp(dir=manifest.parent, prefix=f".{manifest.name}.", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(raw)
        os.replace(tmp_path, manifest_path)
    except Exception:
        Path(tmp_path).unlink(missing_ok=True)
        raise


def backup_manifest(manifest_path: str, backup_path: str) -> None:
    """Create a backup copy of manifest."""
    import shutil

    shutil.copy2(manifest_path, backup_path)


def restore_manifest(manifest_path: str, backup_path: str) -> None:
    """Restore manifest from backup atomically."""
    backup = Path(backup_path)
    if not backup.is_file():
        print(f"Error: backup not found: {backup_path}", file=sys.stderr)
        sys.exit(1)
    # Atomic restore: copy backup to tmp, then replace
    manifest = Path(manifest_path)
    fd, tmp_path = tempfile.mkstemp(dir=manifest.parent, prefix=f".{manifest.name}.", suffix=".tmp")
    try:
        with open(backup_path, "rb") as src, os.fdopen(fd, "wb") as dst:
            dst.write(src.read())
        os.replace(tmp_path, manifest_path)
    except Exception:
        Path(tmp_path).unlink(missing_ok=True)
        raise


def main():
    parser = argparse.ArgumentParser(
        description="Atomically patch manifest.json.",
        usage="%(prog)s <manifest.json> [options]",
    )
    parser.add_argument("manifest", help="Path to manifest.json")
    parser.add_argument("--duration", type=float, help="Override duration")
    parser.add_argument("--fps", type=int, help="Override fps")
    parser.add_argument("--resolution", help="Override resolution as WxH, e.g. 640x360")
    parser.add_argument("--backup", help="Create backup at path before patching")
    parser.add_argument("--restore", help="Restore from backup path")
    args = parser.parse_args()

    if not Path(args.manifest).is_file():
        print(f"Error: manifest not found: {args.manifest}", file=sys.stderr)
        sys.exit(1)

    # Restore mode
    if args.restore:
        restore_manifest(args.manifest, args.restore)
        print(f"[patch-manifest] Restored from {args.restore}")
        return

    # Backup mode
    if args.backup:
        backup_manifest(args.manifest, args.backup)

    # Patch mode
    resolution = None
    if args.resolution:
        try:
            w, h = args.resolution.split("x")
            resolution = (int(w), int(h))
        except ValueError:
            print(f"Error: invalid resolution format: {args.resolution}", file=sys.stderr)
            sys.exit(1)

    data = patch_manifest(
        args.manifest,
        duration=args.duration,
        fps=args.fps,
        resolution=resolution,
    )
    write_manifest_atomic(args.manifest, data)

    parts = []
    if args.duration is not None:
        parts.append(f"duration={args.duration}")
    if args.fps is not None:
        parts.append(f"fps={args.fps}")
    if resolution is not None:
        parts.append(f"resolution={args.resolution}")
    print(f"[patch-manifest] Patched: {', '.join(parts)}")


if __name__ == "__main__":
    main()
