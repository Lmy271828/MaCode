#!/usr/bin/env bash
set -euo pipefail

# pipeline/audio-analyze.sh
# 分析音频文件，生成节拍/能量时间轴 CSV，供场景代码驱动动画。

if [[ "${1:-}" == "--help" || "${1:-}" == "-h" ]]; then
    SCRIPT_NAME=$(basename "$0")
    cat <<EOF
Usage: $SCRIPT_NAME <audio_file> <output_csv> [fps]

Analyze audio and generate a beat/energy timeline CSV for animation driving.

Arguments:
  <audio_file>  Input audio file to analyze
  <output_csv>  Output CSV path (default: timeline.csv)
  [fps]         Frames per second for alignment (default: 30)

Examples:
  $SCRIPT_NAME song.mp3 beats.csv
  $SCRIPT_NAME song.mp3 beats.csv 60
EOF
    exit 0
fi

AUDIO="${1:-}"
OUTPUT="${2:-timeline.csv}"
FPS="${3:-30}"

if [[ -z "$AUDIO" ]]; then
    echo "Usage: $0 <audio_file> <output_csv> [fps=30]" >&2
    exit 1
fi

if [[ ! -f "$AUDIO" ]]; then
    echo "Error: audio file not found: $AUDIO" >&2
    exit 1
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

# 优先使用项目 .venv 的 Python
VENV_PYTHON="$PROJECT_ROOT/.venv/bin/python"
if [[ -x "$VENV_PYTHON" ]]; then
    PYTHON="$VENV_PYTHON"
else
    PYTHON="python3"
fi

TMPDIR=$(mktemp -d)
trap 'rm -rf "$TMPDIR"' EXIT

echo "[audio-analyze] Analyzing $AUDIO → $OUTPUT @ ${FPS}fps"

# ── 1. ffmpeg 提取各频带 PCM（100Hz 采样率，单声道，16bit） ──
# 100Hz 采样率意味着每 10ms 一个样本，30fps 视频每帧约 3.33 个样本

ffmpeg -y -hide_banner -loglevel error \
    -i "$AUDIO" \
    -ar 100 -ac 1 -f s16le "$TMPDIR/pcm_all.raw"

ffmpeg -y -hide_banner -loglevel error \
    -i "$AUDIO" \
    -af "lowpass=f=100" \
    -ar 100 -ac 1 -f s16le "$TMPDIR/pcm_low.raw"

ffmpeg -y -hide_banner -loglevel error \
    -i "$AUDIO" \
    -af "bandpass=f=1000:w=1900" \
    -ar 100 -ac 1 -f s16le "$TMPDIR/pcm_mid.raw"

ffmpeg -y -hide_banner -loglevel error \
    -i "$AUDIO" \
    -af "highpass=f=2000" \
    -ar 100 -ac 1 -f s16le "$TMPDIR/pcm_high.raw"

# ── 2. Python 分析：分帧能量 + 节拍检测 ──
"$PYTHON" << PYEOF
import struct
import numpy as np
import csv
from pathlib import Path

def read_pcm(path):
    """读取 16bit 有符号整数 PCM 为 numpy float32 数组（归一化到 -1~1）"""
    data = Path(path).read_bytes()
    samples = struct.unpack(f"<{len(data)//2}h", data)
    return np.array(samples, dtype=np.float32) / 32768.0

fps = $FPS
samples_per_frame = 100.0 / fps  # 100Hz 采样率下每帧的样本数

all_pcm = read_pcm("$TMPDIR/pcm_all.raw")
low_pcm = read_pcm("$TMPDIR/pcm_low.raw")
mid_pcm = read_pcm("$TMPDIR/pcm_mid.raw")
high_pcm = read_pcm("$TMPDIR/pcm_high.raw")

# 统一长度
min_len = min(len(all_pcm), len(low_pcm), len(mid_pcm), len(high_pcm))
all_pcm = all_pcm[:min_len]
low_pcm = low_pcm[:min_len]
mid_pcm = mid_pcm[:min_len]
high_pcm = high_pcm[:min_len]

# 分帧计算 RMS 能量
num_frames = int(np.floor(min_len / samples_per_frame))
frame_times = np.arange(num_frames) / fps

def frame_rms(pcm, spf):
    frames = []
    for i in range(num_frames):
        start = int(i * spf)
        end = int((i + 1) * spf)
        chunk = pcm[start:end]
        rms = np.sqrt(np.mean(chunk ** 2)) if len(chunk) > 0 else 0.0
        frames.append(rms)
    return np.array(frames)

loudness = frame_rms(all_pcm, samples_per_frame)
low_energy = frame_rms(low_pcm, samples_per_frame)
mid_energy = frame_rms(mid_pcm, samples_per_frame)
high_energy = frame_rms(high_pcm, samples_per_frame)

# 归一化到 0~1（用 95 分位数避免极端值）
def normalize(arr):
    cap = np.percentile(arr, 95) if np.max(arr) > 0 else 1.0
    cap = max(cap, 1e-6)
    return np.clip(arr / cap, 0.0, 1.0)

loudness = normalize(loudness)
low_energy = normalize(low_energy)
mid_energy = normalize(mid_energy)
high_energy = normalize(high_energy)

# ── 节拍检测：在低频能量上找局部峰值 ──
# 条件：
#   1. 能量 > 0.3（阈值）
#   2. 比前后各 3 帧高
#   3. 距离上一个节拍至少 0.2 秒（约 6 帧@30fps）
beats = np.zeros(num_frames, dtype=int)
min_beat_gap_frames = max(1, int(0.2 * fps))
threshold = 0.3

last_beat = -min_beat_gap_frames
for i in range(3, num_frames - 3):
    if low_energy[i] < threshold:
        continue
    if i - last_beat < min_beat_gap_frames:
        continue
    if low_energy[i] > low_energy[i-1] and low_energy[i] > low_energy[i-2] and low_energy[i] > low_energy[i-3]:
        if low_energy[i] > low_energy[i+1] and low_energy[i] > low_energy[i+2] and low_energy[i] > low_energy[i+3]:
            beats[i] = 1
            last_beat = i

# ── 写入 CSV ──
with open("$OUTPUT", "w", newline="") as f:
    writer = csv.writer(f)
    writer.writerow(["time", "beat", "loudness", "low", "mid", "high"])
    for i in range(num_frames):
        writer.writerow([
            f"{frame_times[i]:.4f}",
            beats[i],
            f"{loudness[i]:.4f}",
            f"{low_energy[i]:.4f}",
            f"{mid_energy[i]:.4f}",
            f"{high_energy[i]:.4f}",
        ])

beat_count = int(np.sum(beats))
print(f"[audio-analyze] Done: {num_frames} frames, {beat_count} beats detected → $OUTPUT")
PYEOF
