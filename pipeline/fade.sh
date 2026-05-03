#!/usr/bin/env bash
set -euo pipefail

# pipeline/fade.sh
# 使用 ffmpeg afade / fade 实现音视频淡入淡出。
#
# 用法: fade.sh <input> <output> [fade_in_duration] [fade_out_duration]
#   input            - 输入视频文件
#   output           - 输出视频文件
#   fade_in_duration  - 淡入时长（秒），默认 0.5
#   fade_out_duration - 淡出时长（秒），默认 0.5

INPUT="${1:-}"
OUTPUT="${2:-}"
FADE_IN="${3:-0.5}"
FADE_OUT="${4:-0.5}"

if [[ -z "$INPUT" || -z "$OUTPUT" ]]; then
    echo "Usage: $0 <input> <output> [fade_in_sec] [fade_out_sec]" >&2
    exit 1
fi

if [[ ! -f "$INPUT" ]]; then
    echo "Error: input not found: $INPUT" >&2
    exit 1
fi

mkdir -p "$(dirname "$OUTPUT")"

# 获取视频时长（秒）
DURATION=$(ffprobe -v error -show_entries format=duration -of default=noprint_wrappers=1:nokey=1 "$INPUT")
DURATION=${DURATION%.*}

# 计算淡出开始时间
FADE_OUT_START=$(awk "BEGIN {print $DURATION - $FADE_OUT}")

echo "[ffmpeg] Applying fade: in=${FADE_IN}s, out=${FADE_OUT}s (start=${FADE_OUT_START}s)"

ffmpeg -y \
    -i "$INPUT" \
    -vf "fade=t=in:st=0:d=${FADE_IN},fade=t=out:st=${FADE_OUT_START}:d=${FADE_OUT}" \
    -af "afade=t=in:ss=0:d=${FADE_IN},afade=t=out:st=${FADE_OUT_START}:d=${FADE_OUT}" \
    -c:v libx264 -pix_fmt yuv420p \
    -c:a aac -b:a 192k \
    "$OUTPUT" >&2

echo "[ffmpeg] Done: $OUTPUT"
