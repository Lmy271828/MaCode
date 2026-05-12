#!/usr/bin/env bash
set -euo pipefail

# engines/manim/scripts/dev.sh
# ManimCE 快速预览开发循环（编排器）。
#
# 用法: dev.sh <scene_dir>
#   scene_dir - 场景目录，如 scenes/01_test/
#
# 职责：
#   1. 计算预览参数（低分辨率、短时长）
#   2. 原子修改 manifest
#   3. 渲染预览
#   4. 恢复 manifest
#   5. 监听 scene.py 变化并重复 2-4
#
# 执行层工具：
#   - bin/calc-preview-duration.py    计算预览时长
#   - bin/patch-manifest.py           原子修改/恢复 manifest
#   - engines/manim/scripts/render-preview.sh  单次预览渲染
#   - bin/signal-check.py             查询人类介入信号

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../../.." && pwd)"

if [[ "${1:-}" == "--help" || "${1:-}" == "-h" ]]; then
    cat <<EOF
Usage: $(basename "$0") <scene_dir>

ManimCE 快速预览开发循环。监听 scene.py 变化并低分辨率渲染预览。

Arguments:
  <scene_dir>    场景目录路径，如 scenes/01_test/

Examples:
  $(basename "$0") scenes/01_test
EOF
    exit 0
fi

SCENE_DIR="${1:-}"
if [[ -z "$SCENE_DIR" ]]; then
    echo "Usage: $0 <scene_dir>" >&2
    exit 1
fi

SCENE_DIR="${SCENE_DIR%/}"
SCENE_NAME=$(basename "$SCENE_DIR")
MANIFEST="$SCENE_DIR/manifest.json"
SCENE_PY="$SCENE_DIR/scene.py"

if [[ ! -f "$MANIFEST" ]]; then
    echo "Error: manifest.json not found in $SCENE_DIR" >&2
    exit 1
fi
if [[ ! -f "$SCENE_PY" ]]; then
    echo "Error: scene.py not found in $SCENE_DIR" >&2
    exit 1
fi

# ── 1. 计算预览参数 ──
PREVIEW_DURATION=$(python3 "$PROJECT_ROOT/bin/calc-preview-duration.py" "$MANIFEST")
PREVIEW_FPS="10"
PREVIEW_WIDTH="640"
PREVIEW_HEIGHT="360"
echo "[dev] Preview: ${PREVIEW_DURATION}s @ ${PREVIEW_FPS}fps ${PREVIEW_WIDTH}x${PREVIEW_HEIGHT}"

# ── 2. 准备日志 ──
mkdir -p "$PROJECT_ROOT/.agent/log"
LOG_FILE="$PROJECT_ROOT/.agent/log/$(date +%Y%m%d_%H%M%S)_${SCENE_NAME}_dev.log"

# ── 3. 定义单次渲染流程 ──
BACKUP="$MANIFEST.dev.bak"

_run_once() {
    local action="${1:-render}"

    # 检查人类介入信号（per-scene 优先，全局回退）
    local signals_json
    signals_json=$(python3 "$PROJECT_ROOT/bin/signal-check.py" --scene "$SCENE_NAME" 2>/dev/null || echo '{}')

    local pause abort
    pause=$(echo "$signals_json" | SCENE_NAME="$SCENE_NAME" SIGNAL_NAME="pause" python3 -c "
import json, sys, os
d = json.load(sys.stdin)
scene = os.environ['SCENE_NAME']
sig = os.environ['SIGNAL_NAME']
print(d.get('scenes', {}).get(scene, {}).get(sig,
      d.get('global', {}).get(sig, False)))
")
    abort=$(echo "$signals_json" | SCENE_NAME="$SCENE_NAME" SIGNAL_NAME="abort" python3 -c "
import json, sys, os
d = json.load(sys.stdin)
scene = os.environ['SCENE_NAME']
sig = os.environ['SIGNAL_NAME']
print(d.get('scenes', {}).get(scene, {}).get(sig,
      d.get('global', {}).get(sig, False)))
")

    if [[ "$pause" == "True" || "$pause" == "true" ]]; then
        if [[ "$action" == "render" ]]; then
            echo "[dev] PAUSE signal detected. Waiting..."
        fi
        return 2
    fi

    if [[ "$abort" == "True" || "$abort" == "true" ]]; then
        echo "[dev] ABORT signal detected. Exiting."
        return 1
    fi

    # 原子修改 manifest
    python3 "$PROJECT_ROOT/bin/patch-manifest.py" "$MANIFEST" \
        --backup "$BACKUP" \
        --duration "$PREVIEW_DURATION" \
        --fps "$PREVIEW_FPS" \
        --resolution "${PREVIEW_WIDTH}x${PREVIEW_HEIGHT}" \
        >> "$LOG_FILE" 2>&1

    # 渲染预览
    bash "$PROJECT_ROOT/engines/manim/scripts/render-preview.sh" "$SCENE_DIR" >> "$LOG_FILE" 2>&1 || true

    # 恢复 manifest
    python3 "$PROJECT_ROOT/bin/patch-manifest.py" "$MANIFEST" --restore "$BACKUP" >> "$LOG_FILE" 2>&1

    return 0
}

# ── 4. 初始渲染 ──
_run_once "render"
RET=$?
if [[ "$RET" -eq 1 ]]; then
    exit 0
fi
if [[ "$RET" -eq 2 ]]; then
    # PAUSE 状态，进入循环等待
    :
fi

# ── 5. 监听循环 ──
echo "[dev] Watching $SCENE_PY for changes..."
echo "[dev] Press Ctrl+C to stop."

LAST_MTIME=$(stat -c %Y "$SCENE_PY" 2>/dev/null || echo "0")

while true; do
    sleep 2

    CURRENT_MTIME=$(stat -c %Y "$SCENE_PY" 2>/dev/null || echo "0")
    if [[ "$CURRENT_MTIME" == "$LAST_MTIME" ]]; then
        continue
    fi

    LAST_MTIME="$CURRENT_MTIME"
    echo "[dev] Detected change in $SCENE_PY at $(date '+%H:%M:%S')"

    _run_once "render"
    RET=$?
    if [[ "$RET" -eq 1 ]]; then
        exit 0
    fi
    if [[ "$RET" -eq 2 ]]; then
        # PAUSE 状态，持续检查直到清除
        while true; do
            sleep 3
            _run_once "check"
            RET=$?
            if [[ "$RET" -eq 1 ]]; then
                exit 0
            fi
            if [[ "$RET" -ne 2 ]]; then
                break
            fi
        done
        echo "[dev] PAUSE cleared. Resuming..."
    fi
done
