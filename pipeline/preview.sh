#!/usr/bin/env bash
set -euo pipefail

# pipeline/preview.sh
# 降分辨率 / 抽帧快速预览，用于 Agent 迭代调试。
#
# 用法: preview.sh <input> <output> [scale] [fps]
#   input  - 输入视频文件
#   output - 输出视频文件
#   scale  - 目标宽度（像素），默认 640
#   fps    - 目标帧率，默认 10

INPUT="${1:-}"
OUTPUT="${2:-}"
SCALE="${3:-640}"
FPS="${4:-10}"

if [[ -z "$INPUT" || -z "$OUTPUT" ]]; then
    echo "Usage: $0 <input> <output> [scale_width] [fps]" >&2
    exit 1
fi

if [[ ! -f "$INPUT" ]]; then
    echo "Error: input not found: $INPUT" >&2
    exit 1
fi

mkdir -p "$(dirname "$OUTPUT")"

echo "[ffmpeg] Generating preview: scale=${SCALE}, fps=${FPS}"

ffmpeg -y \
    -i "$INPUT" \
    -vf "fps=${FPS},scale=${SCALE}:-2:flags=lanczos" \
    -c:v libx264 -crf 32 -preset fast -pix_fmt yuv420p \
    -an \
    "$OUTPUT" >&2

echo "[ffmpeg] Done: $OUTPUT"
