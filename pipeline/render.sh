#!/usr/bin/env bash
set -euo pipefail

# pipeline/render.sh
# 读取场景目录的 manifest.json，调用对应引擎渲染脚本。
#
# 用法: pipeline/render.sh <scene_dir>
#   scene_dir - 场景目录，如 scenes/01_test/

SCENE_DIR="${1:-}"

if [[ -z "$SCENE_DIR" ]]; then
    echo "Usage: $0 <scene_dir>" >&2
    exit 1
fi

# 标准化路径（去除尾部斜杠）
SCENE_DIR="${SCENE_DIR%/}"
SCENE_NAME=$(basename "$SCENE_DIR")

MANIFEST="$SCENE_DIR/manifest.json"
if [[ ! -f "$MANIFEST" ]]; then
    echo "Error: manifest.json not found in $SCENE_DIR" >&2
    exit 1
fi

# 读取 manifest：引擎类型 + 场景文件扩展名
if command -v jq >/dev/null 2>&1; then
    ENGINE=$(jq -r '.engine // "manim"' "$MANIFEST")
    FPS=$(jq -r '.fps // 30' "$MANIFEST")
    DURATION=$(jq -r '.duration // 3' "$MANIFEST")
    RESOLUTION=$(jq -r '.resolution // [1920, 1080]' "$MANIFEST")
else
    # Fallback: use Python for JSON parsing (always available in conda math env)
    PYTHON="${HOME}/miniconda3/envs/math/bin/python"
    if [[ ! -x "$PYTHON" ]]; then
        PYTHON="python3"
    fi
    ENGINE=$($PYTHON -c "import json,sys; print(json.load(open('$MANIFEST')).get('engine','manim'))")
    FPS=$($PYTHON -c "import json,sys; print(json.load(open('$MANIFEST')).get('fps',30))")
    DURATION=$($PYTHON -c "import json,sys; print(json.load(open('$MANIFEST')).get('duration',3))")
    RESOLUTION=$($PYTHON -c "import json,sys; print(json.load(open('$MANIFEST')).get('resolution',[1920,1080]))")
fi

# 根据引擎确定场景文件扩展名和路径
case "$ENGINE" in
    manim)
        SCENE_FILE="$SCENE_DIR/scene.py"
        ;;
    motion_canvas)
        SCENE_FILE="$SCENE_DIR/scene.tsx"
        ;;
    *)
        echo "Error: unsupported engine '$ENGINE'" >&2
        exit 1
        ;;
esac

if [[ ! -f "$SCENE_FILE" ]]; then
    echo "Error: scene file not found: $SCENE_FILE" >&2
    exit 1
fi

# 解析分辨率
if command -v jq >/dev/null 2>&1; then
    WIDTH=$(echo "$RESOLUTION" | jq '.[0]')
    HEIGHT=$(echo "$RESOLUTION" | jq '.[1]')
else
    WIDTH=$($PYTHON -c "import ast; print(ast.literal_eval('$RESOLUTION')[0])")
    HEIGHT=$($PYTHON -c "import ast; print(ast.literal_eval('$RESOLUTION')[1])")
fi

# 确定输出目录
OUTPUT_DIR=".agent/tmp/$SCENE_NAME"
FRAMES_DIR="$OUTPUT_DIR/frames"
mkdir -p "$FRAMES_DIR"

# 记录日志
LOG_FILE=".agent/log/$(date +%Y%m%d_%H%M%S)_${SCENE_NAME}.log"
mkdir -p ".agent/log"

echo "[$ENGINE] Rendering $SCENE_NAME..."
echo "[$ENGINE] Scene: $SCENE_FILE"
echo "[$ENGINE] Output: $FRAMES_DIR"
echo "[$ENGINE] Settings: ${WIDTH}x${HEIGHT} @ ${FPS}fps for ${DURATION}s"

# 定位项目根目录
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

# 调用引擎渲染脚本
ENGINE_SCRIPT="$PROJECT_ROOT/engines/$ENGINE/scripts/render.sh"
if [[ ! -f "$ENGINE_SCRIPT" ]]; then
    echo "Error: engine script not found: $ENGINE_SCRIPT" >&2
    exit 1
fi

# ── Manifest 校验 ─────────────────────────────────────
validate_manifest() {
    local m="$1"
    local errors=0

    # 必填字段检查
    for field in engine duration fps resolution; do
        if ! grep -q "\"$field\"" "$m" 2>/dev/null; then
            echo "  ✗ Missing required field: $field" >&2
            errors=$((errors + 1))
        fi
    done

    # engine 值校验（sed 提取，兼容无 jq 环境）
    local engine_val
    engine_val=$(sed -n 's/.*"engine"[[:space:]]*:[[:space:]]*"\([^"]*\)".*/\1/p' "$m" 2>/dev/null || true)
    if [[ -n "$engine_val" ]] && [[ "$engine_val" != "manim" && "$engine_val" != "motion_canvas" ]]; then
        echo "  ✗ Unsupported engine: '$engine_val' (use manim or motion_canvas)" >&2
        errors=$((errors + 1))
    fi

    # duration: 必须是正数
    local dur_val
    dur_val=$(sed -n 's/.*"duration"[[:space:]]*:[[:space:]]*\([0-9.]*\).*/\1/p' "$m" 2>/dev/null || echo "")
    if [[ -z "$dur_val" ]]; then
        echo "  ✗ duration is required" >&2
        errors=$((errors + 1))
    elif [[ "$dur_val" == "0" ]]; then
        echo "  ✗ duration must be > 0" >&2
        errors=$((errors + 1))
    fi

    # fps: 必须是正整数
    local fps_val
    fps_val=$(sed -n 's/.*"fps"[[:space:]]*:[[:space:]]*\([0-9]*\).*/\1/p' "$m" 2>/dev/null || echo "")
    if [[ -z "$fps_val" || "$fps_val" -le 0 ]]; then
        echo "  ✗ fps must be a positive integer, got: '$fps_val'" >&2
        errors=$((errors + 1))
    fi

    # resolution: 必须是 [width, height] 数组
    local res_val
    res_val=$(sed -n 's/.*"resolution"[[:space:]]*:[[:space:]]*\[[[:space:]]*\([0-9]*\)[[:space:]]*,[[:space:]]*\([0-9]*\)[[:space:]]*\].*/\1x\2/p' "$m" 2>/dev/null || true)
    if [[ -z "$res_val" ]]; then
        echo "  ✗ resolution must be [width, height]" >&2
        errors=$((errors + 1))
    fi

    return $errors
}

echo "[validate] Checking manifest..."
if ! validate_manifest "$MANIFEST"; then
    echo "[validate] FAILED. Fix manifest.json before rendering." >&2
    exit 1
fi
echo "[validate] OK"
# ──────────────────────────────────────────────────────

# ── API-Gate: 代码审查门 ────────────────────────────
SOURCEMAP="engines/${ENGINE}/SOURCEMAP.md"
if [[ -f "$SOURCEMAP" && -x "$PROJECT_ROOT/bin/api-gate.py" ]]; then
    echo "[api-gate] Checking $SCENE_FILE against SOURCEMAP BLACKLIST..."
    if ! "$PROJECT_ROOT/bin/api-gate.py" "$SCENE_FILE" "$SOURCEMAP" >> "$LOG_FILE" 2>&1; then
        echo "[api-gate] BLOCKED. Fix violations before rendering." | tee -a "$LOG_FILE"
        tail -5 "$LOG_FILE"
        exit 1
    fi
    echo "[api-gate] OK"
fi
# ──────────────────────────────────────────────────────

# ── Phase 4.1: 帧级缓存检查 ──────────────────────────
CACHE_SCRIPT="$PROJECT_ROOT/pipeline/cache.sh"
if [[ -x "$CACHE_SCRIPT" ]]; then
    if "$CACHE_SCRIPT" "$SCENE_DIR" check "$OUTPUT_DIR" >> "$LOG_FILE" 2>&1; then
        echo "[cache] Using cached frames, skipping engine render"
    else
        echo "[cache] Cache miss, rendering with $ENGINE..."
        bash "$ENGINE_SCRIPT" "$SCENE_FILE" "$FRAMES_DIR" "$FPS" "$DURATION" "$WIDTH" "$HEIGHT" >> "$LOG_FILE" 2>&1
    fi
else
    bash "$ENGINE_SCRIPT" "$SCENE_FILE" "$FRAMES_DIR" "$FPS" "$DURATION" "$WIDTH" "$HEIGHT" >> "$LOG_FILE" 2>&1
fi
# ──────────────────────────────────────────────────────

# ── Resource Fuse Checks ──────────────────────────────────────
FRAME_COUNT=$(find "$FRAMES_DIR" -name "*.png" | wc -l)
if [[ "$FRAME_COUNT" -gt 10000 ]]; then
    echo "FUSE: frame count $FRAME_COUNT exceeds limit 10000" >&2
    exit 1
fi

# 50 GB = 53687091200 bytes
DISK_BYTES=$(du -sb .agent/tmp/ 2>/dev/null | awk '{print $1}')
if [[ "$DISK_BYTES" -gt 53687091200 ]]; then
    DISK_GB=$((DISK_BYTES / 1024 / 1024 / 1024))
    echo "FUSE: disk usage ${DISK_GB}GB exceeds limit 50GB" >&2
    exit 1
fi
# ──────────────────────────────────────────────────────────────

# 编码为 MP4
bash "$PROJECT_ROOT/pipeline/concat.sh" "$FRAMES_DIR" "$OUTPUT_DIR/raw.mp4" >> "$LOG_FILE" 2>&1

# Phase 2: 仍然无音频，raw.mp4 即 final.mp4
cp "$OUTPUT_DIR/raw.mp4" "$OUTPUT_DIR/final.mp4"

# ── Phase 4.1: 缓存写入 ──────────────────────────────
if [[ -x "$CACHE_SCRIPT" ]]; then
    "$CACHE_SCRIPT" "$SCENE_DIR" populate "$OUTPUT_DIR" >> "$LOG_FILE" 2>&1 || true
fi
# ──────────────────────────────────────────────────────

echo "Done: $OUTPUT_DIR/final.mp4"
