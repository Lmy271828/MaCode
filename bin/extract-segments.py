#!/usr/bin/env python3
"""bin/extract-segments.py
从场景源码中提取 @segment: 注释，输出 segments.json。

用法:
    extract-segments.py scenes/02_fourier/scene.py > scenes/02_fourier/segments.json
    extract-segments.py --sync scenes/02_fourier/  # 同步到 manifest.json
"""

import argparse
import json
import os
import re
import sys

COMMENT_PREFIX = {
    '.py': '#',
    '.ts': '//',
    '.tsx': '//',
    '.js': '//',
}

def extract(filepath):
    ext = os.path.splitext(filepath)[1]
    prefix = COMMENT_PREFIX.get(ext, '#')

    p = re.escape(prefix)
    SEGMENT_RE = re.compile(r'^\s*' + p + r'\s*@segment:(\w+)\s*$')
    TIME_RE = re.compile(r'^\s*' + p + r'\s*@time:([\d.]+)-([\d.]+)s\s*$')
    KEYFRAMES_RE = re.compile(r'^\s*' + p + r'\s*@keyframes:\[(.*?)\]\s*$')
    DESC_RE = re.compile(r'^\s*' + p + r'\s*@description:(.*)$')
    CHECKS_RE = re.compile(r'^\s*' + p + r'\s*@checks:\[(.*?)\]\s*$')

    segments = []
    current = None

    with open(filepath, encoding='utf-8') as f:
        for lineno, line in enumerate(f, 1):
            m = SEGMENT_RE.match(line)
            if m:
                if current:
                    current['line_end'] = lineno - 1
                current = {
                    'id': m.group(1),
                    'file': os.path.basename(filepath),
                    'line_start': lineno,
                }
                segments.append(current)
                continue

            if not current:
                continue

            m = TIME_RE.match(line)
            if m:
                current['time_range'] = [float(m.group(1)), float(m.group(2))]
                continue

            m = KEYFRAMES_RE.match(line)
            if m:
                current['keyframes'] = [
                    float(x.strip()) for x in m.group(1).split(',') if x.strip()
                ]
                continue

            m = DESC_RE.match(line)
            if m:
                current['description'] = m.group(1).strip()
                continue

            m = CHECKS_RE.match(line)
            if m:
                current['checks'] = [
                    x.strip().strip('"\'') for x in m.group(1).split(',') if x.strip()
                ]
                continue

            if line.strip() and not line.strip().startswith(prefix):
                current['line_end'] = lineno - 1
                current = None

    if current and 'line_end' not in current:
        with open(filepath, encoding='utf-8') as f:
            lines = f.readlines()
            current['line_end'] = len(lines)

    return {'segments': segments, 'source_file': os.path.basename(filepath)}

def sync_to_manifest(segments_data, manifest_path):
    if not os.path.exists(manifest_path):
        print(f"Error: manifest not found: {manifest_path}", file=sys.stderr)
        sys.exit(1)

    with open(manifest_path, encoding='utf-8') as f:
        manifest = json.load(f)

    manifest['segments'] = segments_data['segments']

    with open(manifest_path, 'w', encoding='utf-8') as f:
        json.dump(manifest, f, indent=2, ensure_ascii=False)
        f.write('\n')

    print(f"Synced {len(segments_data['segments'])} segments to {manifest_path}")

if __name__ == '__main__':
    parser = argparse.ArgumentParser(
        description='Extract @segment annotations from scene source into JSON.',
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument('scene_file', help='Path to scene source file (.py, .ts, .tsx, .js)')
    parser.add_argument('--sync', action='store_true',
                        help='Sync extracted segments to manifest.json in the same directory')
    args = parser.parse_args()

    filepath = args.scene_file
    result = extract(filepath)

    if args.sync:
        scene_dir = os.path.dirname(os.path.abspath(filepath))
        manifest_path = os.path.join(scene_dir, 'manifest.json')
        sync_to_manifest(result, manifest_path)
    else:
        print(json.dumps(result, indent=2, ensure_ascii=False))
