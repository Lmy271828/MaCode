#!/usr/bin/env bash
set -euo pipefail

# pipeline/smart-cut.sh
# 基于 ffprobe silencedetect 自动剪辑视频中的静默/停顿段。
# 无音频的视频直接 passthrough（不作剪辑）。
#
# 用法:
#   pipeline/smart-cut.sh <input.mp4> [output.mp4] [noise_level] [min_duration]
#     input.mp4      - 输入视频
#     output.mp4     - 输出视频（默认：同目录 smartcut_<input>.mp4）
#     noise_level    - 静默阈值 dB（默认: -30dB，越小越敏感）
#     min_duration   - 最短静默时长 秒（默认: 0.5）

INPUT="${1:-}"
OUTPUT="${2:-}"
NOISE_LEVEL="${3:--30dB}"
MIN_DURATION="${4:-0.5}"

if [[ -z "$INPUT" || ! -f "$INPUT" ]]; then
    echo "Usage: $0 <input.mp4> [output.mp4] [noise_level] [min_duration]" >&2
    exit 1
fi

# 默认输出路径
if [[ -z "$OUTPUT" ]]; then
    INPUT_DIR=$(dirname "$INPUT")
    INPUT_NAME=$(basename "$INPUT" .mp4)
    OUTPUT="${INPUT_DIR}/smartcut_${INPUT_NAME}.mp4"
fi

# ── 检查是否有音频流 ──────────────────────────────────
HAS_AUDIO=false
if command -v ffprobe >/dev/null 2>&1; then
    AUDIO_STREAMS=$(ffprobe -v error -select_streams a -show_entries stream=codec_type -of csv=p=0 "$INPUT" 2>/dev/null | wc -l)
    if [[ "$AUDIO_STREAMS" -gt 0 ]]; then
        HAS_AUDIO=true
    fi
fi

if [[ "$HAS_AUDIO" == false ]]; then
    echo "[smart-cut] No audio track detected, copying input as-is"
    cp "$INPUT" "$OUTPUT"
    echo "Done: $OUTPUT (passthrough, no audio)"
    exit 0
fi

# ── 检测静默段 ────────────────────────────────────────
echo "[smart-cut] Analyzing silence (threshold=$NOISE_LEVEL, min_dur=${MIN_DURATION}s)..."

SILENCE_LOG=$(ffmpeg -i "$INPUT" \
    -af "silencedetect=n=${NOISE_LEVEL}:d=${MIN_DURATION}" \
    -f null - 2>&1 | grep -E "silence_(start|end):")

if [[ -z "$SILENCE_LOG" ]]; then
    echo "[smart-cut] No silence detected, copying input as-is"
    cp "$INPUT" "$OUTPUT"
    echo "Done: $OUTPUT (no silence found)"
    exit 0
fi

# ── 解析静默段，计算保留段 ────────────────────────────
# 策略：检测到的静默段 → 保留它们之间的非静默段
# ffprobe silencedetect 输出格式:
#   [silencedetect ...] silence_start: 2.5
#   [silencedetect ...] silence_end: 3.8 | silence_duration: 1.3

# 获取视频总时长
DURATION=$(ffprobe -v error -show_entries format=duration -of csv=p=0 "$INPUT" 2>/dev/null | cut -d. -f1)
DURATION=${DURATION:-0}

# 收集静默段
SILENCE_STARTS=()
SILENCE_ENDS=()

while IFS= read -r line; do
    if [[ "$line" =~ silence_start:\ ([0-9.]+) ]]; then
        SILENCE_STARTS+=("${BASH_REMATCH[1]}")
    elif [[ "$line" =~ silence_end:\ ([0-9.]+) ]]; then
        SILENCE_ENDS+=("${BASH_REMATCH[1]}")
    fi
done <<< "$SILENCE_LOG"

if [[ ${#SILENCE_STARTS[@]} -eq 0 ]]; then
    echo "[smart-cut] No silence to cut, copying input as-is"
    cp "$INPUT" "$OUTPUT"
    echo "Done: $OUTPUT"
    exit 0
fi

# 计算保留段 (keep segments: regions between silences)
KEEP_SEGMENTS=()

# 第一个非静默段: 0 → 第一个 silence_start
if [[ "${SILENCE_STARTS[0]}" != "0" ]]; then
    KEEP_SEGMENTS+=("0:${SILENCE_STARTS[0]}")
fi

# 中间的非静默段: silence_end[i] → silence_start[i+1]
for ((i=0; i<${#SILENCE_ENDS[@]}; i++)); do
    end_i="${SILENCE_ENDS[$i]}"
    next_start="${SILENCE_STARTS[$((i+1))]:-$DURATION}"

    # 跳过极短的段 (< 0.1s 可能是噪音)
    if command -v python3 >/dev/null 2>&1; then
        gap=$(python3 -c "print(float('$next_start') - float('$end_i'))")
    else
        gap=$(awk "BEGIN {print $next_start - $end_i}")
    fi

    if [[ "${gap%.*}" -gt 0 ]]; then
        KEEP_SEGMENTS+=("${end_i}:${next_start}")
    fi
done

# 最后一个非静默段: 最后一个 silence_end → DURATION
last_end="${SILENCE_ENDS[-1]}"
if [[ -n "$DURATION" ]] && [[ "${last_end%.*}" -lt "${DURATION%.*}" ]]; then
    KEEP_SEGMENTS+=("${last_end}:${DURATION}")
fi

SEG_COUNT=${#KEEP_SEGMENTS[@]}
echo "[smart-cut] Found $SEG_COUNT non-silent segment(s) to keep"

if [[ "$SEG_COUNT" -eq 0 ]]; then
    echo "[smart-cut] WARN: entire video is silent, copying as-is" >&2
    cp "$INPUT" "$OUTPUT"
    exit 0
fi

# ── 构建 ffmpeg filtergraph ───────────────────────────
# 使用 trim + concat 滤镜精确切割
FILTER_PARTS=()
CONCAT_INPUTS=""

for idx in $(seq 0 $((SEG_COUNT - 1))); do
    seg="${KEEP_SEGMENTS[$idx]}"
    seg_start="${seg%%:*}"
    seg_end="${seg##*:}"

    # 视频 trim + 音频 atrim，保持同步
    FILTER_PARTS+=("[0:v]trim=start=${seg_start}:end=${seg_end},setpts=PTS-STARTPTS[v${idx}];")
    FILTER_PARTS+=("[0:a]atrim=start=${seg_start}:end=${seg_end},asetpts=PTS-STARTPTS[a${idx}];")
    CONCAT_INPUTS+="[v${idx}][a${idx}]"
done

# concat 所有保留段
FILTER="${FILTER_PARTS[*]}${CONCAT_INPUTS}concat=n=${SEG_COUNT}:v=1:a=1[vout][aout]"

echo "[smart-cut] Encoding trimmed video..."

ffmpeg -i "$INPUT" \
    -filter_complex "$FILTER" \
    -map "[vout]" -map "[aout]" \
    -c:v libx264 -preset fast -crf 23 \
    -c:a aac -b:a 128k \
    -y "$OUTPUT" 2>&1 | tail -3

echo "Done: $OUTPUT"
echo "  Segments kept: $SEG_COUNT"
