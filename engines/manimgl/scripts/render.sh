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

if [[ "${1:-}" == "--help" || "${1:-}" == "-h" ]]; then
    cat <<EOF
Usage: $(basename "$0") <scene.py> <output_dir> [fps] [duration] [width] [height]

接收 scene.py 路径和输出目录，启动 ManimGL 实时预览并输出帧序列。

Arguments:
  <scene.py>    场景源码路径
  <output_dir>  帧序列输出目录
  [fps]         帧率 (default: 30)
  [duration]    时长（秒，default: 3）
  [width]       宽度（default: 1920）
  [height]      高度（default: 1080）

Examples:
  $(basename "$0") scenes/01_test/scene.py .agent/tmp/01_test/frames/
EOF
    exit 0
fi

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

SCENE_NAME=$(basename "$SCENE_PY" .py)
STATE_DIR="$PROJECT_ROOT/.agent/tmp/$SCENE_NAME"
mkdir -p "$STATE_DIR"

write_state() {
    local status="$1"
    shift
    "$PROJECT_ROOT/bin/state-write.py" "$STATE_DIR" "$status" --tool "render.sh" "$@" 2>/dev/null || true
}

write_progress() {
    local phase="$1"
    local status="$2"
    local msg="${3:-}"
    "$PROJECT_ROOT/bin/progress-write.py" "$PROJECT_ROOT/.agent/progress/${SCENE_NAME}.jsonl" "$phase" "$status" "$msg" 2>/dev/null || true
}

write_state "running" --task-id "$SCENE_NAME"
write_progress "init" "running" "manimgl prepare"

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

    TOTAL_FRAMES=$(awk "BEGIN {print int($FPS * $DURATION)}")

    for ((i=1; i<=TOTAL_FRAMES; i++)); do
        printf -v FRAME_FILE "$OUTPUT_DIR/frame_%04d.png" "$i"
        ffmpeg -y -f lavfi -i "color=c=darkblue:s=${WIDTH}x${HEIGHT}:d=1" \
            -vf "drawtext=text='ManimGL Placeholder\\n${SCENE_NAME}':fontsize=48:fontcolor=white:x=(w-text_w)/2:y=(h-text_h)/2" \
            -frames:v 1 "$FRAME_FILE" >/dev/null 2>&1
    done

    write_state "completed" 0 --outputs "{\"framesRendered\": $TOTAL_FRAMES, \"outputDir\": \"$OUTPUT_DIR\", \"engine\": \"manimgl\", \"mode\": \"placeholder\"}"
    write_progress "capture" "completed" "placeholder frames generated"
    echo "[manimgl] Placeholder done: $TOTAL_FRAMES frames in $OUTPUT_DIR"
    exit 0
fi

# ── Render mode selection ──
# When OUTPUT_DIR is provided (pipeline / macode render), we write a video
# file instead of opening an interactive preview window.
# The pipeline (render-scene.py) expects raw.mp4 in OUTPUT_DIR for
# interactive-mode engines.
if [[ -n "$OUTPUT_DIR" ]]; then
    RENDER_FLAGS="-w"
    if [[ -n "$WIDTH" && -n "$HEIGHT" ]]; then
        RENDER_FLAGS="$RENDER_FLAGS -r ${WIDTH}x${HEIGHT}"
    fi
    # NOTE: --fps is omitted because manimlib has a type-bug when -w is used
    # The scene's frame rate is controlled by camera.fps in construct().

    # Extract the first Scene subclass name so manimlib doesn't prompt
    SCENE_CLASS=$("$VENV_PYTHON" -c "
import ast, sys
with open('$SCENE_PY') as f:
    tree = ast.parse(f.read())
for node in ast.walk(tree):
    if isinstance(node, ast.ClassDef):
        for base in node.bases:
            name = None
            if isinstance(base, ast.Name):
                name = base.id
            elif isinstance(base, ast.Attribute):
                name = base.attr
            if name and name.endswith('Scene'):
                print(node.name)
                sys.exit(0)
" 2>/dev/null || true)

    # --file_name raw so that pipeline/render-scene.py can find raw.mp4
    RENDER_FLAGS="$RENDER_FLAGS --video_dir \"$OUTPUT_DIR\" --file_name raw -n 0"

    echo "[manimgl] Writing video: $SCENE_PY → $OUTPUT_DIR/raw.mp4"
    write_progress "capture" "running" "video write started"

    cd "$PROJECT_ROOT"
    RENDER_RC=0
    if [[ -n "$SCENE_CLASS" ]]; then
        eval "$VENV_PYTHON" -m manimlib "$SCENE_PY" "$SCENE_CLASS" $RENDER_FLAGS 2>&1 | tee "$OUTPUT_DIR/render.log" || RENDER_RC=$?
    else
        eval "$VENV_PYTHON" -m manimlib "$SCENE_PY" $RENDER_FLAGS 2>&1 | tee "$OUTPUT_DIR/render.log" || RENDER_RC=$?
    fi

    if [[ "$RENDER_RC" -ne 0 ]]; then
        echo "[manimgl] Video render failed with exit code $RENDER_RC" >&2
        write_state "failed" "$RENDER_RC"
        write_progress "capture" "failed" "video render exited with code $RENDER_RC"
        exit "$RENDER_RC"
    fi

    if [[ -f "$OUTPUT_DIR/raw.mp4" ]]; then
        echo "[manimgl] Video ready: $OUTPUT_DIR/raw.mp4"
        write_state "completed" 0 --outputs "{\"videoPath\": \"$OUTPUT_DIR/raw.mp4\", \"outputDir\": \"$OUTPUT_DIR\", \"engine\": \"manimgl\"}"
        write_progress "capture" "completed" "video rendered"
    else
        echo "[manimgl] WARNING: render succeeded but raw.mp4 not found in $OUTPUT_DIR" >&2
        write_state "completed" 0 --outputs "{\"outputDir\": \"$OUTPUT_DIR\", \"engine\": \"manimgl\", \"warning\": \"raw.mp4 missing\"}"
        write_progress "capture" "completed" "video render finished (raw.mp4 missing)"
    fi
else
    # Interactive human mode: launch preview window
    echo "[manimgl] Launching interactive preview: $SCENE_PY"
    echo "[manimgl] Close the window to finish. Any cached frames will be preserved."

    write_progress "capture" "running" "interactive preview started"

    cd "$PROJECT_ROOT"

    RENDER_RC=0
    "$VENV_PYTHON" -m manimlib "$SCENE_PY" 2>&1 | tee "$OUTPUT_DIR/render.log" || RENDER_RC=$?

    if ls "$OUTPUT_DIR"/frame_*.png >/dev/null 2>&1; then
        echo "[manimgl] Found existing frames in $OUTPUT_DIR"
        FRAME_COUNT=$(ls "$OUTPUT_DIR"/frame_*.png 2>/dev/null | wc -l)
        write_state "completed" 0 --outputs "{\"framesRendered\": $FRAME_COUNT, \"outputDir\": \"$OUTPUT_DIR\", \"engine\": \"manimgl\"}"
        write_progress "capture" "completed" "frames captured"
    else
        echo "[manimgl] No frames captured. Interactive preview completed."
        if [[ "$RENDER_RC" -ne 0 ]]; then
            write_state "failed" "$RENDER_RC" --error "interactive preview exited with code $RENDER_RC"
            write_progress "capture" "failed" "interactive preview exited with code $RENDER_RC"
        else
            write_state "completed" 0 --outputs "{\"outputDir\": \"$OUTPUT_DIR\", \"engine\": \"manimgl\", \"mode\": \"interactive\"}"
            write_progress "capture" "completed" "preview completed without frames"
        fi
    fi
fi

echo "[manimgl] Done."
