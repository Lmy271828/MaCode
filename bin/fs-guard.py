#!/usr/bin/env python3
"""bin/fs-guard.py
Filesystem boundary guard — ensure Agent only writes to allowed directories.

Usage:
    fs-guard.py <scene_dir>

Exit: 0 = pass, 1 = violations found, 2 = argument or file error
"""

import argparse
import os
import sys

# Directories that Agent is allowed to write to
ALLOWED_PREFIXES = [
    'scenes/',
    'assets/',
    'output/',
    '.agent/',
]

# Directories that Agent must NEVER write to
FORBIDDEN_PREFIXES = [
    'engines/',
    'bin/',
    'pipeline/',
    'tests/',
    'docs/',
]

# Files that Agent must NEVER modify
FORBIDDEN_FILES = {
    'project.yaml',
    'requirements.txt',
    'package.json',
    'package-lock.json',
}


def is_allowed_path(path: str, project_root: str) -> tuple[bool, str]:
    rel = os.path.relpath(path, project_root)
    basename = os.path.basename(path)

    if basename in FORBIDDEN_FILES:
        return False, f'forbidden file: {basename}'

    for prefix in FORBIDDEN_PREFIXES:
        if rel.startswith(prefix):
            return False, f'forbidden directory: {prefix}'

    for prefix in ALLOWED_PREFIXES:
        if rel.startswith(prefix):
            return True, ''

    return False, f'path not in allowed list: {rel}'


def main() -> int:
    parser = argparse.ArgumentParser(
        description='Filesystem boundary guard.',
        epilog='Exit: 0=pass, 1=violations, 2=error',
    )
    parser.add_argument('scene_dir', help='Path to scene directory')
    args = parser.parse_args()

    scene_dir = os.path.abspath(args.scene_dir)
    if not os.path.isdir(scene_dir):
        print(f'FATAL: Not a directory: {scene_dir}', file=sys.stderr)
        return 2

    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    ok, reason = is_allowed_path(scene_dir, project_root)
    if not ok:
        print(f'FS_VIOLATION: {scene_dir}: {reason}')
        print('Agent may only write to scenes/, assets/, output/, .agent/')
        return 1

    print('FS_OK')
    return 0


if __name__ == '__main__':
    sys.exit(main())
