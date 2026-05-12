#!/usr/bin/env python3
"""bin/cache-restore.py
Restore cached output to destination directory.

Usage:
    cache-restore.py <cache_key> <dest_dir>

Exit: 0 on success, 1 on error
"""

import os
import shutil
import sys


def main():
    if len(sys.argv) < 3:
        print("Usage: cache-restore.py <cache_key> <dest_dir>", file=sys.stderr)
        sys.exit(1)

    key = sys.argv[1]
    dest_dir = sys.argv[2]
    cache_dir = os.path.join(".agent", "cache", key)

    if not os.path.isdir(cache_dir):
        print(f"[cache] MISS: {key}", file=sys.stderr)
        sys.exit(1)

    os.makedirs(dest_dir, exist_ok=True)

    restored = 0
    for name in os.listdir(cache_dir):
        if name.startswith("."):
            continue
        src = os.path.join(cache_dir, name)
        dst = os.path.join(dest_dir, name)
        if os.path.isdir(src):
            if os.path.isdir(dst):
                shutil.rmtree(dst)
            shutil.copytree(src, dst)
        else:
            shutil.copy2(src, dst)
        restored += 1

    print(f"[cache] RESTORED: {key} ({restored} items) -> {dest_dir}")


if __name__ == "__main__":
    main()
