#!/usr/bin/env bash
set -euo pipefail

# pipeline/preview.sh
# 降分辨率 / 抽帧快速预览，用于 Agent 迭代调试。

if [[ "${1:-}" == "--help" || "${1:-}" == "-h" ]]; then
    SCRIPT_NAME=$(basename "$0")
    cat <<EOF
Usage: $SCRIPT_NAME <input> <output> [scale] [fps]

Generate a low-resolution / low-fps preview video for quick debugging.

Arguments:
  <input>   Input video file path
  <output>  Output preview video file path
  [scale]   Target width in pixels (default: 640)
  [fps]     Target frame rate (default: 10)

Examples:
  $SCRIPT_NAME input.mp4 preview.mp4
  $SCRIPT_NAME input.mp4 preview.mp4 320 5
EOF
    exit 0
fi

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
