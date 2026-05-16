#!/usr/bin/env bash
set -euo pipefail

# engines/manim/scripts/render.sh
# 接收 scene.py 路径和输出目录，调用 manim 输出帧序列
# 渲染超时由上游 bin/macode-run 统一 enforce，本脚本不使用 GNU timeout。
#
# 用法: render.sh <scene.py> <output_dir> [fps] [duration] [width] [height]
#   scene.py    - 场景源码路径
#   output_dir  - 帧序列输出目录（如 .agent/tmp/01_test/frames/）
#   fps         - 帧率（默认 30）
#   duration    - 时长（秒，由场景控制）
#   width       - 宽度（由场景控制）
#   height      - 高度（由场景控制）

if [[ "${1:-}" == "--help" || "${1:-}" == "-h" ]]; then
    cat <<EOF
Usage: $(basename "$0") <scene.py> <output_dir> [fps] [duration] [width] [height]

接收 scene.py 路径和输出目录，调用 manim 输出 PNG 帧序列。

Arguments:
  <scene.py>    场景源码路径
  <output_dir>  帧序列输出目录
  [fps]         帧率 (default: 30)
  [duration]    时长（秒，由场景控制）
  [width]       宽度（由场景控制）
  [height]      高度（由场景控制）

Examples:
  $(basename "$0") scenes/01_test/scene.py .agent/tmp/01_test/frames/
EOF
    exit 0
fi

SCENE_PY="${1:-}"
OUTPUT_DIR="${2:-}"
FPS="${3:-30}"

if [[ -z "$SCENE_PY" || -z "$OUTPUT_DIR" ]]; then
    echo "Usage: $0 <scene.py> <output_dir> [fps] [duration] [width] [height]" >&2
    exit 1
fi

if [[ ! -f "$SCENE_PY" ]]; then
    echo "Error: scene file not found: $SCENE_PY" >&2
    exit 1
fi

# 获取场景所在目录（用于 -p 模块路径）
SCENE_DIR=$(dirname "$SCENE_PY")
SCENE_NAME=$(basename "$SCENE_PY" .py)

# 确保输出目录存在
mkdir -p "$OUTPUT_DIR"

# 提前获取项目根目录（状态写入需要）
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"

# ── 状态/进度文件写入（标准 v1.0 格式）─────────────────
PROGRESS_DIR="$PROJECT_ROOT/.agent/progress"
mkdir -p "$PROGRESS_DIR"
PROGRESS_PATH="$PROGRESS_DIR/${SCENE_NAME}.jsonl"
STATE_DIR="$PROJECT_ROOT/.agent/tmp/$SCENE_NAME"
mkdir -p "$STATE_DIR"

write_progress() {
    local phase="$1"
    local status="$2"
    local message="${3:-}"
    "$PROJECT_ROOT/bin/progress-write.py" "$PROGRESS_PATH" "$phase" "$status" "$message" 2>/dev/null || true
}

write_state() {
    local status="$1"
    shift
    "$PROJECT_ROOT/bin/state-write.py" "$STATE_DIR" "$status" --tool "render.sh" "$@" 2>/dev/null || true
}

write_progress "init" "running" "Manim render starting: ${SCENE_PY}"
write_state "running" --task-id "$SCENE_NAME"
# ─────────────────────────────────────────────────────

# 使用 manim 渲染为 PNG 帧序列
# -g 指定渲染质量（不使用，由场景控制）
# --format png 输出帧序列
# --media_dir 指定输出根目录
# -o 指定输出文件名前缀

# PYTHON 必须在 keyframes 段之前赋值（本脚本 set -u，keyframes 内会调用 $PYTHON）
VENV_PYTHON="$PROJECT_ROOT/.venv/bin/python"
if [[ -x "$VENV_PYTHON" ]]; then
    PYTHON="$VENV_PYTHON"
else
    PYTHON="python3"
fi

# ── Layout snapshot keyframes ──
MANIFEST_JSON="$SCENE_DIR/manifest.json"
if [[ -f "$MANIFEST_JSON" ]]; then
    KEYFRAMES=$("$PYTHON" -c "
import json, sys
try:
    m = json.load(open('$MANIFEST_JSON'))
    kf = m.get('keyframes', [])
    if not kf and m.get('duration'):
        kf = [0.0, float(m['duration'])]
    print(','.join(str(x) for x in kf))
except Exception:
    pass
" 2>/dev/null)
    if [[ -n "$KEYFRAMES" ]]; then
        export MACODE_KEYFRAMES="$KEYFRAMES"
        export MACODE_SNAPSHOT_DIR="$OUTPUT_DIR"
        # Clean old snapshots to avoid stale data
        rm -f "$OUTPUT_DIR/layout_snapshots.jsonl"
        echo "[manim] Layout snapshots enabled at: $KEYFRAMES"
    fi
fi

echo "[manim] Rendering $SCENE_PY -> $OUTPUT_DIR"
write_progress "render" "running" "Calling manim --format png"

# ── Backend selection ──
BACKEND="gpu"
if [[ -f "$PROJECT_ROOT/.agent/hardware_profile.json" ]]; then
    BACKEND=$(bash "$PROJECT_ROOT/bin/select-backend.sh" 2>/dev/null || echo "gpu")
fi
echo "[manim] Render backend: $BACKEND"

if [[ "$BACKEND" == "d3d12" ]]; then
    export GALLIUM_DRIVER=d3d12
    export LIBGL_ALWAYS_SOFTWARE=0
    export MESA_D3D12_DEFAULT_ADAPTER_NAME=NVIDIA
    echo "[manim] D3D12 GPU acceleration (WSL2 DX12 passthrough)"
elif [[ "$BACKEND" == "cpu" ]]; then
    export LIBGL_ALWAYS_SOFTWARE=1
    echo "[manim] Forcing software OpenGL (Mesa llvmpipe)"
elif [[ "$BACKEND" == "headless" ]]; then
    echo "[manim] HEADLESS mode. No OpenGL available."
    # Generate placeholder frames logic here if needed
fi

# 将引擎适配层加入 Python 路径，使场景可 import templates/utils
ENGINE_SRC="$(cd "$(dirname "${BASH_SOURCE[0]}")/../src" && pwd)"
COMMON_SRC="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../common/src" && pwd)"
export PYTHONPATH="${ENGINE_SRC}${PYTHONPATH:+:$PYTHONPATH}"
export PYTHONPATH="${COMMON_SRC}${PYTHONPATH:+:$PYTHONPATH}"

# manim 默认输出到 media/images/<module_name>/
# 我们需要把帧移到指定输出目录
"$PYTHON" -m manim \
    --format png \
    --fps "$FPS" \
    --media_dir "$OUTPUT_DIR/.media" \
    "$SCENE_PY" \
    2>&1 | tee "$OUTPUT_DIR/render.log"

MANIM_EXIT=${PIPESTATUS[0]}
if [[ $MANIM_EXIT -ne 0 ]]; then
    echo "[manim] FAILED (exit $MANIM_EXIT). Analyzing error..." >&2
    write_progress "render" "error" "Manim exit code $MANIM_EXIT"
    write_state "failed" "$MANIM_EXIT" --error "Manim exit code $MANIM_EXIT"
    SOURCEMAP="$(dirname "$(dirname "${BASH_SOURCE[0]}")")/SOURCEMAP.md"
    if [[ -f "$SOURCEMAP" ]]; then
        if grep -q "manimlib" "$OUTPUT_DIR/render.log" 2>/dev/null; then
            echo "[diagnosis] Deprecated manimlib API detected." >&2
            echo "[action]    See BLACKLIST: DEPRECATED_GL in $SOURCEMAP" >&2
            echo "[fix]       Replace 'from manimlib' with 'from manim'" >&2
        fi
        if grep -q "_config" "$OUTPUT_DIR/render.log" 2>/dev/null; then
            echo "[diagnosis] Internal config module detected." >&2
            echo "[action]    See BLACKLIST: INTERNAL_CONFIG in $SOURCEMAP" >&2
            echo "[fix]       Remove imports from manim._config" >&2
        fi
        echo "[hint] Run 'macode inspect --grep <keyword>' to find correct API." >&2
    fi
    exit $MANIM_EXIT
fi

# manim PNG 输出目录结构: .media/images/<scene_name>/<SceneClass>/<SceneClass>0001.png
# 将其移动到标准位置并重命名为 frame_*.png
MEDIA_DIR="$OUTPUT_DIR/.media/images/$SCENE_NAME"
if [[ -d "$MEDIA_DIR" ]]; then
    # 找到实际包含 png 的子目录（通常是场景类名）
    PNG_DIR=$(find "$MEDIA_DIR" -name "*.png" -print -quit | xargs dirname 2>/dev/null || true)
    if [[ -n "$PNG_DIR" && "$PNG_DIR" != "$OUTPUT_DIR" ]]; then
        # 按字母顺序重命名为 frame_0001.png, frame_0002.png, ...
        i=1
        for f in $(ls -1 "$PNG_DIR"/*.png | sort); do
            printf -v dest "$OUTPUT_DIR/frame_%04d.png" "$i"
            mv "$f" "$dest"
            i=$((i + 1))
        done
    fi
    # 清理临时 media 目录
    rm -rf "$OUTPUT_DIR/.media"
fi

# Count rendered frames
FRAME_COUNT=$(find "$OUTPUT_DIR" -maxdepth 1 -name "frame_*.png" | wc -l)
write_progress "cleanup" "completed" "Frames in $OUTPUT_DIR"
write_state "completed" 0 --outputs "{\"framesRendered\": $FRAME_COUNT, \"outputDir\": \"$OUTPUT_DIR\", \"frameFormat\": \"png\"}"
echo "[manim] Done. $FRAME_COUNT frames in $OUTPUT_DIR"
