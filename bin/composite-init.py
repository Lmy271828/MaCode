#!/usr/bin/env python3
"""bin/composite-init.py
Composite 场景模板脚手架工具。

用法:
    composite-init.py init <scene_path> --template <template_name>
        从模板创建新的 composite 场景。
        模板: intro-main-outro, problem-solution

    composite-init.py add-segment <scene_path> <seg_id> [--after <existing_seg>]
        向现有 composite 场景添加新 segment。
"""

import argparse
import json
import os
import sys

TEMPLATES = {
    'intro-main-outro': [
        {'id': 'intro', 'duration': 2.0},
        {'id': 'main', 'duration': 5.0},
        {'id': 'outro', 'duration': 1.0},
    ],
    'problem-solution': [
        {'id': 'problem', 'duration': 3.0},
        {'id': 'solution', 'duration': 5.0},
    ],
}

DEFAULT_SCENE_PY = '''"""{seg_id} segment of {scene_name}."""

from templates.scene_base import MaCodeScene
from manim import *


class {class_name}(MaCodeScene):
    def construct(self):
        # TODO: implement {seg_id} segment
        text = Text("{seg_id}", font_size=48)
        self.play(FadeIn(text), run_time=0.5)
        self.wait({duration})
'''

DEFAULT_SCENE_TSX = '''import {{makeScene2D}} from '@motion-canvas/2d';
import {{Txt}} from '@motion-canvas/2d';
import {{createRef}} from '@motion-canvas/core';

/**
 * {seg_id} segment of {scene_name}
 */
export default makeScene2D(function* (view) {{
  const text = createRef<Txt>();

  view.add(
    <Txt
      ref={{text}}
      text="{seg_id}"
      fontSize={{64}}
      fill="white"
    />
  );

  yield* text().scale(1.2, 0.5);
  yield* text().scale(1, 0.5);
}});
'''

def make_manifest(engine: str, duration: float) -> dict:
    if engine == 'motion_canvas':
        return {
            'engine': 'motion_canvas',
            'template': 'makeScene2D',
            'duration': duration,
            'fps': 30,
            'resolution': [1920, 1080],
            'assets': [],
            'dependencies': [],
        }
    return {
        'duration': duration,
        'fps': 30,
        'resolution': [1920, 1080],
        'engine': 'manimgl',
    }


def sanitize_class_name(seg_id: str) -> str:
    """将 segment id 转为合法的 Python 类名。"""
    return ''.join(word.capitalize() for word in seg_id.split('_')) + 'Scene'


def write_file(path: str, content: str):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, 'w', encoding='utf-8') as f:
        f.write(content)


def compact_json(data: dict) -> str:
    """输出 compact JSON，但将短列表强制保持单行以兼容 sed 校验。"""
    raw = json.dumps(data, indent=2, ensure_ascii=False)
    import re
    raw = re.sub(r'"resolution": \[\s*(\d+),\s*(\d+)\s*\]', r'"resolution": [\1, \2]', raw)
    return raw


def init_scene(scene_path: str, template_name: str, engine: str = 'manimgl'):
    if template_name not in TEMPLATES:
        print(f"Error: unknown template '{template_name}'. Available: {', '.join(TEMPLATES.keys())}", file=sys.stderr)
        sys.exit(1)

    scene_path = os.path.normpath(scene_path)
    if os.path.exists(scene_path):
        print(f"Error: directory already exists: {scene_path}", file=sys.stderr)
        sys.exit(1)

    scene_name = os.path.basename(scene_path)
    segments = TEMPLATES[template_name]

    # 选择模板
    if engine == 'motion_canvas':
        scene_template = DEFAULT_SCENE_TSX
        scene_ext = '.tsx'
    else:
        scene_template = DEFAULT_SCENE_PY
        scene_ext = '.py'

    # 创建 shots 子目录和 segment 文件
    manifest_segments = []
    for i, seg in enumerate(segments):
        seg_id = seg['id']
        duration = seg['duration']
        seg_dir = f'shots/{i:02d}_{seg_id}'
        full_seg_dir = os.path.join(scene_path, seg_dir)

        # segment manifest
        seg_manifest = make_manifest(engine, duration)
        write_file(os.path.join(full_seg_dir, 'manifest.json'),
                   compact_json(seg_manifest) + '\n')

        # segment scene file
        scene_content = scene_template.format(
            seg_id=seg_id,
            scene_name=scene_name,
            class_name=sanitize_class_name(seg_id),
            duration=duration - 0.5
        )
        write_file(os.path.join(full_seg_dir, f'scene{scene_ext}'), scene_content)

        manifest_segments.append({
            'id': seg_id,
            'scene_dir': seg_dir,
        })

    # 创建顶层 composite manifest
    composite_manifest = {
        'type': 'composite',
        'segments': manifest_segments,
        'meta': {
            'title': scene_name,
            'author': 'agent',
            'tags': [template_name],
        }
    }
    write_file(os.path.join(scene_path, 'manifest.json'),
               compact_json(composite_manifest) + '\n')

    print(f"[init] Created composite scene: {scene_path}")
    print(f"[init] Template: {template_name}")
    print(f"[init] Engine: {engine}")
    print(f"[init] Segments: {len(segments)}")
    for seg in segments:
        print(f"  - {seg['id']} ({seg['duration']}s)")


def add_segment(scene_path: str, seg_id: str, after: str = None, engine: str = None):
    scene_path = os.path.normpath(scene_path)
    manifest_path = os.path.join(scene_path, 'manifest.json')

    if not os.path.isfile(manifest_path):
        print(f"Error: manifest.json not found: {manifest_path}", file=sys.stderr)
        sys.exit(1)

    with open(manifest_path, encoding='utf-8') as f:
        manifest = json.load(f)

    if manifest.get('type') not in ('composite', 'composite-unified'):
        print("Error: manifest type must be composite or composite-unified", file=sys.stderr)
        sys.exit(1)

    # 自动检测 engine：从第一个 segment 的 manifest 读取
    if engine is None:
        first_seg = manifest.get('segments', [{}])[0]
        first_dir = first_seg.get('scene_dir') or first_seg.get('shot', '')
        first_manifest = os.path.join(scene_path, first_dir, 'manifest.json')
        if os.path.isfile(first_manifest):
            with open(first_manifest) as f:
                first_data = json.load(f)
            engine = first_data.get('engine', 'manimgl')
        else:
            engine = 'manimgl'

    existing_ids = [s['id'] for s in manifest.get('segments', [])]
    if seg_id in existing_ids:
        print(f"Error: segment '{seg_id}' already exists", file=sys.stderr)
        sys.exit(1)

    # 计算新 segment 的序号
    if after:
        if after not in existing_ids:
            print(f"Error: --after segment '{after}' not found", file=sys.stderr)
            sys.exit(1)
        insert_idx = existing_ids.index(after) + 1
    else:
        insert_idx = len(existing_ids)

    # 生成 segment 目录名
    seg_dir = f'shots/{insert_idx:02d}_{seg_id}'
    full_seg_dir = os.path.join(scene_path, seg_dir)
    if os.path.exists(full_seg_dir):
        print(f"Error: segment directory already exists: {full_seg_dir}", file=sys.stderr)
        sys.exit(1)

    # 创建 segment 文件
    duration = 3.0
    seg_manifest = make_manifest(engine, duration)
    write_file(os.path.join(full_seg_dir, 'manifest.json'),
               compact_json(seg_manifest) + '\n')

    if engine == 'motion_canvas':
        scene_content = DEFAULT_SCENE_TSX.format(
            seg_id=seg_id,
            scene_name=os.path.basename(scene_path),
            class_name=sanitize_class_name(seg_id),
            duration=duration - 0.5
        )
        scene_ext = '.tsx'
    else:
        scene_content = DEFAULT_SCENE_PY.format(
            seg_id=seg_id,
            scene_name=os.path.basename(scene_path),
            class_name=sanitize_class_name(seg_id),
            duration=duration - 0.5
        )
        scene_ext = '.py'
    write_file(os.path.join(full_seg_dir, f'scene{scene_ext}'), scene_content)

    # 更新 composite manifest
    manifest['segments'].insert(insert_idx, {
        'id': seg_id,
        'scene_dir': seg_dir,
    })

    # 重新编号后续 shots 目录（如果需要）
    # 简化处理：不移动现有目录，只更新 manifest 中的 scene_dir

    write_file(manifest_path, compact_json(manifest) + '\n')

    print(f"[add-segment] Added segment '{seg_id}' at index {insert_idx}")
    print(f"[add-segment] Directory: {full_seg_dir}")


def main():
    parser = argparse.ArgumentParser(
        description='Composite scene scaffolding tool.',
        epilog='Templates: intro-main-outro, problem-solution. '
               'Creates manifest.json, shot directories and starter scene files.',
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    subparsers = parser.add_subparsers(dest='command', help='Available commands')

    init_parser = subparsers.add_parser('init', help='Create composite scene from template')
    init_parser.add_argument('scene_path', help='Path to new scene directory')
    init_parser.add_argument('--template', required=True, choices=list(TEMPLATES.keys()),
                             help='Template name')
    init_parser.add_argument('--engine', default='manimgl', choices=['manimgl', 'motion_canvas'],
                             help='Engine for segments (default: manimgl)')

    add_parser = subparsers.add_parser('add-segment', help='Add segment to existing composite')
    add_parser.add_argument('scene_path', help='Path to composite scene directory')
    add_parser.add_argument('seg_id', help='New segment ID')
    add_parser.add_argument('--after', help='Insert after existing segment ID')
    add_parser.add_argument('--engine', choices=['manimgl', 'motion_canvas'],
                             help='Engine for new segment (auto-detected if omitted)')

    args = parser.parse_args()

    if args.command == 'init':
        init_scene(args.scene_path, args.template, args.engine)
    elif args.command == 'add-segment':
        add_segment(args.scene_path, args.seg_id, args.after, args.engine)
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == '__main__':
    main()
