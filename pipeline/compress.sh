#!/usr/bin/env bash
set -euo pipefail

# pipeline/compress.sh
# CRF 28 快速压缩，用于生成社交媒体版本。
#
# 用法: compress.sh <input> <output> [crf]
#   input  - 输入视频文件
#   output - 输出视频文件
#   crf    - CRF 值（默认 28，范围 0-51，越大文件越小）

INPUT="${1:-}"
OUTPUT="${2:-}"
CRF="${3:-28}"

if [[ -z "$INPUT" || -z "$OUTPUT" ]]; then
    echo "Usage: $0 <input> <output> [crf]" >&2
    exit 1
fi

if [[ ! -f "$INPUT" ]]; then
    echo "Error: input not found: $INPUT" >&2
    exit 1
fi

mkdir -p "$(dirname "$OUTPUT")"

echo "[ffmpeg] Compressing with CRF=${CRF}..."

ffmpeg -y \
    -i "$INPUT" \
    -c:v libx264 -crf "$CRF" -preset fast -pix_fmt yuv420p \
    -c:a aac -b:a 128k \
    -movflags +faststart \
    "$OUTPUT" >&2

echo "[ffmpeg] Done: $OUTPUT"
