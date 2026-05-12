#!/usr/bin/env python3
"""bin/sandbox-check.py
Detect dangerous Python call patterns in scene code.

Usage:
    sandbox-check.py <scene_file>

Exit: 0 = pass, 1 = violations found, 2 = argument or file error
"""

import argparse
import re
import sys

# Dangerous patterns with no legitimate use in math animation scenes
SANDBOX_PATTERNS = [
    # Subprocess execution
    (r'\bsubprocess\b', 'subprocess — arbitrary command execution'),
    (r'\bos\.system\s*\(', 'os.system() — arbitrary shell command'),
    (r'\bos\.popen\s*\(', 'os.popen() — arbitrary shell command'),
    # Dynamic import bypass
    (r'\b__import__\s*\(', '__import__() — dynamic import bypass'),
    # Network access
    (r'\bimport\s+socket\b', 'socket — raw network access'),
    (r'\bfrom\s+socket\s+import\b', 'socket — raw network access'),
    (r'\bimport\s+requests\b', 'requests — HTTP client'),
    (r'\bfrom\s+requests\s+import\b', 'requests — HTTP client'),
    (r'\bimport\s+urllib\b', 'urllib — HTTP client'),
    (r'\bfrom\s+urllib', 'urllib — HTTP client'),
    # Filesystem destruction
    (r'\bshutil\.rmtree\s*\(', 'shutil.rmtree() — recursive delete'),
    (r'\bos\.remove\s*\(', 'os.remove() — file deletion'),
    (r'\bos\.rmdir\s*\(', 'os.rmdir() — directory deletion'),
    # Sensitive absolute paths
    (r'open\s*\(\s*[\'"]/', 'open() reading absolute path (potential data leak)'),
    # Process termination
    (r'\bos\.kill\s*\(', 'os.kill() — process termination'),
    (r'\bsys\.exit\s*\(', 'sys.exit() — premature process termination'),
]


def check(code: str) -> list[str]:
    violations = []
    for pattern, description in SANDBOX_PATTERNS:
        if re.search(pattern, code):
            violations.append(description)
    return violations


def main() -> int:
    parser = argparse.ArgumentParser(
        description='Detect dangerous Python call patterns.',
        epilog='Exit: 0=pass, 1=violations, 2=error',
    )
    parser.add_argument('scene_file', help='Path to scene source file')
    args = parser.parse_args()

    try:
        with open(args.scene_file, encoding='utf-8') as f:
            code = f.read()
    except OSError as e:
        print(f'FATAL: Cannot read scene: {e}', file=sys.stderr)
        return 2

    violations = check(code)
    if violations:
        print('SANDBOX_VIOLATIONS:')
        for v in violations:
            print(f'  - {v}')
        return 1

    print('SANDBOX_OK')
    return 0


if __name__ == '__main__':
    sys.exit(main())
