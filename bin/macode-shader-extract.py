#!/usr/bin/env python3
"""Extract built-in manimlib shader to output directory.

Usage: macode-shader-extract.py <shader_name> <output_dir>
"""

import os
import sys


def main() -> int:
    if len(sys.argv) < 3:
        print("Usage: macode-shader-extract.py <shader_name> <output_dir>", file=sys.stderr)
        return 1

    shader_name = sys.argv[1]
    output_dir = sys.argv[2]

    # Add manimgl src to PYTHONPATH for shader_extractor
    manimgl_src = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "engines", "manimgl", "src"
    )
    if manimgl_src not in sys.path:
        sys.path.insert(0, manimgl_src)

    from utils.shader_extractor import extract_builtin_shader, save_shader_asset

    try:
        data = extract_builtin_shader(shader_name)
        save_shader_asset(data, output_dir)
        print(f"Extracted {data['name']} → {output_dir}")
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
