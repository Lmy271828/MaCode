#!/usr/bin/env bash
set -euo pipefail

# engines/manim/scripts/render.sh
# 接收 scene.py 路径和输出目录，调用 manim 输出帧序列
#
# 用法: render.sh <scene.py> <output_dir> [fps] [duration] [width] [height]
#   scene.py    - 场景源码路径
#   output_dir  - 帧序列输出目录（如 .agent/tmp/01_test/frames/）
#   fps         - 帧率（默认 30）
#   duration    - 时长（秒，由场景控制）
#   width       - 宽度（由场景控制）
#   height      - 高度（由场景控制）

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

# 使用 manim 渲染为 PNG 帧序列
# -g 指定渲染质量（不使用，由场景控制）
# --format png 输出帧序列
# --media_dir 指定输出根目录
# -o 指定输出文件名前缀

echo "[manim] Rendering $SCENE_PY -> $OUTPUT_DIR"

# 定位 conda math 环境的 Python
CONDA_PYTHON="$HOME/miniconda3/envs/math/bin/python"
if [[ -x "$CONDA_PYTHON" ]]; then
    PYTHON="$CONDA_PYTHON"
else
    PYTHON="python3"
fi

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

echo "[manim] Done. Frames in $OUTPUT_DIR"
