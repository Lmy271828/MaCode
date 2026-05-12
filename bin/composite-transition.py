#!/usr/bin/env python3
"""bin/composite-transition.py
生成 ffmpeg xfade filtergraph 并执行 composite 视频拼接（含转场效果）。

用法:
    composite-transition.py output.mp4 --segments '<json_segments>'

JSON segments 示例:
[
  {"video": ".agent/tmp/seg1/final.mp4", "transition": {"type": "fade", "duration": 0.3}},
  {"video": ".agent/tmp/seg2/final.mp4", "transition": {"type": "wipeleft", "duration": 0.5}},
  {"video": ".agent/tmp/seg3/final.mp4"}
]

transition 字段可选。省略时默认无转场（硬切）。
支持的转场类型（ffmpeg xfade）：fade, wipeleft, wiperight, wipeup, wipedown,
slideleft, slideright, slideup, slidedown, distance, smoothleft, smoothright,
circlecrop, rectcrop, fadegrays, radial, fadeblack, fadewhite, pixelize, diagtl,
diagtr, diagbl, diagbr, hlslice, hrslice, vuslice, vdslice, hblur,
"""

import argparse
import json
import os
import subprocess
import sys


def get_video_duration(path: str) -> float:
    """用 ffprobe 获取视频时长（秒）。"""
    cmd = [
        "ffprobe", "-v", "error",
        "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1",
        path,
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"ffprobe failed for {path}: {result.stderr}")
    return float(result.stdout.strip())


def build_xfade_filtergraph(segments: list) -> tuple:
    """
    构建 xfade filtergraph。

    返回: (filter_complex_string, inputs_list)
    """
    n = len(segments)
    if n == 0:
        raise ValueError("No segments provided")
    if n == 1:
        return None, [segments[0]["video"]]

    # 测量所有视频时长
    durations = []
    for seg in segments:
        dur = get_video_duration(seg["video"])
        durations.append(dur)

    # 收集转场参数
    transitions = []
    for i in range(n - 1):
        seg = segments[i]
        trans = seg.get("transition")
        if trans:
            t_type = trans.get("type", "fade")
            t_dur = float(trans.get("duration", 0.5))
        else:
            t_type = "fade"
            t_dur = 0.0  # 零时长转场 = 硬切
        transitions.append((t_type, t_dur))

    # 构建 filtergraph
    # 第 i 个 xfade 的 offset = 前一个输出时长 - transition_duration
    # 前一个输出时长 = durations[0] (i=0) 或 前一个 xfade 的 max(prev, offset+next_dur)
    filters = []
    prev_label = "0:v"
    running_output = durations[0]  # Duration of accumulated output so far

    for i in range(n - 1):
        t_type, t_dur = transitions[i]
        offset = running_output - t_dur
        # 确保 offset 不为负
        if offset < 0:
            offset = 0.0
            t_dur = running_output  # Clamp transition to available duration

        next_input = f"{i + 1}:v"
        out_label = f"f{i}" if i < n - 2 else "fv"

        if t_dur > 0:
            filters.append(
                f"[{prev_label}][{next_input}]"
                f"xfade=transition={t_type}:duration={t_dur:.3f}:offset={offset:.3f}"
                f"[{out_label}]"
            )
        else:
            # 零时长转场：用 concat 代替（避免 xfade duration=0 报错）
            filters.append(
                f"[{prev_label}][{next_input}]"
                f"concat=n=2:v=1:a=0"
                f"[{out_label}]"
            )
        # Update running output for next xfade
        running_output = max(running_output, offset + durations[i + 1])
        prev_label = out_label

    filter_str = ";".join(filters)
    return filter_str, None


def main():
    parser = argparse.ArgumentParser(
        description='Build ffmpeg xfade filtergraph and concat composite videos with transitions.',
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument('output_path', help='Output video file path')
    parser.add_argument('--segments', help='JSON array of segments with optional transition fields')
    parser.add_argument('segments_json', nargs='?', help=argparse.SUPPRESS)
    args = parser.parse_args()

    output_path = args.output_path
    if args.segments:
        segments_json = args.segments
    elif args.segments_json:
        segments_json = args.segments_json
    else:
        parser.error('the following arguments are required: --segments')
    segments = json.loads(segments_json)

    if not segments:
        print("Error: empty segments", file=sys.stderr)
        sys.exit(1)

    n = len(segments)

    # 检查所有视频存在
    for seg in segments:
        v = seg.get("video", "")
        if not os.path.isfile(v):
            print(f"Error: video not found: {v}", file=sys.stderr)
            sys.exit(1)

    if n == 1:
        # 单视频直接复制
        subprocess.run(["cp", segments[0]["video"], output_path], check=True)
        print(f"Single segment copied to {output_path}")
        return

    filter_str, _ = build_xfade_filtergraph(segments)

    # 构建 ffmpeg 命令
    cmd = ["ffmpeg", "-y", "-hide_banner", "-loglevel", "error"]
    for seg in segments:
        cmd.extend(["-i", seg["video"]])
    cmd.extend(["-filter_complex", filter_str, "-map", "[fv]"])
    cmd.extend(["-c:v", "libx264", "-pix_fmt", "yuv420p", "-movflags", "+faststart"])
    cmd.append(output_path)

    print(f"[transition] Building filtergraph with {n} segments...")
    print(f"[transition] Filter: {filter_str}")

    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"[transition] ffmpeg failed:\n{result.stderr}", file=sys.stderr)
        sys.exit(1)

    print(f"[transition] Done: {output_path}")


if __name__ == "__main__":
    main()
