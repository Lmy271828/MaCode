#!/usr/bin/env python3
"""bin/check-frames.py
基于幕 keyframes 的运行时布局检查（Layer 2）。

用法:
    check-frames.py scenes/04_base_demo/

NOTE:
    Layer 2 现在通过运行时布局快照（layout_snapshots.jsonl）检测文本重叠。
    本脚本是 check-runner.py --layer layer2 的 backward-compatible 包装器。
"""

import argparse
import json
import os
import subprocess
import sys
from datetime import UTC, datetime

_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
if _SCRIPT_DIR not in sys.path:
    sys.path.insert(0, _SCRIPT_DIR)

from checks._utils import write_check_report


def fail(msg: str):
    print(msg, file=sys.stderr)
    sys.exit(1)


def run_registry_checks(scene_dir: str, engine: str = None) -> dict:
    """Delegate to check-runner.py for layer2 checks."""
    cmd = [sys.executable, os.path.join(_SCRIPT_DIR, 'check-runner.py'), scene_dir, '--layer', 'layer2']
    if engine:
        cmd += ['--engine', engine]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode in (0, 1, 2):
        return json.loads(result.stdout)
    fail(f"check-runner.py failed: {result.stderr.strip()}")


def main():
    parser = argparse.ArgumentParser(
        description='Keyframe-based sampled frame checker. '
                    'Detects overlaps, readability and focus issues.',
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument('scene_dir', help='Path to scene directory')
    parser.add_argument('--output', default=None, help='Write report to file (with locking)')
    args = parser.parse_args()

    scene_dir = args.scene_dir
    if not os.path.isdir(scene_dir):
        fail(f"Error: directory not found: {scene_dir}")

    manifest_path = os.path.join(scene_dir, 'manifest.json')
    if not os.path.exists(manifest_path):
        fail(f"Error: manifest.json not found: {manifest_path}")

    with open(manifest_path, encoding='utf-8') as f:
        manifest = json.load(f)

    engine = manifest.get('engine', 'manim')
    report = run_registry_checks(scene_dir, engine=engine)

    # Backward-compatible output format
    output = {
        'scene': report.get('scene', os.path.basename(os.path.normpath(scene_dir))),
        'timestamp': datetime.now(UTC).isoformat(),
        'segments': report.get('segments', []),
    }
    if args.output:
        write_check_report(args.output, output)
    print(json.dumps(output, indent=2, ensure_ascii=False))


if __name__ == '__main__':
    main()
