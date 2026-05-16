#!/usr/bin/env python3
"""List available shader assets from registry.

Usage: macode-shader-list.py <registry_json_path>
"""

import json
import os
import sys


def main() -> int:
    if len(sys.argv) < 2:
        print("Usage: macode-shader-list.py <registry_json_path>", file=sys.stderr)
        return 1

    registry_path = sys.argv[1]
    if not os.path.isfile(registry_path):
        print(f"No shader registry found. Expected: {registry_path}", file=sys.stderr)
        return 1

    with open(registry_path, encoding="utf-8") as f:
        reg = json.load(f)

    print("Available shader assets (Layer 2):")
    for s in reg.get("assets", []):
        cat = s.get("category", "unknown")
        typ = s.get("type", "unknown")
        print(f"  {s['id']:<30} [{cat}/{typ}]  {s.get('description', '')}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
