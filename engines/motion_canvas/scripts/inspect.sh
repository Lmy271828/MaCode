#!/usr/bin/env bash
set -euo pipefail

# engines/motion_canvas/scripts/inspect.sh
# 打印该引擎可用的模板与工具函数。
# 优先从 SOURCEMAP.md 读取结构化信息。

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../../.." && pwd)"
SOURCEMAP="$SCRIPT_DIR/../SOURCEMAP.md"

echo "=== Motion Canvas Engine Inspection ==="
echo ""

# ── 版本信息 ─────────────────────────────────────────
if [[ -f "$SOURCEMAP" ]]; then
    grep "引擎版本" "$SOURCEMAP" | head -1 | sed 's/>[[:space:]]*//'
    grep "适配层版本" "$SOURCEMAP" | head -1 | sed 's/>[[:space:]]*//'
fi

# 动态查询实际安装版本
if [[ -f "$PROJECT_ROOT/node_modules/@motion-canvas/core/package.json" ]]; then
    echo "  Installed: v$(node -e "console.log(require('@motion-canvas/core/package.json').version)" 2>/dev/null || echo 'unknown')"
fi
echo ""

# ── WHITELIST ────────────────────────────────────────
if [[ -f "$SOURCEMAP" ]]; then
    echo "--- WHITELIST: Safe API paths ---"
    awk '/^## WHITELIST/ {found=1; next} /^## / {if(found) exit} found && /^\|/ && !/ 标识 /' "$SOURCEMAP" | \
        while IFS='|' read -r _ id path purpose priority; do
            id=$(echo "$id" | xargs)
            priority=$(echo "$priority" | xargs)
            purpose=$(echo "$purpose" | xargs)
            printf "  %-25s [%s]  %s\n" "$id" "$priority" "$purpose"
        done
    echo ""

    echo "--- BLACKLIST: Do not touch ---"
    awk '/^## BLACKLIST/ {found=1; next} /^## / {if(found) exit} found && /^\|/ && !/ 标识 /' "$SOURCEMAP" | \
        while IFS='|' read -r _ id path reason; do
            id=$(echo "$id" | xargs)
            reason=$(echo "$reason" | xargs)
            printf "  %-25s  %s\n" "$id" "$reason"
        done
    echo ""

    echo "--- EXTENSION: Future work ---"
    awk '/^## EXTENSION/ {found=1; next} /^## / {if(found) exit} found && /^\|/ && !/ 标识 /' "$SOURCEMAP" | \
        while IFS='|' read -r _ id desc status; do
            id=$(echo "$id" | xargs)
            status=$(echo "$status" | xargs)
            desc=$(echo "$desc" | xargs)
            printf "  %-25s [%-8s] %s\n" "$id" "$status" "$desc"
        done
else
    echo "  WARN: SOURCEMAP.md not found. Run: macode sourcemap init motion_canvas"
    echo ""

    # 回退：静态列表
    echo "--- Common Nodes (static fallback) ---"
    cat <<'EOF'
  Circle  Rect  Line  Text  Layout  Node
  Img  Video  Latex  SVG  Grid  Camera
EOF
    echo ""

    echo "--- Common Signals / Hooks ---"
    cat <<'EOF'
  createSignal  createRef
  all / sequence / loop
  useLogger  useProject  useScene
EOF
fi

echo ""
echo "--- Quick API lookup ---"
echo "  Run 'macode inspect --grep <keyword>' to search SOURCEMAP."
echo "  Run 'engines/motion_canvas/scripts/validate_sourcemap.sh' to verify paths."
