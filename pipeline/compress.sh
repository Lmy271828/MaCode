#!/usr/bin/env bash
set -euo pipefail

# pipeline/compress.sh
# CRF 28 快速压缩，用于生成社交媒体版本。

if [[ "${1:-}" == "--help" || "${1:-}" == "-h" ]]; then
    SCRIPT_NAME=$(basename "$0")
    cat <<EOF
Usage: $SCRIPT_NAME <input> <output> [crf]

Fast compress video with CRF for social media sharing.

Arguments:
  <input>   Input video file path
  <output>  Output video file path
  [crf]     CRF value 0-51, larger = smaller file (default: 28)

Examples:
  $SCRIPT_NAME input.mp4 output.mp4
  $SCRIPT_NAME input.mp4 output.mp4 23
EOF
    exit 0
fi

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
