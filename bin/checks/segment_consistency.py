#!/usr/bin/env python3
"""bin/checks/segment_consistency.py
Layer 1 check: manifest↔source segment alignment.

Usage:
    segment_consistency.py --scene-dir scenes/04_base_demo/
"""

import argparse
import json
import os
import sys

_SCRIPT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _SCRIPT_DIR not in sys.path:
    sys.path.insert(0, _SCRIPT_DIR)

from checks._utils import extract_segments_from_source, load_manifest, segments_equal


def fail(msg: str):
    print(msg, file=sys.stderr)
    sys.exit(1)


def check(scene_dir: str) -> dict:
    manifest = load_manifest(scene_dir)
    source_path = os.path.join(scene_dir, 'scene.py')
    if not os.path.exists(source_path):
        return {
            'check': 'segment_consistency',
            'layer': 'layer1',
            'scene': os.path.basename(os.path.normpath(scene_dir)),
            'status': 'error',
            'segments': [],
            'issues': [{'type': 'source_missing', 'message': 'scene.py not found'}],
        }

    manifest_segments = manifest.get('segments', [])
    extracted_segments = extract_segments_from_source(source_path)
    manifest_by_id = {s['id']: s for s in manifest_segments}
    extracted_by_id = {s['id']: s for s in extracted_segments}
    all_ids = sorted(set(manifest_by_id) | set(extracted_by_id))

    segment_results = []
    global_status = 'pass'

    for seg_id in all_ids:
        m_seg = manifest_by_id.get(seg_id)
        e_seg = extracted_by_id.get(seg_id)
        seg_status = 'pass'
        issues = []

        if m_seg is None:
            seg_status = 'warning'
            issues.append({
                'type': 'manifest_missing',
                'message': f'Segment "{seg_id}" 存在于源码注释但不在 manifest.json 中',
                'suggested_lines': [e_seg.get('line_start', 0), e_seg.get('line_end', 0)] if e_seg else [0, 0],
                'fixable': True,
                'fix_confidence': 0.9,
                'fix': {
                    'strategy': 'align_segment_comment',
                    'action': 'add_to_manifest',
                },
            })
        elif e_seg is None:
            seg_status = 'warning'
            issues.append({
                'type': 'source_missing',
                'message': f'Segment "{seg_id}" 存在于 manifest.json 但不在源码注释中',
                'suggested_lines': [m_seg.get('line_start', 0), m_seg.get('line_end', 0)],
                'fixable': True,
                'fix_confidence': 0.9,
                'fix': {
                    'strategy': 'align_segment_comment',
                    'action': 'add_source_comment',
                },
            })
        elif not segments_equal(m_seg, e_seg):
            seg_status = 'warning'
            issues.append({
                'type': 'comment_manifest_mismatch',
                'message': f'Segment "{seg_id}" 的注释与 manifest.json 内容不一致',
                'suggested_lines': [e_seg.get('line_start', 0), e_seg.get('line_end', 0)],
                'fixable': True,
                'fix_confidence': 0.85,
                'fix': {
                    'strategy': 'align_segment_comment',
                    'action': 'sync_manifest_to_comment',
                },
            })

        segment_results.append({'id': seg_id, 'status': seg_status, 'issues': issues})
        if seg_status != 'pass' and global_status == 'pass':
            global_status = seg_status

    return {
        'check': 'segment_consistency',
        'layer': 'layer1',
        'scene': os.path.basename(os.path.normpath(scene_dir)),
        'status': global_status,
        'segments': segment_results,
    }


def main():
    parser = argparse.ArgumentParser(
        description='Layer 1: manifest↔source segment consistency.',
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
