#!/usr/bin/env bash
set -euo pipefail

# engines/motion_canvas/scripts/render.sh
# 接收 scene.tsx 路径和输出目录，尝试调用 Motion Canvas 渲染。
#
# 用法: render.sh <scene.tsx> <output_dir> [fps] [duration] [width] [height]
#   scene.tsx   - 场景源码路径
#   output_dir  - 帧序列输出目录
#   fps         - 帧率（默认 30）
#   duration    - 时长秒数（默认 3）
#   width       - 宽度（默认 1920）
#   height      - 高度（默认 1080）

SCENE_TSX="${1:-}"
OUTPUT_DIR="${2:-}"
FPS="${3:-30}"
DURATION="${4:-3}"
WIDTH="${5:-1920}"
HEIGHT="${6:-1080}"

if [[ -z "$SCENE_TSX" || -z "$OUTPUT_DIR" ]]; then
    echo "Usage: $0 <scene.tsx> <output_dir> [fps] [duration] [width] [height]" >&2
    exit 1
fi

if [[ ! -f "$SCENE_TSX" ]]; then
    echo "Error: scene file not found: $SCENE_TSX" >&2
    exit 1
fi

mkdir -p "$OUTPUT_DIR"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../../.." && pwd)"

echo "[motion_canvas] Rendering $SCENE_TSX -> $OUTPUT_DIR"
echo "[motion_canvas] Settings: ${WIDTH}x${HEIGHT} @ ${FPS}fps for ${DURATION}s"

# 尝试使用 Node.js 渲染脚本
cd "$PROJECT_ROOT"

if command -v npx >/dev/null 2>&1; then
    if npx tsx "$SCRIPT_DIR/render.mjs" "$SCENE_TSX" "$OUTPUT_DIR" "$FPS" "$DURATION" "$WIDTH" "$HEIGHT" 2>&1 | tee "$OUTPUT_DIR/render.log"; then
        echo "[motion_canvas] Done. Frames in $OUTPUT_DIR"
        exit 0
    fi
fi

# 如果 Node.js 渲染失败，生成占位帧序列（确保 pipeline 不中断）
echo "[motion_canvas] WARNING: Headless rendering failed. Generating placeholder frames." >&2
echo "[motion_canvas] Motion Canvas requires a browser environment for full rendering." >&2
echo "[motion_canvas] Install dependencies: npm install canvas jsdom tsx" >&2

SCENE_NAME=$(basename "$SCENE_TSX" .tsx)
TOTAL_FRAMES=$(awk "BEGIN {print int($FPS * $DURATION)}")

for ((i=1; i<=TOTAL_FRAMES; i++)); do
    printf -v FRAME_FILE "$OUTPUT_DIR/frame_%04d.png" "$i"
    # 使用 ffmpeg 生成纯色帧 + 文字
    ffmpeg -y -f lavfi -i "color=c=gray:s=${WIDTH}x${HEIGHT}:d=1" \
        -vf "drawtext=text='Motion Canvas Placeholder\\n${SCENE_NAME}':fontsize=48:fontcolor=white:x=(w-text_w)/2:y=(h-text_h)/2" \
        -frames:v 1 "$FRAME_FILE" >/dev/null 2>&1
done

echo "[motion_canvas] Placeholder done: $TOTAL_FRAMES frames in $OUTPUT_DIR"
