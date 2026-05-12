#!/usr/bin/env python3
"""bin/composite-cache.py
Composite 场景的依赖图缓存 —— 仅重新渲染变更的 segment。

用法:
    composite-cache.py check <composite_scene_dir> <output_dir>
        检查哪些 segment 需要重新渲染。
        输出 JSON: {"segments": [{"id": "...", "hash": "...", "cached": true/false, "video": "..."}]}

    composite-cache.py populate <composite_scene_dir> <output_dir>
        渲染完成后，记录 segment 哈希到缓存映射。

原理:
    1. 对每个 segment，计算其 scene.py + manifest.json 的哈希
    2. 在 .agent/cache/composite/<scene_name>.json 中维护 hash -> video 映射
    3. 如果 segment 哈希未变且缓存视频存在，直接复用
    4. 最终视频 final.mp4 的缓存由 render.sh 负责（当所有 segment 均未变时跳过 concat）
"""

import argparse
import hashlib
import json
import os
import sys


def compute_file_hash(*paths: str) -> str:
    """计算多个文件的内容哈希（SHA-256 前 16 位）。"""
    h = hashlib.sha256()
    for p in paths:
        if os.path.isfile(p):
            with open(p, 'rb') as f:
                h.update(f.read())
    return h.hexdigest()[:16]


def get_cache_index(scene_name: str) -> str:
    return os.path.join('.agent', 'cache', 'composite', f'{scene_name}.json')


def load_cache_index(scene_name: str) -> dict:
    path = get_cache_index(scene_name)
    if os.path.isfile(path):
        with open(path, encoding='utf-8') as f:
            return json.load(f)
    return {}


def save_cache_index(scene_name: str, data: dict):
    path = get_cache_index(scene_name)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def find_scene_file(scene_dir: str) -> str:
    """查找 scene.<ext> 文件。"""
    for candidate in os.listdir(scene_dir):
        if candidate.startswith('scene.') and candidate != 'scene.':
            candidate_path = os.path.join(scene_dir, candidate)
            if os.path.isfile(candidate_path):
                return candidate_path
    return ''


def check_composite(scene_dir: str, output_dir: str):
    """检查 composite 各 segment 的缓存状态。"""
    scene_name = os.path.basename(os.path.normpath(scene_dir))
    manifest_path = os.path.join(scene_dir, 'manifest.json')

    with open(manifest_path, encoding='utf-8') as f:
        manifest = json.load(f)

    segments = manifest.get('segments', [])
    cache_index = load_cache_index(scene_name)
    results = []
    all_cached = True

    for seg in segments:
        seg_id = seg['id']
        seg_dir_rel = seg.get('scene_dir', seg.get('shot', ''))
        seg_dir = os.path.join(scene_dir, seg_dir_rel)
        seg_manifest = os.path.join(seg_dir, 'manifest.json')
        seg_scene = find_scene_file(seg_dir)

        # 计算 segment 哈希（源码 + manifest）
        seg_hash = compute_file_hash(seg_scene, seg_manifest)

        # segment 视频路径（按 render.sh 约定：.agent/tmp/<basename>/final.mp4）
        seg_name = os.path.basename(os.path.normpath(seg_dir_rel))
        seg_video = os.path.join('.agent', 'tmp', seg_name, 'final.mp4')

        # 查找缓存
        cached_video = cache_index.get(seg_hash, '')
        is_cached = bool(cached_video) and os.path.isfile(cached_video)

        if not is_cached:
            all_cached = False

        results.append({
            'id': seg_id,
            'hash': seg_hash,
            'cached': is_cached,
            'video': cached_video if is_cached else seg_video,
        })

    # 额外检查：composite manifest 本身变更也算 cache miss
    composite_hash = compute_file_hash(manifest_path)
    composite_cached = cache_index.get('_composite_hash') == composite_hash and all_cached

    output = {
        'scene': scene_name,
        'composite_hash': composite_hash,
        'all_cached': composite_cached,
        'segments': results,
    }
    print(json.dumps(output, indent=2, ensure_ascii=False))
    return 0 if composite_cached else 1


def populate_composite(scene_dir: str, output_dir: str):
    """渲染完成后，记录 segment 视频到缓存索引。"""
    scene_name = os.path.basename(os.path.normpath(scene_dir))
    manifest_path = os.path.join(scene_dir, 'manifest.json')

    with open(manifest_path, encoding='utf-8') as f:
        manifest = json.load(f)

    segments = manifest.get('segments', [])
    cache_index = load_cache_index(scene_name)

    for seg in segments:
        seg_dir_rel = seg.get('scene_dir', seg.get('shot', ''))
        seg_dir = os.path.join(scene_dir, seg_dir_rel)
        seg_manifest = os.path.join(seg_dir, 'manifest.json')
        seg_scene = find_scene_file(seg_dir)
        seg_hash = compute_file_hash(seg_scene, seg_manifest)

        seg_name = os.path.basename(os.path.normpath(seg_dir_rel))
        video_path = os.path.join('.agent', 'tmp', seg_name, 'final.mp4')
        if os.path.isfile(video_path):
            cache_index[seg_hash] = video_path

    # 记录 composite manifest 哈希
    cache_index['_composite_hash'] = compute_file_hash(manifest_path)

    save_cache_index(scene_name, cache_index)
    print(f"[composite-cache] Updated index for {scene_name} ({len(segments)} segments)")
    return 0


def main():
    parser = argparse.ArgumentParser(
        description='Composite scene dependency cache — re-render only changed segments.',
        epilog='check: outputs JSON cache status. populate: records hashes after render.',
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument('action', choices=['check', 'populate'],
                        help='Action: check cache status or populate after render')
    parser.add_argument('scene_dir', help='Path to composite scene directory')
    parser.add_argument('output_dir', help='Output directory (reserved for future use)')
    args = parser.parse_args()

    action = args.action
    scene_dir = args.scene_dir
    output_dir = args.output_dir

    if action == 'check':
        sys.exit(check_composite(scene_dir, output_dir))
    elif action == 'populate':
        sys.exit(populate_composite(scene_dir, output_dir))
    else:
        print(f"Error: unknown action '{action}' (use check or populate)", file=sys.stderr)
        sys.exit(1)


if __name__ == '__main__':
    main()
