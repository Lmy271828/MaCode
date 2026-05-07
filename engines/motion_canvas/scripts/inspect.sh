#!/usr/bin/env bash
set -euo pipefail

# engines/motion_canvas/scripts/inspect.sh
# 打印该引擎可用的模板与工具函数。
# 通过 sourcemap-read 消费 JSON，不再直接解析 Markdown。

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../../.." && pwd)"
SOURCEMAP="$SCRIPT_DIR/../SOURCEMAP.md"

# ── 确保 JSON 机器接口新鲜 ───────────────────────────
if [[ -f "$SOURCEMAP" ]]; then
    if ! python3 "$PROJECT_ROOT/bin/sourcemap-sync.py" --check motion_canvas >/dev/null 2>&1; then
        python3 "$PROJECT_ROOT/bin/sourcemap-sync.py" motion_canvas >/dev/null 2>&1 || true
    fi
fi

show_redirects() {
    echo "--- REDIRECT: Common Pitfall Corrections ---"
    bash "$PROJECT_ROOT/bin/sourcemap-read" motion_canvas redirect 2>/dev/null || echo "  (sourcemap-read failed)"
    echo ""
}

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

# ── WHITELIST / BLACKLIST / EXTENSION ────────────────
if [[ -f "$SOURCEMAP" ]]; then
    echo "--- WHITELIST: Safe API paths ---"
    bash "$PROJECT_ROOT/bin/sourcemap-read" motion_canvas whitelist 2>/dev/null || echo "  (sourcemap-read failed)"
    echo ""

    echo "--- BLACKLIST: Do not touch ---"
    bash "$PROJECT_ROOT/bin/sourcemap-read" motion_canvas blacklist 2>/dev/null || echo "  (sourcemap-read failed)"
    echo ""

    echo "--- EXTENSION: Future work ---"
    bash "$PROJECT_ROOT/bin/sourcemap-read" motion_canvas extension 2>/dev/null || echo "  (sourcemap-read failed)"
    echo ""

    show_redirects
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
