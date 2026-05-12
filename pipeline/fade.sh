#!/usr/bin/env bash
set -euo pipefail

# pipeline/fade.sh
# 使用 ffmpeg afade / fade 实现音视频淡入淡出。

if [[ "${1:-}" == "--help" || "${1:-}" == "-h" ]]; then
    SCRIPT_NAME=$(basename "$0")
    cat <<EOF
Usage: $SCRIPT_NAME <input> <output> [fade_in_sec] [fade_out_sec]

Apply audio/video fade-in and fade-out effects using ffmpeg.

Arguments:
  <input>          Input video file path
  <output>         Output video file path
  [fade_in_sec]    Fade-in duration in seconds (default: 0.5)
  [fade_out_sec]   Fade-out duration in seconds (default: 0.5)

Examples:
  $SCRIPT_NAME input.mp4 output.mp4
  $SCRIPT_NAME input.mp4 output.mp4 1.0 2.0
EOF
    exit 0
fi

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
