#!/usr/bin/env python3
"""bin/cache-store.py
Store output directory to cache.

Usage:
    cache-store.py <cache_key> <source_dir>

Exit: 0 on success, 1 on error
"""

import json
import os
import shutil
import sys


def main():
    if len(sys.argv) < 3:
        print("Usage: cache-store.py <cache_key> <source_dir>", file=sys.stderr)
        sys.exit(1)

    key = sys.argv[1]
    source_dir = sys.argv[2]
    cache_dir = os.path.join(".agent", "cache", key)

    if not os.path.isdir(source_dir):
        print(f"Error: source_dir not found: {source_dir}", file=sys.stderr)
        sys.exit(1)

    os.makedirs(cache_dir, exist_ok=True)

    for name in os.listdir(source_dir):
        if name.startswith("."):
            continue
        src = os.path.join(source_dir, name)
        dst = os.path.join(cache_dir, name)
        if os.path.isdir(src):
            if os.path.isdir(dst):
                shutil.rmtree(dst)
            shutil.copytree(src, dst)
        else:
            shutil.copy2(src, dst)

    # Write manifest for transparency
    manifest = {
        "key": key,
        "source": os.path.abspath(source_dir),
    }
    with open(os.path.join(cache_dir, ".cache_manifest"), "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)
        f.write("\n")

    print(f"[cache] STORED: {key}")


if __name__ == "__main__":
    main()
