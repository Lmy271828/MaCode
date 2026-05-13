#!/usr/bin/env python3
"""bin/checks/shader_registry.py
Layer 1 check: manifest shader declarations vs actual assets.

Validates that shaders listed in manifest.json['shaders'] exist in
assets/shaders/ as pre-renderable directories.

Usage:
    shader_registry.py --scene-dir scenes/02_shader_mc/
"""

import argparse
import json
import os
import sys

_SCRIPT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _SCRIPT_DIR not in sys.path:
    sys.path.insert(0, _SCRIPT_DIR)

from checks._utils import get_project_root, load_manifest


def fail(msg: str):
    print(msg, file=sys.stderr)
    sys.exit(1)


def check(scene_dir: str) -> dict:
    manifest = load_manifest(scene_dir)
    declared_shaders = manifest.get('shaders', [])

    project_root = get_project_root()
    shaders_dir = os.path.join(project_root, 'assets', 'shaders')

    segment_results = []
    global_status = 'pass'

    for shader_name in declared_shaders:
        shader_path = os.path.join(shaders_dir, shader_name)
        seg_status = 'pass'
        issues = []

        if not os.path.isdir(shader_path):
            seg_status = 'error'
            issues.append({
                'type': 'shader_missing',
                'severity': 'error',
                'message': f'Shader "{shader_name}" declared in manifest but not found in assets/shaders/',
                'fixable': True,
                'fix_confidence': 0.9,
                'fix': {
                    'strategy': 'add_shader_asset',
                    'action': 'create_shader_directory',
                    'params': {'path': f'assets/shaders/{shader_name}/'},
                },
            })
        else:
            # Check for expected files (frag shader or pre-rendered frames)
            has_frag = any(
                f.endswith('.frag') or f.endswith('.glsl')
                for f in os.listdir(shader_path)
            )
            has_frames = os.path.isdir(os.path.join(shader_path, 'frames'))
            if not has_frag and not has_frames:
                seg_status = 'warning'
                issues.append({
                    'type': 'shader_empty',
                    'severity': 'warning',
                    'message': (
                        f'Shader dir "{shader_name}" exists but contains '
                        f'no .frag/.glsl source or pre-rendered frames/'
                    ),
                    'fixable': True,
                    'fix_confidence': 0.8,
                    'fix': {
                        'strategy': 'add_shader_source',
                        'action': 'add_frag_or_prerender',
                        'params': {'shader_dir': f'assets/shaders/{shader_name}/'},
                        'hint': (
                            f'在 assets/shaders/{shader_name}/ 下添加 .frag 或 .glsl 源码文件，'
                            f'或运行 `macode shader render assets/shaders/{shader_name}/` 预渲染帧序列'
                        ),
                    },
                })

        segment_results.append({'id': shader_name, 'status': seg_status, 'issues': issues})
        if seg_status != 'pass' and global_status == 'pass':
            global_status = seg_status

    return {
        'check': 'shader_registry',
        'layer': 'layer1',
        'scene': os.path.basename(os.path.normpath(scene_dir)),
        'status': global_status,
        'segments': segment_results,
    }


def main():
    parser = argparse.ArgumentParser(
        description='Layer 1: manifest shader registry consistency.',
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
