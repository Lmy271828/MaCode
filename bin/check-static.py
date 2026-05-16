#!/usr/bin/env python3
"""bin/check-static.py
基于幕的静态检查，不渲染画面（秒级完成）。

用法:
    check-static.py scenes/04_base_demo/

Registry Architecture:
    This script is now a thin runner over bin/check-runner.py for layer1 checks.
    Individual detection logic lives in bin/checks/*.py.
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
from project_engine import find_project_root, resolve_engine_from_manifest


def fail(msg: str):
    print(msg, file=sys.stderr)
    sys.exit(1)


def run_registry_checks(scene_dir: str, engine: str = None) -> dict:
    """Delegate to check-runner.py for layer1 checks."""
    cmd = [sys.executable, os.path.join(_SCRIPT_DIR, 'check-runner.py'), scene_dir, '--layer', 'layer1']
    if engine:
        cmd += ['--engine', engine]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode in (0, 1) and result.stdout.strip():
        return json.loads(result.stdout)
    # Defensive: empty stdout or unexpected failure — synthesize error report
    error_msg = result.stderr.strip() or 'check-runner.py produced no output'
    return {
        'scene': os.path.basename(os.path.normpath(scene_dir)),
        'status': 'error',
        'segments': [],
        'issues': [{'type': 'runner_failed', 'message': error_msg}],
    }


def check_composite_or_unified(scene_dir: str, manifest: dict, manifest_type: str):
    """递归检查 composite / composite-unified 的子场景。"""
    segments = manifest.get('segments', [])
    results = []
    for seg in segments:
        seg_id = seg.get('id', 'unknown')
        seg_dir = os.path.join(scene_dir, seg.get('scene_dir', ''))
        if not os.path.isdir(seg_dir):
            results.append({
                'id': seg_id,
                'status': 'error',
                'issues': [{'type': 'dir_missing', 'message': f'Segment dir not found: {seg_dir}'}]
            })
            continue
        result = subprocess.run(
            [sys.executable, __file__, seg_dir],
            capture_output=True, text=True
        )
        if result.returncode == 0:
            data = json.loads(result.stdout)
            results.append({
                'id': seg_id,
                'status': data.get('status', 'unknown'),
                'sub_segments': data.get('segments', []),
                'issues': data.get('issues', []),
            })
        else:
            results.append({
                'id': seg_id,
                'status': 'error',
                'issues': [{'type': 'check_failed', 'message': result.stderr.strip()}]
            })

    output = {
        'scene': os.path.basename(os.path.normpath(scene_dir)),
        'type': manifest_type,
        'timestamp': datetime.now(UTC).isoformat(),
        'segments': results,
    }
    print(json.dumps(output, indent=2, ensure_ascii=False))


def main():
    parser = argparse.ArgumentParser(
        description='Static scene checker (no rendering). '
                    'Validates segment consistency, duration and formula density.',
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

    manifest_type = manifest.get('type', 'scene')
    if manifest_type == 'composite-unified':
        check_composite_or_unified(scene_dir, manifest, manifest_type)
        return

    project_root = find_project_root(scene_dir)
    engine = resolve_engine_from_manifest(manifest, scene_dir, project_root)
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
