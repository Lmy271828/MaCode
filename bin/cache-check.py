#!/usr/bin/env python3
"""bin/cache-check.py
Check if a cache key exists and is valid.

Usage:
    cache-check.py <cache_key>

Exit: 0 = cache hit, 1 = cache miss
"""

import os
import sys


def main():
    if len(sys.argv) < 2 or sys.argv[1] in ("-h", "--help"):
        print("Usage: cache-check.py <cache_key>")
        print("")
        print("Check if a cache key exists and is valid.")
        print("")
        print("Arguments:")
        print("  <cache_key>    Cache key to check")
        print("")
        print("Exit codes:")
        print("  0  Cache hit")
        print("  1  Cache miss or error")
        sys.exit(0 if sys.argv[1] in ("-h", "--help") else 1)

    key = sys.argv[1]
    cache_dir = os.path.join(".agent", "cache", key)
    manifest = os.path.join(cache_dir, ".cache_manifest")

    if os.path.isfile(manifest):
        sys.exit(0)
    else:
        sys.exit(1)


if __name__ == "__main__":
    main()
