#!/usr/bin/env python3
"""bin/primitive-gate.py
Detect direct writes to low-level primitives (GLSL, raw LaTeX, hand-written configs).

Usage:
    primitive-gate.py <scene_dir>

Exit: 0 = pass, 1 = violations found, 2 = argument or file error
"""

import argparse
import os
import re
import sys

# Patterns that indicate Agent wrote low-level primitives directly
CODE_PATTERNS = [
    # GLSL shader code in Python/TSX files
    (r'gl_Position|gl_FragColor|gl_FragCoord', 'GLSL builtin in scene code'),
    (r'uniform\s+\w+\s+\w+', 'GLSL uniform declaration in scene code'),
    (r'varying\s+\w+\s+\w+', 'GLSL varying declaration in scene code'),
    (r'attribute\s+\w+\s+\w+', 'GLSL attribute declaration in scene code'),
    (r'#version\s+\d+', 'GLSL version directive in scene code'),
    # Raw LaTeX environments (Agent should use latex_helper)
    (r'\\\\begin\{cases\}', 'raw LaTeX cases (use utils.latex_helper)'),
    (r'\\\\begin\{bmatrix\}|\\\\begin\{pmatrix\}|\\\\begin\{Bmatrix\}', 'raw LaTeX matrix (use utils.latex_helper)'),
    (r'\\\\begin\{align\*?\}', 'raw LaTeX align (use utils.latex_helper)'),
    (r'\\\\begin\{equation\*?\}', 'raw LaTeX equation (use utils.latex_helper)'),
    # Hand-written ffmpeg filtergraphs
    (r'-vf\s*"', 'hand-written ffmpeg -vf (use utils.ffmpeg_builder)'),
    (r'-af\s*"', 'hand-written ffmpeg -af (use utils.ffmpeg_builder)'),
    (r'-filter_complex\s*"', 'hand-written ffmpeg filter_complex (use utils.ffmpeg_builder)'),
    # Hand-written config files (Agent should not write engine configs)
    (r'engine:\s*\w+', 'hand-written engine config in scene code'),
]

# Forbidden file types that Agent should not create
FORBIDDEN_EXTENSIONS = {'.glsl', '.vert', '.frag', '.geom', '.comp'}

# Forbidden paths (relative to project root)
FORBIDDEN_PATH_PATTERNS = [
    r'^engines/[^/]+/engine\.conf$',
    r'^engines/[^/]+/SOURCEMAP\.md$',
    r'^project\.yaml$',
    r'^pipeline/',
    r'^bin/',
]


def check_code(file_path: str) -> list[str]:
    violations = []
    try:
        with open(file_path, encoding='utf-8') as f:
            code = f.read()
    except (OSError, UnicodeDecodeError):
        return violations

    for pattern, description in CODE_PATTERNS:
        if re.search(pattern, code):
            violations.append(f'{file_path}: {description}')
    return violations


def check_files(scene_dir: str, project_root: str) -> list[str]:
    violations = []
    for root, _dirs, files in os.walk(scene_dir):
        for name in files:
            ext = os.path.splitext(name)[1].lower()
            if ext in FORBIDDEN_EXTENSIONS:
                full = os.path.join(root, name)
                violations.append(
                    f'{full}: forbidden file type "{ext}" — '
                    'Agent must not write GLSL directly. Use Effect Registry.'
                )
    return violations


def check_path_bounds(scene_dir: str, project_root: str) -> list[str]:
    violations = []
    rel = os.path.relpath(scene_dir, project_root)
    for pattern in FORBIDDEN_PATH_PATTERNS:
        if re.search(pattern, rel):
            violations.append(
                f'{scene_dir}: scene directory violates path boundary — '
                f'matches forbidden pattern "{pattern}"'
            )
    return violations


def main() -> int:
    parser = argparse.ArgumentParser(
        description='Detect direct writes to low-level primitives.',
        epilog='Exit: 0=pass, 1=violations, 2=error',
    )
    parser.add_argument('scene_dir', help='Path to scene directory')
    args = parser.parse_args()

    scene_dir = os.path.abspath(args.scene_dir)
    if not os.path.isdir(scene_dir):
        print(f'FATAL: Not a directory: {scene_dir}', file=sys.stderr)
        return 2

    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    violations: list[str] = []

    # 1. Check scene code files for primitive patterns
    for ext in ('.py', '.tsx', '.ts', '.js', '.mjs'):
        for f in os.listdir(scene_dir):
            if f.endswith(ext):
                violations.extend(check_code(os.path.join(scene_dir, f)))

    # 2. Check for forbidden file types
    violations.extend(check_files(scene_dir, project_root))

    # 3. Check path boundaries
    violations.extend(check_path_bounds(scene_dir, project_root))

    if violations:
        print('PRIMITIVE_VIOLATIONS:')
        for v in violations:
            print(f'  - {v}')
        return 1

    print('PRIMITIVE_OK')
    return 0


if __name__ == '__main__':
    sys.exit(main())
