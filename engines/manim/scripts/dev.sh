#!/usr/bin/env bash
set -euo pipefail

# engines/manim/scripts/dev.sh
# ManimCE 的快速预览开发循环。
#
# 用法: dev.sh <scene_dir>
#   scene_dir - 场景目录，如 scenes/01_test/
#
# 功能:
#   1. 提取 acts.json，计算总时长
#   2. 如果总时长 > 10s，只渲染前 3 秒作为预览
#   3. 用低分辨率（360p, 10fps）快速渲染
#   4. 生成 preview.mp4
#   5. 监听 scene.py 文件变化
#   6. 文件变化后，重复步骤 2-4

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../../.." && pwd)"

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

# 确保日志目录存在
mkdir -p "$PROJECT_ROOT/.agent/log"
LOG_FILE="$PROJECT_ROOT/.agent/log/$(date +%Y%m%d_%H%M%S)_${SCENE_NAME}_dev.log"

# 解析 manifest 中的 duration（优先）或从 acts 计算
_get_total_duration() {
    local m="$1"
    local dur=""
    if command -v jq >/dev/null 2>&1; then
        dur=$(jq -r '.duration // empty' "$m" 2>/dev/null)
    fi
    if [[ -z "$dur" ]]; then
        dur=$(python3 -c "import json,sys; print(json.load(open('$m')).get('duration',''))" 2>/dev/null)
    fi
    echo "$dur"
}

# 提取 acts 并计算最大时间范围（作为 fallback）
_get_acts_duration() {
    local m="$1"
    python3 -c "
import json
try:
    data = json.load(open('$m'))
    acts = data.get('acts', [])
    if not acts:
        print(data.get('duration', 0))
    else:
        max_end = 0
        for act in acts:
            tr = act.get('time_range', [])
            if len(tr) >= 2:
                max_end = max(max_end, tr[1])
        print(max_end)
except:
    print(0)
" 2>/dev/null || echo "0"
}

# 计算预览时长
TOTAL_DURATION=$(_get_total_duration "$MANIFEST")
if [[ -z "$TOTAL_DURATION" || "$TOTAL_DURATION" == "0" ]]; then
    TOTAL_DURATION=$(_get_acts_duration "$MANIFEST")
fi

# 预览时长: 如果总时长 > 10s，只取前 3s；否则取总时长
if awk "BEGIN {exit !($TOTAL_DURATION > 10)}"; then
    PREVIEW_DURATION="3"
    echo "[dev] Total duration ${TOTAL_DURATION}s > 10s, previewing first 3s"
else
    PREVIEW_DURATION="$TOTAL_DURATION"
    echo "[dev] Total duration ${TOTAL_DURATION}s, previewing full scene"
fi

# 快速预览设置
PREVIEW_FPS="10"
PREVIEW_WIDTH="640"
PREVIEW_HEIGHT="360"

OUTPUT_DIR="$PROJECT_ROOT/.agent/tmp/$SCENE_NAME"
PREVIEW_MP4="$OUTPUT_DIR/preview.mp4"

# 备份 manifest
MANIFEST_BACKUP="$MANIFEST.dev.bak"

_cleanup() {
    if [[ -f "$MANIFEST_BACKUP" ]]; then
        mv "$MANIFEST_BACKUP" "$MANIFEST"
        echo "[dev] Restored manifest.json"
    fi
}
trap _cleanup EXIT INT TERM

# 修改 manifest 为预览设置
_patch_manifest() {
    python3 -c "
import json
import re
with open('$MANIFEST', 'r') as f:
    m = json.load(f)
with open('$MANIFEST_BACKUP', 'w') as f:
    json.dump(m, f, indent=2, ensure_ascii=False)
    f.write('\n')
m['duration'] = $PREVIEW_DURATION
m['fps'] = $PREVIEW_FPS
m['resolution'] = [$PREVIEW_WIDTH, $PREVIEW_HEIGHT]
raw = json.dumps(m, indent=2, ensure_ascii=False)
# pipeline/render.sh 的 validate_manifest 用 sed 正则解析 resolution，要求它在单行
raw = re.sub(r'\"resolution\": \[\s*(\d+),\s*(\d+)\s*\]', r'\"resolution\": [\1, \2]', raw)
with open('$MANIFEST', 'w') as f:
    f.write(raw)
    f.write('\n')
print('[dev] Patched manifest: ${PREVIEW_DURATION}s @ ${PREVIEW_FPS}fps ${PREVIEW_WIDTH}x${PREVIEW_HEIGHT}')
" 2>&1 | tee -a "$LOG_FILE"
}

# 渲染并生成预览
_render_preview() {
    echo "[dev] Rendering preview..."
    if bash "$PROJECT_ROOT/pipeline/render.sh" "$SCENE_DIR" >> "$LOG_FILE" 2>&1; then
        local raw_mp4="$OUTPUT_DIR/raw.mp4"
        local final_mp4="$OUTPUT_DIR/final.mp4"
        local src_mp4=""
        if [[ -f "$raw_mp4" ]]; then
            src_mp4="$raw_mp4"
        elif [[ -f "$final_mp4" ]]; then
            src_mp4="$final_mp4"
        fi

        if [[ -n "$src_mp4" && -f "$src_mp4" ]]; then
            bash "$PROJECT_ROOT/pipeline/preview.sh" "$src_mp4" "$PREVIEW_MP4" "$PREVIEW_WIDTH" "$PREVIEW_FPS" >> "$LOG_FILE" 2>&1
            echo "[dev] Preview ready: $PREVIEW_MP4"
        else
            echo "[dev] Warning: no output video found after render" >&2
        fi
    else
        echo "[dev] Render failed. Check log: $LOG_FILE" >&2
    fi
}

# 初始渲染
_patch_manifest
_render_preview

# 恢复 manifest（在循环前恢复，避免持续修改）
if [[ -f "$MANIFEST_BACKUP" ]]; then
    mv "$MANIFEST_BACKUP" "$MANIFEST"
fi
# 清除 trap，后面手动管理
trap - EXIT INT TERM

echo "[dev] Watching $SCENE_PY for changes..."
echo "[dev] Press Ctrl+C to stop."

# 轮询监听文件变化（inotifywait 不可用时的 fallback）
LAST_MTIME=$(stat -c %Y "$SCENE_PY" 2>/dev/null || echo "0")

while true; do
    sleep 2

    CURRENT_MTIME=$(stat -c %Y "$SCENE_PY" 2>/dev/null || echo "0")
    if [[ "$CURRENT_MTIME" == "$LAST_MTIME" ]]; then
        continue
    fi

    LAST_MTIME="$CURRENT_MTIME"
    echo "[dev] Detected change in $SCENE_PY at $(date '+%H:%M:%S')"

    # 检查人类介入信号
    SIGNALS=$(bash "$PROJECT_ROOT/bin/signal-check.sh" "$SCENE_NAME" 2>/dev/null || echo '{}')
    PAUSE=$(echo "$SIGNALS" | python3 -c "import json,sys; print(json.load(sys.stdin).get('pause',False))")
    ABORT=$(echo "$SIGNALS" | python3 -c "import json,sys; print(json.load(sys.stdin).get('abort',False))")

    if [[ "$PAUSE" == "True" || "$PAUSE" == "true" ]]; then
        echo "[dev] PAUSE signal detected. Waiting..."
        while [[ "$PAUSE" == "True" || "$PAUSE" == "true" ]]; do
            sleep 3
            SIGNALS=$(bash "$PROJECT_ROOT/bin/signal-check.sh" "$SCENE_NAME" 2>/dev/null || echo '{}')
            PAUSE=$(echo "$SIGNALS" | python3 -c "import json,sys; print(json.load(sys.stdin).get('pause',False))")
        done
        echo "[dev] PAUSE cleared. Resuming..."
    fi

    if [[ "$ABORT" == "True" || "$ABORT" == "true" ]]; then
        echo "[dev] ABORT signal detected. Exiting."
        exit 0
    fi

    # 重新打补丁并渲染
    _patch_manifest
    _render_preview
    if [[ -f "$MANIFEST_BACKUP" ]]; then
        mv "$MANIFEST_BACKUP" "$MANIFEST"
    fi
done
