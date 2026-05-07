#!/usr/bin/env bash
set -euo pipefail

# engines/manimgl/scripts/render.sh
# 接收 scene.py 路径和输出目录，启动 ManimGL 实时预览。
#
# 用法: render.sh <scene.py> <output_dir> [fps] [duration] [width] [height]
#   scene.py    - 场景源码路径
#   output_dir  - 帧序列输出目录（如 .agent/tmp/01_test/frames/）
#   fps         - 帧率（默认 30）
#   duration    - 时长（秒，默认 3）
#   width       - 宽度（默认 1920）
#   height      - 高度（默认 1080）

SCENE_PY="${1:-}"
OUTPUT_DIR="${2:-}"
FPS="${3:-30}"
DURATION="${4:-3}"
WIDTH="${5:-1920}"
HEIGHT="${6:-1080}"

if [[ -z "$SCENE_PY" || -z "$OUTPUT_DIR" ]]; then
    echo "Usage: $0 <scene.py> <output_dir> [fps] [duration] [width] [height]" >&2
    exit 1
fi

if [[ ! -f "$SCENE_PY" ]]; then
    echo "Error: scene file not found: $SCENE_PY" >&2
    exit 1
fi

mkdir -p "$OUTPUT_DIR"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../../.." && pwd)"
VENV_PYTHON="$PROJECT_ROOT/.venv-manimgl/bin/python"

# 将引擎适配层加入 Python 路径，使场景可 import templates/utils
ENGINE_SRC="$(cd "$SCRIPT_DIR/../src" && pwd)"
export PYTHONPATH="${ENGINE_SRC}${PYTHONPATH:+:$PYTHONPATH}"

echo "[manimgl] Preparing $SCENE_PY"

# 检查 ManimGL 是否安装
FALLBACK=0
if [[ ! -x "$VENV_PYTHON" ]]; then
    echo "[manimgl] ERROR: ManimGL not installed. Run: bash bin/setup.sh" >&2
    echo "[manimgl] ManimGL requires a dedicated virtual environment (.venv-manimgl)." >&2
    FALLBACK=1
else
    if ! "$VENV_PYTHON" -c "import manimlib" >/dev/null 2>&1; then
        echo "[manimgl] ERROR: manimlib not found in .venv-manimgl. Run: bash bin/setup.sh" >&2
        FALLBACK=1
    fi
fi

# ── Backend selection ──
BACKEND="gpu"
if [[ -f "$PROJECT_ROOT/.agent/hardware_profile.json" ]]; then
    BACKEND=$(bash "$PROJECT_ROOT/bin/select-backend.sh" 2>/dev/null || echo "gpu")
fi
echo "[manimgl] Render backend: $BACKEND"

if [[ "$BACKEND" == "headless" ]]; then
    echo "[manimgl] HEADLESS mode. ManimGL requires an OpenGL display."
    FALLBACK=1
elif [[ "$BACKEND" == "d3d12" ]]; then
    export GALLIUM_DRIVER=d3d12
    export LIBGL_ALWAYS_SOFTWARE=0
    export MESA_D3D12_DEFAULT_ADAPTER_NAME=NVIDIA
    echo "[manimgl] D3D12 GPU acceleration (WSL2 DX12 passthrough)"
elif [[ "$BACKEND" == "cpu" ]]; then
    export LIBGL_ALWAYS_SOFTWARE=1
    echo "[manimgl] Software OpenGL (Mesa llvmpipe). Interactive preview will be slow."
    # Continue to normal manimlib launch
fi

# Remove old MACODE_HEADLESS check (or keep as override)
if [[ "${MACODE_HEADLESS:-0}" == "1" ]]; then
    echo "[manimgl] MACODE_HEADLESS override active."
    FALLBACK=1
fi

# 降级：生成占位帧
if [[ "$FALLBACK" == "1" ]]; then
    echo "[manimgl] Generating placeholder frames (interactive preview unavailable)." >&2

    SCENE_NAME=$(basename "$SCENE_PY" .py)
    TOTAL_FRAMES=$(awk "BEGIN {print int($FPS * $DURATION)}")

    for ((i=1; i<=TOTAL_FRAMES; i++)); do
        printf -v FRAME_FILE "$OUTPUT_DIR/frame_%04d.png" "$i"
        ffmpeg -y -f lavfi -i "color=c=darkblue:s=${WIDTH}x${HEIGHT}:d=1" \
            -vf "drawtext=text='ManimGL Placeholder\\n${SCENE_NAME}':fontsize=48:fontcolor=white:x=(w-text_w)/2:y=(h-text_h)/2" \
            -frames:v 1 "$FRAME_FILE" >/dev/null 2>&1
    done

    echo "[manimgl] Placeholder done: $TOTAL_FRAMES frames in $OUTPUT_DIR"
    exit 0
fi

# 启动 ManimGL 实时预览
echo "[manimgl] Launching interactive preview: $SCENE_PY"
echo "[manimgl] Close the window to finish. Any cached frames will be preserved."

cd "$PROJECT_ROOT"

# ManimGL 是交互式引擎，此脚本阻塞直到窗口关闭
"$VENV_PYTHON" -m manimlib "$SCENE_PY" 2>&1 | tee "$OUTPUT_DIR/render.log" || true

# 检查是否有帧缓存
if ls "$OUTPUT_DIR"/frame_*.png >/dev/null 2>&1; then
    echo "[manimgl] Found existing frames in $OUTPUT_DIR"
else
    echo "[manimgl] No frames captured. Interactive preview completed."
fi

echo "[manimgl] Done."
