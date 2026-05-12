#!/usr/bin/env bash
set -euo pipefail

# pipeline/thumbnail.sh
# 从视频中提取关键帧/缩略图，使用 ffmpeg 精确 seek。

if [[ "${1:-}" == "--help" || "${1:-}" == "-h" ]]; then
    SCRIPT_NAME=$(basename "$0")
    cat <<EOF
Usage: $SCRIPT_NAME <input.mp4> [output_dir] [mode]

Extract key frames or thumbnails from a video using ffmpeg seek.

Arguments:
  <input.mp4>   Input video file path
  [output_dir]  Directory to save thumbnails (default: same as input)
  [mode]        mid | N | time=MM:SS | interval=N (default: mid)

Examples:
  $SCRIPT_NAME video.mp4
  $SCRIPT_NAME video.mp4 thumbs/ 5
  $SCRIPT_NAME video.mp4 thumbs/ time=01:30
EOF
    exit 0
fi

INPUT="${1:-}"
OUTPUT_DIR="${2:-}"
MODE="${3:-mid}"

if [[ -z "$INPUT" || ! -f "$INPUT" ]]; then
    echo "Usage: $0 <input.mp4> [output_dir] [mode]" >&2
    echo "  mode: mid | N | time=MM:SS | interval=N" >&2
    exit 1
fi

# 默认输出目录
if [[ -z "$OUTPUT_DIR" ]]; then
    OUTPUT_DIR="$(dirname "$INPUT")"
fi
mkdir -p "$OUTPUT_DIR"

INPUT_NAME=$(basename "$INPUT" | sed 's/\.[^.]*$//')

if ! command -v ffprobe >/dev/null 2>&1 || ! command -v ffmpeg >/dev/null 2>&1; then
    echo "Error: ffprobe and ffmpeg are required" >&2
    exit 1
fi

# 获取视频时长
DURATION=$(ffprobe -v error -show_entries format=duration -of csv=p=0 "$INPUT" 2>/dev/null)
if [[ -z "$DURATION" || "$DURATION" == "N/A" ]]; then
    echo "Error: cannot determine video duration" >&2
    exit 1
fi

echo "[thumbnail] Source: $INPUT (${DURATION}s)"

# ── 提取单帧 ──────────────────────────────────────────
extract_frame() {
    local time_sec="$1"
    local label="$2"
    local output="$OUTPUT_DIR/${INPUT_NAME}_thumb_${label}.png"

    ffmpeg -ss "$time_sec" -i "$INPUT" \
        -frames:v 1 -q:v 2 \
        -y "$output" 2>/dev/null

    if [[ -f "$output" ]]; then
        echo "  $output ($(du -h "$output" | cut -f1))"
    else
        echo "  FAILED: $output" >&2
    fi
}

# ── 模式分发 ──────────────────────────────────────────

# mid: 视频正中间
if [[ "$MODE" == "mid" ]]; then
    MIDPOINT=$(awk "BEGIN {print $DURATION / 2}")
    echo "[thumbnail] Mode: mid (t=${MIDPOINT}s)"
    extract_frame "$MIDPOINT" "mid"

# time=MM:SS 或 time=SECONDS
elif [[ "$MODE" =~ ^time=(.+)$ ]]; then
    TIME_SPEC="${BASH_REMATCH[1]}"

    # 尝试解析 MM:SS 格式
    if [[ "$TIME_SPEC" =~ ^([0-9]+):([0-9.]+)$ ]]; then
        MINUTES="${BASH_REMATCH[1]}"
        SECS="${BASH_REMATCH[2]}"
        TIME_SEC=$(awk "BEGIN {print $MINUTES * 60 + $SECS}")
    else
        TIME_SEC="$TIME_SPEC"
    fi

    echo "[thumbnail] Mode: time (t=${TIME_SEC}s)"
    extract_frame "$TIME_SEC" "${TIME_SPEC//:/_}"

# interval=N: 每 N 秒一帧
elif [[ "$MODE" =~ ^interval=([0-9.]+)$ ]]; then
    INTERVAL="${BASH_REMATCH[1]}"
    echo "[thumbnail] Mode: interval (every ${INTERVAL}s)"

    COUNT=0
    CURRENT=0
    while (( $(awk "BEGIN {print ($CURRENT < $DURATION)}") )); do
        extract_frame "$CURRENT" "$(printf '%04d' $COUNT)"
        CURRENT=$(awk "BEGIN {print $CURRENT + $INTERVAL}")
        COUNT=$((COUNT + 1))
    done
    echo "  Total: $COUNT thumbnails"

# 数字 N: 均匀分布 N 帧
elif [[ "$MODE" =~ ^[0-9]+$ ]]; then
    NUM_FRAMES="$MODE"
    echo "[thumbnail] Mode: uniform ($NUM_FRAMES frames)"

    for i in $(seq 0 $((NUM_FRAMES - 1))); do
        # 均匀分布，避免第一帧（通常为黑屏/标题）和最后一帧（通常为结束画面）
        if [[ "$NUM_FRAMES" -eq 1 ]]; then
            POS=$(awk "BEGIN {print $DURATION / 2}")
        else
            OFFSET=$(awk "BEGIN {print $DURATION * 0.05}")  # 5% margin
            POS=$(awk "BEGIN {print $OFFSET + ($DURATION - 2 * $OFFSET) * $i / ($NUM_FRAMES - 1)}")
        fi
        extract_frame "$POS" "$(printf '%02d' $i)"
    done
    echo "  Total: $NUM_FRAMES thumbnails"

else
    echo "Error: unknown mode '$MODE'" >&2
    echo "  Use: mid | N | time=MM:SS | interval=N" >&2
    exit 1
fi

echo "Done: thumbnails in $OUTPUT_DIR/"
