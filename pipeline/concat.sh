#!/usr/bin/env bash
set -euo pipefail

# pipeline/concat.sh
# 两种模式：
#   1) 帧序列目录 -> MP4:   concat.sh <frames_dir> <output_mp4>
#   2) 多个 MP4 拼接:       concat.sh <output_mp4> <mp4_1> <mp4_2> ...

# 判断模式：如果第一个参数是目录且存在，则为模式 1；否则为模式 2
FIRST_ARG="${1:-}"

if [[ -z "$FIRST_ARG" ]]; then
    echo "Usage (frames): $0 <frames_dir> <output_mp4>"
    echo "Usage (videos): $0 <output_mp4> <video1> <video2> ..." >&2
    exit 1
fi

# 模式 1: 帧序列 -> MP4
if [[ -d "$FIRST_ARG" ]]; then
    FRAMES_DIR="$FIRST_ARG"
    OUTPUT_MP4="${2:-}"

    if [[ -z "$OUTPUT_MP4" ]]; then
        echo "Usage: $0 <frames_dir> <output_mp4>" >&2
        exit 1
    fi

    FRAME_COUNT=$(find "$FRAMES_DIR" -name "*.png" | wc -l)
    if [[ "$FRAME_COUNT" -eq 0 ]]; then
        echo "Error: no PNG frames found in $FRAMES_DIR" >&2
        exit 1
    fi

    echo "[ffmpeg] Encoding $FRAME_COUNT frames -> $OUTPUT_MP4"

    FPS=30
    ffmpeg -y \
        -f image2 \
        -framerate "$FPS" \
        -i "$FRAMES_DIR/frame_%04d.png" \
        -c:v libx264 \
        -pix_fmt yuv420p \
        -movflags +faststart \
        "$OUTPUT_MP4" >&2

    echo "[ffmpeg] Done: $OUTPUT_MP4"
    exit 0
fi

# 模式 2: 多个 MP4 拼接
OUTPUT_MP4="$FIRST_ARG"
shift

if [[ $# -lt 1 ]]; then
    echo "Usage: $0 <output_mp4> <video1> <video2> ..." >&2
    exit 1
fi

# 验证所有输入文件存在
for f in "$@"; do
    if [[ ! -f "$f" ]]; then
        echo "Error: file not found: $f" >&2
        exit 1
    fi
done

mkdir -p "$(dirname "$OUTPUT_MP4")"

# 创建 concat demuxer 列表文件
CONCAT_LIST=$(mktemp)
trap "rm -f $CONCAT_LIST" EXIT

for f in "$@"; do
    # 需要绝对路径或 safe 0 模式
    abs_path=$(cd "$(dirname "$f")" && pwd)/$(basename "$f")
    echo "file '$abs_path'" >> "$CONCAT_LIST"
done

echo "[ffmpeg] Concatenating $# videos -> $OUTPUT_MP4"

ffmpeg -y -f concat -safe 0 -i "$CONCAT_LIST" -c copy "$OUTPUT_MP4" >&2

echo "[ffmpeg] Done: $OUTPUT_MP4"
