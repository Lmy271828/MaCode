#!/usr/bin/env python3
"""bin/composite-audio.py
Composite 场景音频轨道合成工具。

用法:
    composite-audio.py <video_path> <manifest.json> <output_path>

功能:
    1. 读取 composite manifest 的 `audio` 字段
    2. 支持多音轨混合（背景音乐、旁白等）
    3. 支持 loop、volume、fade_in、fade_out
    4. 音频总时长自动对齐到视频时长

manifest audio 格式:
    {
      "audio": {
        "tracks": [
          {
            "file": "assets/bg_music.mp3",
            "loop": true,
            "volume": 0.3,
            "fade_in": 1.0,
            "fade_out": 2.0
          }
        ]
      }
    }
"""

import argparse
import json
import os
import subprocess
import sys


def get_video_duration(video_path: str) -> float:
    """使用 ffprobe 获取视频时长。"""
    result = subprocess.run(
        ['ffprobe', '-v', 'error', '-show_entries', 'format=duration',
         '-of', 'default=noprint_wrappers=1:nokey=1', video_path],
        capture_output=True, text=True
    )
    if result.returncode != 0:
        raise RuntimeError(f"ffprobe failed: {result.stderr}")
    return float(result.stdout.strip())


def build_audio_filter(tracks: list, total_duration: float) -> tuple:
    """构建 ffmpeg filter_complex 音频滤镜链。

    Returns:
        (filter_string, input_args)  ——  input_args 是额外的 -i 参数列表
    """
    inputs = []
    filters = []
    mix_inputs = []

    for i, track in enumerate(tracks):
        audio_file = track['file']
        loop = track.get('loop', False)
        volume = track.get('volume', 1.0)
        fade_in = track.get('fade_in', 0.0)
        fade_out = track.get('fade_out', 0.0)

        # 输入索引：video=0, 音频从 1 开始
        a_idx = i + 1
        inputs.extend(['-i', audio_file])

        # loop 处理：如果需要循环，先裁剪到总时长
        if loop:
            # 使用 atrim + asetpts 循环裁剪
            filters.append(
                f'[{a_idx}:a]aloop=loop=-1:size=2e+09,'
                f'atrim=0:{total_duration},'
                f'asetpts=PTS-STARTPTS[a{i}]'
            )
        else:
            # 不循环，直接裁剪或填充静音到总时长
            filters.append(
                f'[{a_idx}:a]apad=whole_dur={total_duration},'
                f'atrim=0:{total_duration},'
                f'asetpts=PTS-STARTPTS[a{i}]'
            )

        # volume + fade
        vol_filter = f'[a{i}]volume={volume}'
        if fade_in > 0:
            vol_filter += f',afade=t=in:ss=0:d={fade_in}'
        if fade_out > 0:
            fade_start = max(0.0, total_duration - fade_out)
            vol_filter += f',afade=t=out:st={fade_start}:d={fade_out}'
        vol_filter += f'[a{i}_mixed]'
        filters.append(vol_filter)

        mix_inputs.append(f'[a{i}_mixed]')

    if len(mix_inputs) == 1:
        # 单音轨，直接映射
        filters.append(f'{mix_inputs[0]}amix=inputs=1[aout]')
    else:
        # 多音轨混合
        mix_str = ''.join(mix_inputs)
        filters.append(f'{mix_str}amix=inputs={len(mix_inputs)}:duration=first[aout]')

    filter_complex = ';'.join(filters)
    return filter_complex, inputs


def main():
    parser = argparse.ArgumentParser(
        description='Composite scene audio track mixer. '
                    'Supports multi-track mixing, looping, volume and fade.',
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument('video_path', help='Input video file path')
    parser.add_argument('manifest', help='Path to composite manifest.json')
    parser.add_argument('output_path', help='Output video file path')
    args = parser.parse_args()

    video_path = args.video_path
    manifest_path = args.manifest
    output_path = args.output_path

    if not os.path.isfile(video_path):
        print(f"Error: video not found: {video_path}", file=sys.stderr)
        sys.exit(1)

    with open(manifest_path, encoding='utf-8') as f:
        manifest = json.load(f)

    audio_config = manifest.get('audio')
    if not audio_config:
        print("[audio] No audio config in manifest, copying video as-is")
        subprocess.run(['cp', video_path, output_path], check=True)
        return

    tracks = audio_config.get('tracks', [])
    if not tracks:
        print("[audio] No audio tracks, copying video as-is")
        subprocess.run(['cp', video_path, output_path], check=True)
        return

    # 解析音频文件路径（支持相对 scene_dir 或 project root）
    manifest_dir = os.path.dirname(os.path.abspath(manifest_path))
    for track in tracks:
        audio_file = track['file']
        if not os.path.isabs(audio_file):
            # 先尝试相对于 manifest 目录
            candidate = os.path.join(manifest_dir, audio_file)
            if os.path.isfile(candidate):
                track['file'] = candidate
            else:
                # 再尝试相对于项目根目录
                candidate2 = os.path.join(manifest_dir, '..', '..', audio_file)
                if os.path.isfile(candidate2):
                    track['file'] = os.path.normpath(candidate2)

        if not os.path.isfile(track['file']):
            print(f"[audio] WARNING: audio file not found: {track['file']}", file=sys.stderr)

    total_duration = get_video_duration(video_path)
    print(f"[audio] Video duration: {total_duration:.3f}s")
    print(f"[audio] Mixing {len(tracks)} track(s)...")

    filter_complex, extra_inputs = build_audio_filter(tracks, total_duration)

    cmd = [
        'ffmpeg', '-y',
        '-i', video_path,
        *extra_inputs,
        '-filter_complex', filter_complex,
        '-map', '0:v',
        '-map', '[aout]',
        '-c:v', 'copy',
        '-c:a', 'aac',
        '-b:a', '192k',
        '-shortest',
        output_path
    ]

    print(f"[audio] ffmpeg command: {' '.join(cmd)}")
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"[audio] ffmpeg failed:\n{result.stderr}", file=sys.stderr)
        sys.exit(1)

    print(f"[audio] Done: {output_path}")


if __name__ == '__main__':
    main()
