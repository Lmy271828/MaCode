#!/usr/bin/env python3
"""bin/composite-audio-sync.py
跨 Segment 音频同步工具 —— 基于 BPM 计算节拍对齐的偏移。

用法:
    composite-audio-sync.py <manifest.json> --bpm <bpm> [--snap-transitions]

功能:
    1. 读取 composite manifest
    2. 根据 BPM 计算每拍的时长
    3. 调整 segment 边界，使其对齐到最近的节拍
    4. 输出调整后的 manifest（stdout）

选项:
    --bpm <float>        音乐节拍（beats per minute）
    --snap-transitions   将 transition 时间点对齐到节拍（默认只 snap segment 起始）
    --tolerance <float>  最大调整容差（秒），默认 0.15
"""

import argparse
import json
import os
import sys


def snap_to_beat(time: float, beat_interval: float, tolerance: float) -> tuple:
    """将时间点对齐到最近的节拍。

    Returns:
        (snapped_time, delta)  ——  delta 为调整量（可为负）
    """
    beat = round(time / beat_interval)
    snapped = beat * beat_interval
    delta = snapped - time
    if abs(delta) > tolerance:
        return time, 0.0
    return snapped, delta


def get_duration(seg: dict, manifest_dir: str) -> float:
    """从 segment 或子场景 manifest 读取 duration。"""
    if 'duration' in seg:
        return float(seg['duration'])
    # 尝试从子场景 manifest 读取
    seg_path = seg.get('scene_dir') or seg.get('shot', '')
    seg_manifest = os.path.join(manifest_dir, seg_path, 'manifest.json')
    if os.path.isfile(seg_manifest):
        with open(seg_manifest, encoding='utf-8') as f:
            data = json.load(f)
        return float(data.get('duration', 0))
    return 0.0


def calculate_offsets(manifest: dict, manifest_dir: str, bpm: float, snap_transitions: bool, tolerance: float):
    """计算节拍对齐后的 segment 时间偏移。"""
    beat_interval = 60.0 / bpm
    segments = manifest.get('segments', [])

    # 先收集原始时长
    raw_durations = []
    for seg in segments:
        raw_durations.append(get_duration(seg, manifest_dir))

    # 计算原始累积偏移
    raw_offsets = [0.0]
    for dur in raw_durations[:-1]:
        raw_offsets.append(raw_offsets[-1] + dur)

    # 对齐 segment 起始到节拍
    snapped_offsets = []
    total_drift = 0.0
    for offset in raw_offsets:
        snapped, delta = snap_to_beat(offset, beat_interval, tolerance)
        snapped_offsets.append(snapped)
        total_drift += delta

    # 构建结果
    results = []
    for i, seg in enumerate(segments):
        start = snapped_offsets[i]
        end = start + raw_durations[i]
        # 如果 snap_transitions，尝试将 end 也对齐
        if snap_transitions and i < len(segments) - 1:
            snapped_end, delta = snap_to_beat(end, beat_interval, tolerance)
            if delta != 0.0:
                end = snapped_end

        results.append({
            'id': seg['id'],
            'original_start': raw_offsets[i],
            'snapped_start': start,
            'original_end': raw_offsets[i] + raw_durations[i],
            'snapped_end': end,
            'drift': start - raw_offsets[i],
        })

    return results, beat_interval, total_drift


def main():
    parser = argparse.ArgumentParser(
        description='Cross-segment audio sync via BPM.',
        epilog='Reads a composite manifest and outputs adjusted segment offsets aligned to beats.',
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument('manifest', help='Path to composite manifest.json')
    parser.add_argument('--bpm', type=float, required=True, help='Beats per minute')
    parser.add_argument('--snap-transitions', action='store_true',
                        help='Snap transition points to beats (default: only snap segment starts)')
    parser.add_argument('--tolerance', type=float, default=0.15,
                        help='Max adjustment tolerance in seconds (default: 0.15)')
    args = parser.parse_args()

    with open(args.manifest, encoding='utf-8') as f:
        manifest = json.load(f)

    if manifest.get('type') not in ('composite', 'composite-unified'):
        print(f"Error: manifest type must be composite or composite-unified, got {manifest.get('type')}",
              file=sys.stderr)
        sys.exit(1)

    manifest_dir = os.path.dirname(os.path.abspath(args.manifest))
    results, beat_interval, total_drift = calculate_offsets(
        manifest, manifest_dir, args.bpm, args.snap_transitions, args.tolerance
    )

    output = {
        'bpm': args.bpm,
        'beat_interval': beat_interval,
        'total_drift': total_drift,
        'segments': results,
    }

    print(json.dumps(output, indent=2, ensure_ascii=False))


if __name__ == '__main__':
    main()
