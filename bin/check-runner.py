#!/usr/bin/env python3
"""bin/check-runner.py
Registry-based check runner.

Loads engine-specific check-registry.json and executes selected checks,
aggregating results into a unified report.

Usage:
    check-runner.py <scene_dir> [--layer layer1|layer2|layer3] [--check <id>]
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

from checks._utils import load_manifest


def fail(msg: str):
    print(msg, file=sys.stderr)
    sys.exit(1)


def load_registry(engine: str) -> dict:
    registry_path = os.path.join('engines', engine, 'check-registry.json')
    if not os.path.exists(registry_path):
        fail(f"Error: check-registry.json not found for engine '{engine}': {registry_path}")
    with open(registry_path, encoding='utf-8') as f:
        return json.load(f)


def discover_checks(registry: dict, layer: str = None, check_ids: list = None) -> list:
    """Return list of (check_id, check_config) tuples to run."""
    results = []
    layers = registry.get('layers', {})

    if layer:
        layer_data = layers.get(layer, {})
        checks = layer_data.get('checks', {})
        for cid, cfg in checks.items():
            if check_ids is None or cid in check_ids:
                results.append((cid, cfg))
        return results

    for _lname, ldata in layers.items():
        checks = ldata.get('checks', {})
        for cid, cfg in checks.items():
            if check_ids is not None and cid not in check_ids:
                continue
            if check_ids is None and not cfg.get('enabled_by_default', False):
                continue
            results.append((cid, cfg))
    return results


def run_check(check_id: str, cfg: dict, scene_dir: str) -> dict:
    script = cfg.get('script', '')
    if not script:
        return {
            'check': check_id,
            'status': 'error',
            'issues': [{'type': 'config_error', 'message': 'Missing script path in registry'}],
        }

    script_path = os.path.join(os.path.dirname(_SCRIPT_DIR), script)
    if not os.path.exists(script_path):
        return {
            'check': check_id,
            'status': 'error',
            'issues': [{'type': 'script_missing', 'message': f'Script not found: {script_path}'}],
        }

    cmd = [sys.executable, script_path, '--scene-dir', scene_dir]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
        if result.returncode in (0, 1):
            # 0 = pass, 1 = warning/issue — both return valid JSON
            return json.loads(result.stdout)
        else:
            return {
                'check': check_id,
                'status': 'error',
                'issues': [{'type': 'check_failed', 'message': result.stderr.strip() or 'Unknown error'}],
            }
    except json.JSONDecodeError as e:
        return {
            'check': check_id,
            'status': 'error',
            'issues': [{'type': 'invalid_json', 'message': f'Failed to parse check output: {e}'}],
        }
    except Exception as e:
        return {
            'check': check_id,
            'status': 'error',
            'issues': [{'type': 'exception', 'message': str(e)}],
        }


def merge_segment_results(check_results: list) -> list:
    """Merge per-check segment results into unified segment records."""
    by_id = {}
    for cr in check_results:
        for seg in cr.get('segments', []):
            seg_id = seg['id']
            if seg_id not in by_id:
                by_id[seg_id] = {
                    'id': seg_id,
                    'status': 'pass',
                    'issues': [],
                }
            by_id[seg_id]['issues'].extend(seg.get('issues', []))
            if seg.get('status') != 'pass':
                by_id[seg_id]['status'] = seg['status']
    return list(by_id.values())


def main():
    parser = argparse.ArgumentParser(
        description='Registry-based check runner for MaCode scenes.',
    )
    parser.add_argument('scene_dir', help='Path to scene directory')
    parser.add_argument('--layer', choices=['layer1', 'layer2', 'layer3'],
                        help='Run only checks from this layer')
    parser.add_argument('--check', action='append', dest='check_ids',
                        help='Run specific check(s) by ID')
    parser.add_argument('--engine', help='Override engine (default from manifest)')
    parser.add_argument('--format', choices=['unified', 'raw'], default='unified',
                        help='Output format: unified (merged) or raw (per-check)')
    args = parser.parse_args()

    scene_dir = args.scene_dir
    if not os.path.isdir(scene_dir):
        fail(f"Error: directory not found: {scene_dir}")

    manifest = load_manifest(scene_dir)
    engine = args.engine or manifest.get('engine', 'manim')
    registry = load_registry(engine)
    checks = discover_checks(registry, layer=args.layer, check_ids=args.check_ids)

    if not checks:
        fail("Error: no checks matched the given criteria")

    check_results = []
    for cid, cfg in checks:
        report = run_check(cid, cfg, scene_dir)
        check_results.append(report)

    if args.format == 'raw':
        output = {
            'scene': os.path.basename(os.path.normpath(scene_dir)),
            'engine': engine,
            'timestamp': datetime.now(UTC).isoformat(),
            'checks': check_results,
        }
    else:
        merged_segments = merge_segment_results(check_results)
        global_status = 'pass'
        for seg in merged_segments:
            if seg['status'] != 'pass':
                global_status = seg['status']
                break
        output = {
            'scene': os.path.basename(os.path.normpath(scene_dir)),
            'engine': engine,
            'timestamp': datetime.now(UTC).isoformat(),
            'status': global_status,
            'segments': merged_segments,
        }

    print(json.dumps(output, indent=2, ensure_ascii=False))
    sys.exit(0 if output.get('status') == 'pass' else 1)


if __name__ == '__main__':
    main()
