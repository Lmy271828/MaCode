#!/usr/bin/env bash
set -euo pipefail

# pipeline/concat.sh
# 帧序列 → MP4 编码 / 多 MP4 拼接

if [[ "${1:-}" == "--help" || "${1:-}" == "-h" ]]; then
    SCRIPT_NAME=$(basename "$0")
    cat <<EOF
Usage: $SCRIPT_NAME <frames_dir> <output_mp4> [fps=30]
       $SCRIPT_NAME <output_mp4> <video1> <video2> ...

Encode frame sequence to MP4 or concatenate multiple videos.

Arguments (frames mode):
  <frames_dir>  Directory containing frame_%04d.png sequence
  <output_mp4>  Output MP4 file path
  [fps]         Frame rate (default: 30)

Arguments (videos mode):
  <output_mp4>  Output MP4 file path
  <videoN>      One or more input video files to concatenate

Examples:
  $SCRIPT_NAME frames/ output.mp4 30
  $SCRIPT_NAME output.mp4 part1.mp4 part2.mp4 part3.mp4
EOF
    exit 0
fi

MODE=""

# 判断模式：如果第 1 个参数是目录 → 模式 1；否则 → 模式 2
if [[ $# -ge 1 && -d "${1:-}" ]]; then
    MODE="frames"
else
    MODE="videos"
fi

if [[ "$MODE" == "frames" ]]; then
    FRAMES_DIR="${1:-}"
    OUTPUT_MP4="${2:-}"
    FPS="${3:-30}"

    if [[ -z "$FRAMES_DIR" || -z "$OUTPUT_MP4" ]]; then
        echo "Usage (frames): $0 <frames_dir> <output_mp4> [fps=30]" >&2
        exit 1
    fi

    if [[ ! -d "$FRAMES_DIR" ]]; then
        echo "Error: frames directory not found: $FRAMES_DIR" >&2
        exit 1
    fi

    echo "[concat] Encoding frames @ ${FPS}fps → $OUTPUT_MP4"
    ffmpeg -y \
        -f image2 \
        -framerate "$FPS" \
        -i "$FRAMES_DIR/frame_%04d.png" \
        -c:v libx264 \
        -pix_fmt yuv420p \
        -movflags +faststart \
        "$OUTPUT_MP4"

elif [[ "$MODE" == "videos" ]]; then
    OUTPUT_MP4="${1:-}"
    shift
    VIDEOS=("$@")

    if [[ -z "$OUTPUT_MP4" || ${#VIDEOS[@]} -eq 0 ]]; then
        echo "Usage (videos): $0 <output_mp4> <video1> <video2> ..." >&2
        exit 1
    fi

    # 生成 concat list 文件
    CONCAT_LIST=$(mktemp)
    trap 'rm -f "$CONCAT_LIST"' EXIT

    for v in "${VIDEOS[@]}"; do
        if [[ ! -f "$v" ]]; then
            echo "Error: video not found: $v" >&2
            exit 1
        fi
        echo "file '$(realpath "$v")'" >> "$CONCAT_LIST"
    done

    echo "[concat] Concatenating ${#VIDEOS[@]} videos → $OUTPUT_MP4"
    ffmpeg -y -f concat -safe 0 -i "$CONCAT_LIST" -c copy "$OUTPUT_MP4"
fi
