#!/usr/bin/env bash
set -euo pipefail

# bin/render-all.sh
# 批量渲染 scenes/ 目录下所有场景，按序号遍历。
#
# 用法: render-all.sh [scene_prefix]
#   scene_prefix - 可选，只渲染匹配前缀的场景，如 "01_"

SCENE_PREFIX="${1:-}"

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_ROOT"

# 收集所有场景目录
SCENES=$(find scenes -maxdepth 1 -mindepth 1 -type d | sort)

if [[ -z "$SCENES" ]]; then
    echo "No scenes found in scenes/" >&2
    exit 1
fi

TOTAL=$(echo "$SCENES" | wc -l)
CURRENT=0
SUCCESS=0
FAILED=0

for scene_dir in $SCENES; do
    scene_name=$(basename "$scene_dir")

    # 若指定了前缀则过滤
    if [[ -n "$SCENE_PREFIX" && ! "$scene_name" == "$SCENE_PREFIX"* ]]; then
        continue
    fi

    CURRENT=$((CURRENT + 1))
    echo "[$CURRENT/$TOTAL] Rendering $scene_dir..."

    if bash "$PROJECT_ROOT/pipeline/render.sh" "$scene_dir"; then
        echo "[$CURRENT/$TOTAL] Rendering $scene_dir... OK"
        SUCCESS=$((SUCCESS + 1))
    else
        echo "[$CURRENT/$TOTAL] Rendering $scene_dir... FAILED" >&2
        FAILED=$((FAILED + 1))
    fi
done

echo ""
echo "Done: $SUCCESS succeeded, $FAILED failed (total $CURRENT)"

if [[ "$FAILED" -gt 0 ]]; then
    exit 1
fi
