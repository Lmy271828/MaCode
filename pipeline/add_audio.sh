#!/usr/bin/env bash
set -euo pipefail

# pipeline/add_audio.sh
# 接收视频 + 音频文件，使用 ffmpeg 合成输出。

if [[ "${1:-}" == "--help" || "${1:-}" == "-h" ]]; then
    SCRIPT_NAME=$(basename "$0")
    cat <<EOF
Usage: $SCRIPT_NAME <video> <audio> <output>

Mix external audio into a video file using ffmpeg (copy video, AAC audio).

Arguments:
  <video>   Input video file path
  <audio>   Input audio file path
  <output>  Output video file path

Examples:
  $SCRIPT_NAME video.mp4 music.mp4 output.mp4
EOF
    exit 0
fi

VIDEO="${1:-}"
AUDIO="${2:-}"
OUTPUT="${3:-}"

if [[ -z "$VIDEO" || -z "$AUDIO" || -z "$OUTPUT" ]]; then
    echo "Usage: $0 <video> <audio> <output>" >&2
    exit 1
fi

for f in "$VIDEO" "$AUDIO"; do
    if [[ ! -f "$f" ]]; then
        echo "Error: file not found: $f" >&2
        exit 1
    fi
done

mkdir -p "$(dirname "$OUTPUT")"

echo "[ffmpeg] Mixing audio into video..."
echo "[ffmpeg] Video: $VIDEO"
echo "[ffmpeg] Audio: $AUDIO"
echo "[ffmpeg] Output: $OUTPUT"

# 复制视频流，重新编码音频为 AAC
ffmpeg -y \
    -i "$VIDEO" \
    -i "$AUDIO" \
    -c:v copy \
    -c:a aac \
    -b:a 192k \
    -shortest \
    "$OUTPUT" >&2

echo "[ffmpeg] Done: $OUTPUT"
