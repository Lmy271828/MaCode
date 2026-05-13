#!/usr/bin/env python3
"""bin/checks/layout_overlap.py
Layer 2 check: runtime text overlap detection via layout snapshots.

Reads normalized layout snapshots (.jsonl) and detects AABB intersections
between text/formula objects at each keyframe.

Usage:
    layout_overlap.py --scene-dir scenes/04_base_demo/
"""

import argparse
import json
import os
import sys

_SCRIPT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _SCRIPT_DIR not in sys.path:
    sys.path.insert(0, _SCRIPT_DIR)


def fail(msg: str):
    print(msg, file=sys.stderr)
    sys.exit(1)


def aabb_intersect(a: dict, b: dict) -> bool:
    """AABB intersection in normalized [0,1] coordinates."""
    return (
        a['x'] < b['x'] + b['w'] and a['x'] + a['w'] > b['x'] and
        a['y'] < b['y'] + b['h'] and a['y'] + a['h'] > b['y']
    )


def overlap_area(a: dict, b: dict) -> float:
    """Compute normalized overlap area between two bboxes."""
    if not aabb_intersect(a, b):
        return 0.0
    ix = max(0.0, min(a['x'] + a['w'], b['x'] + b['w']) - max(a['x'], b['x']))
    iy = max(0.0, min(a['y'] + a['h'], b['y'] + b['h']) - max(a['y'], b['y']))
    return ix * iy


def check_snapshot(snapshot: dict) -> list[dict]:
    """Detect text overlaps in a single snapshot."""
    objects = snapshot.get('objects', [])
    text_objects = [o for o in objects if o.get('type') in ('text', 'formula')]
    issues = []

    for i, a in enumerate(text_objects):
        for b in text_objects[i + 1:]:
            if aabb_intersect(a['bbox'], b['bbox']):
                area = overlap_area(a['bbox'], b['bbox'])
                issues.append({
                    'type': 'text_overlap',
                    'severity': 'warning',
                    'message': (
                        f"文本对象 '{a['id']}' 与 '{b['id']}' "
                        f"在 t={snapshot.get('timestamp', 0):.2f}s 重叠，"
                        f"重叠面积 {area:.1%}"
                    ),
                    'timestamp': snapshot.get('timestamp', 0),
                    'objects': [a['id'], b['id']],
                    'overlap_area': round(area, 4),
                    'fixable': True,
                    'fix_confidence': 0.8,
                    'fix': {
                        'strategy': 'reposition',
                        'action': 'adjust_vertical_spacing',
                        'hint': (
                            f"调整 '{a['id']}' 或 '{b['id']}' 的 y 坐标，"
                            f"使两者之间留出至少 0.02 的垂直间距"
                        ),
                    },
                })
    return issues


def _find_snapshot_file(scene_dir: str) -> str:
    """Find layout_snapshots.jsonl in common locations."""
    scene_name = os.path.basename(os.path.normpath(scene_dir))
    candidates = [
        os.path.join(scene_dir, 'layout_snapshots.jsonl'),
        os.path.join('.agent', 'tmp', scene_name, 'layout_snapshots.jsonl'),
        os.path.join('.agent', 'tmp', scene_name, 'frames', 'layout_snapshots.jsonl'),
    ]
    for c in candidates:
        if os.path.exists(c):
            return c
    return candidates[0]  # default


def check(scene_dir: str) -> dict:
    """Run layout overlap check and return a report dict."""
    snapshot_path = _find_snapshot_file(scene_dir)
    if not os.path.exists(snapshot_path):
        return {
            'check': 'layout_overlap',
            'layer': 'layer2',
            'scene': os.path.basename(os.path.normpath(scene_dir)),
            'status': 'pass',
            'segments': [],
            'issues': [],
        }

    segment_results = []
    global_status = 'pass'

    with open(snapshot_path, encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                snapshot = json.loads(line)
            except json.JSONDecodeError:
                continue

            issues = check_snapshot(snapshot)
            seg_status = 'warning' if issues else 'pass'

            segment_results.append({
                'id': f"t{snapshot.get('timestamp', 0):.2f}",
                'status': seg_status,
                'issues': issues,
            })

            if seg_status != 'pass' and global_status == 'pass':
                global_status = seg_status

    return {
        'check': 'layout_overlap',
        'layer': 'layer2',
        'scene': os.path.basename(os.path.normpath(scene_dir)),
        'status': global_status,
        'segments': segment_results,
    }


def main():
    parser = argparse.ArgumentParser(
        description='Layer 2: runtime text overlap detection.',
    )
    parser.add_argument('--scene-dir', required=True, help='Path to scene directory')
    args = parser.parse_args()

    if not os.path.isdir(args.scene_dir):
        fail(f"Error: directory not found: {args.scene_dir}")

    report = check(args.scene_dir)
    print(json.dumps(report, indent=2, ensure_ascii=False))
    sys.exit(0 if report['status'] == 'pass' else 1)


if __name__ == '__main__':
    main()
