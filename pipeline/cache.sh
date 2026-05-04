#!/usr/bin/env bash
set -euo pipefail

# pipeline/cache.sh
# 帧级缓存：基于 scene.py + manifest.json 内容哈希，避免重复渲染未变更的帧。
#
# 用法:
#   pipeline/cache.sh check <scene_dir> <output_dir>
#     返回 0 = cache hit（帧已复制到 output_dir/frames/）
#     返回 1 = cache miss（需正常渲染，output_dir/.cache_path 包含缓存目录路径）
#
#   pipeline/cache.sh populate <scene_dir> <output_dir>
#     渲染完成后将帧存入缓存（由 render.sh 在成功渲染后调用）

SCENE_DIR="${1:-}"
ACTION="${2:-}"
OUTPUT_DIR="${3:-}"

if [[ -z "$SCENE_DIR" || -z "$ACTION" ]]; then
    echo "Usage: $0 <scene_dir> <check|populate> [output_dir]" >&2
    exit 1
fi

SCENE_DIR="${SCENE_DIR%/}"
SCENE_NAME=$(basename "$SCENE_DIR")
MANIFEST="$SCENE_DIR/manifest.json"
CACHE_ROOT=".agent/cache"

# 引擎场景文件可能为 .py 或 .tsx
if [[ -f "$SCENE_DIR/scene.py" ]]; then
    SCENE_FILE="$SCENE_DIR/scene.py"
elif [[ -f "$SCENE_DIR/scene.tsx" ]]; then
    SCENE_FILE="$SCENE_DIR/scene.tsx"
else
    echo "[cache] WARN: no scene file found in $SCENE_DIR, skipping cache" >&2
    exit 1
fi

# ── 计算内容哈希 ──────────────────────────────────────
# 哈希对象：场景源码 + manifest 契约（两者共同决定渲染输出）
compute_hash() {
    local hash
    if command -v sha256sum >/dev/null 2>&1; then
        hash=$(cat "$SCENE_FILE" "$MANIFEST" 2>/dev/null | sha256sum | cut -d' ' -f1 | cut -c1-16)
    elif command -v md5sum >/dev/null 2>&1; then
        hash=$(cat "$SCENE_FILE" "$MANIFEST" 2>/dev/null | md5sum | cut -d' ' -f1 | cut -c1-16)
    elif command -v python3 >/dev/null 2>&1; then
        hash=$(python3 -c "
import hashlib
h = hashlib.sha256()
with open('$SCENE_FILE','rb') as f: h.update(f.read())
with open('$MANIFEST','rb') as f: h.update(f.read())
print(h.hexdigest()[:16])
")
    else
        echo "[cache] ERROR: no hash tool available (sha256sum/md5sum/python3)" >&2
        exit 1
    fi
    echo "$hash"
}

HASH=$(compute_hash)
CACHE_DIR="$CACHE_ROOT/$HASH"
CACHE_FRAMES="$CACHE_DIR/frames"

# ── check 模式：查询缓存 ──────────────────────────────
do_check() {
    local output_dir="${1:-}"
    if [[ -z "$output_dir" ]]; then
        echo "[cache] ERROR: output_dir required for check" >&2
        exit 1
    fi

    local frames_dir="$output_dir/frames"

    if [[ -d "$CACHE_FRAMES" ]] && [[ -n "$(ls -A "$CACHE_FRAMES" 2>/dev/null)" ]]; then
        local frame_count
        frame_count=$(find "$CACHE_FRAMES" -name "*.png" | wc -l)
        echo "[cache] HIT: $HASH ($frame_count frames, scene=$SCENE_NAME)"
        mkdir -p "$frames_dir"
        cp "$CACHE_FRAMES"/*.png "$frames_dir/"
        echo "[cache] Copied $frame_count frames from cache to $frames_dir"
        return 0
    else
        echo "[cache] MISS: $HASH (scene=$SCENE_NAME)"
        # 记录缓存路径，供 render.sh 在成功后 populate
        echo "$CACHE_DIR" > "$output_dir/.cache_path"
        return 1
    fi
}

# ── populate 模式：写入缓存 ───────────────────────────
do_populate() {
    local output_dir="${1:-}"
    if [[ -z "$output_dir" ]]; then
        echo "[cache] ERROR: output_dir required for populate" >&2
        exit 1
    fi

    local frames_dir="$output_dir/frames"

    if [[ ! -d "$frames_dir" ]] || [[ -z "$(ls -A "$frames_dir" 2>/dev/null)" ]]; then
        echo "[cache] WARN: no frames to cache in $frames_dir" >&2
        return 1
    fi

    local frame_count
    frame_count=$(find "$frames_dir" -name "*.png" | wc -l)

    mkdir -p "$CACHE_FRAMES"
    cp "$frames_dir"/*.png "$CACHE_FRAMES/"

    # 同时保存 manifest 副本，便于后续审计
    cp "$MANIFEST" "$CACHE_DIR/manifest.json"
    cp "$SCENE_FILE" "$CACHE_DIR/$(basename "$SCENE_FILE")"

    echo "[cache] STORED: $HASH ($frame_count frames, scene=$SCENE_NAME)"

    # 清理 .cache_path 标记文件
    rm -f "$output_dir/.cache_path"
}

case "$ACTION" in
    check)
        do_check "$OUTPUT_DIR"
        ;;
    populate)
        do_populate "$OUTPUT_DIR"
        ;;
    *)
        echo "[cache] ERROR: unknown action '$ACTION' (use check or populate)" >&2
        exit 1
        ;;
esac
