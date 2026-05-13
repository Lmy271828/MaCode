#!/usr/bin/env python3
"""bin/checks/formula_density.py
Layer 1 check: formula density per segment.

Usage:
    formula_density.py --scene-dir scenes/04_base_demo/
"""

import argparse
import json
import os
import sys

_SCRIPT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _SCRIPT_DIR not in sys.path:
    sys.path.insert(0, _SCRIPT_DIR)

from checks._utils import (
    count_formulas,
    extract_segments_from_source,
    find_function_blocks,
    find_source_file,
    get_code_block,
    load_manifest,
)


def fail(msg: str):
    print(msg, file=sys.stderr)
    sys.exit(1)


def check(scene_dir: str) -> dict:
    manifest = load_manifest(scene_dir)
    source_path = find_source_file(scene_dir)
    if not source_path:
        return {
            'check': 'formula_density',
            'layer': 'layer1',
            'scene': os.path.basename(os.path.normpath(scene_dir)),
            'status': 'error',
            'segments': [],
            'issues': [{'type': 'source_missing', 'severity': 'error', 'message': 'scene source not found (scene.py or scene.tsx)'}],
        }

    resolution = manifest.get('resolution', [1920, 1080])
    area = resolution[0] * resolution[1]

    manifest_segments = manifest.get('segments', [])
    extracted_segments = extract_segments_from_source(source_path)
    manifest_by_id = {s['id']: s for s in manifest_segments}
    is_python = source_path.endswith('.py')
    func_blocks = find_function_blocks(source_path) if is_python else {}
    sorted_funcs = sorted(func_blocks.values(), key=lambda x: x[0])

    segment_results = []
    global_status = 'pass'

    for seg in extracted_segments:
        seg_id = seg['id']
        m_seg = manifest_by_id.get(seg_id)
        if m_seg is None:
            continue

        block_start = m_seg['line_start']
        block_end = m_seg['line_end']
        if is_python:
            for fs, fe, _fname in sorted_funcs:
                if fs > m_seg['line_start']:
                    block_start = fs
                    block_end = fe
                    break
        else:
            # For .tsx, extend to end of file (single scene per file)
            with open(source_path, encoding='utf-8') as f:
                block_end = len(f.readlines())

        code_block = get_code_block(source_path, block_start, block_end)
        formula_count = count_formulas(code_block, is_mc=not is_python)
        seg_status = 'pass'
        issues = []

        if formula_count > 0:
            pixels_per_formula = area / formula_count
            if pixels_per_formula < 50000:
                seg_status = 'warning'
                max_formulas = int(area / 50000)
                excess = formula_count - max_formulas
                hint = (
                    f'当前分辨率 {resolution} 下最多支持 {max_formulas} 个公式，'
                    f'建议删除 {excess} 个公式，或提升分辨率至更大尺寸'
                )
                issues.append({
                    'type': 'formula_density',
                    'severity': 'warning',
                    'message': (
                        f'公式密度过高：{formula_count} 个公式，'
                        f'每公式仅 {pixels_per_formula:.0f} 像素（建议 ≥ 50000）'
                    ),
                    'suggested_lines': [block_start, block_end],
                    'fixable': True,
                    'fix_confidence': 0.7,
                    'fix': {
                        'strategy': 'adjust_scale',
                        'action': 'reduce_formula_count_or_increase_resolution',
                        'params': {
                            'pixels_per_formula': pixels_per_formula,
                            'max_formulas': max_formulas,
                        },
                        'hint': hint,
                    },
                })

        segment_results.append({'id': seg_id, 'status': seg_status, 'issues': issues})
        if seg_status != 'pass' and global_status == 'pass':
            global_status = seg_status

    return {
        'check': 'formula_density',
        'layer': 'layer1',
        'scene': os.path.basename(os.path.normpath(scene_dir)),
        'status': global_status,
        'segments': segment_results,
    }


def main():
    parser = argparse.ArgumentParser(description='Layer 1: formula density check.')
    parser.add_argument('--scene-dir', required=True, help='Path to scene directory')
    args = parser.parse_args()

    if not os.path.isdir(args.scene_dir):
        fail(f"Error: directory not found: {args.scene_dir}")

    report = check(args.scene_dir)
    print(json.dumps(report, indent=2, ensure_ascii=False))
    sys.exit(0 if report['status'] == 'pass' else 1)


if __name__ == '__main__':
    main()
