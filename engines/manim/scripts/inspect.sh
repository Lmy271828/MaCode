#!/usr/bin/env bash
set -euo pipefail

# engines/manim/scripts/inspect.sh
# 打印该引擎可用的模板与工具函数。
# 通过 sourcemap-read 消费 JSON，不再直接解析 Markdown。

if [[ "${1:-}" == "--help" || "${1:-}" == "-h" ]]; then
    cat <<EOF
Usage: $(basename "$0")

打印 ManimCE 引擎可用的模板与工具函数（通过 SOURCEMAP）。

Arguments:
  (无)

Examples:
  $(basename "$0")
EOF
    exit 0
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../../.." && pwd)"
VENV_PYTHON="$PROJECT_ROOT/.venv/bin/python"
if [[ -x "$VENV_PYTHON" ]]; then
    PYTHON="$VENV_PYTHON"
else
    PYTHON="python3"
fi

SOURCEMAP="$SCRIPT_DIR/../SOURCEMAP.md"

# ── 确保 JSON 机器接口新鲜 ───────────────────────────
if [[ -f "$SOURCEMAP" ]]; then
    if ! python3 "$PROJECT_ROOT/bin/sourcemap-sync.py" --check manim >/dev/null 2>&1; then
        python3 "$PROJECT_ROOT/bin/sourcemap-sync.py" manim >/dev/null 2>&1 || true
    fi
fi

show_redirects() {
    echo "--- REDIRECT: Common Pitfall Corrections ---"
    bash "$PROJECT_ROOT/bin/sourcemap-read" manim redirect 2>/dev/null || echo "  (sourcemap-read failed)"
    echo ""
}

echo "=== ManimCE Engine Inspection ==="
echo ""

# ── 版本信息 ─────────────────────────────────────────
echo "--- Version ---"
if [[ -f "$SOURCEMAP" ]]; then
    grep "引擎版本" "$SOURCEMAP" | head -1 | sed 's/>[[:space:]]*//'
    grep "适配层版本" "$SOURCEMAP" | head -1 | sed 's/>[[:space:]]*//'
fi
"$PYTHON" -m manim --version 2>&1 || echo "  (manim not available in current environment)"
echo ""

# ── WHITELIST / BLACKLIST / EXTENSION ────────────────
if [[ -f "$SOURCEMAP" ]]; then
    echo "--- WHITELIST: Safe API paths ---"
    bash "$PROJECT_ROOT/bin/sourcemap-read" manim whitelist 2>/dev/null || echo "  (sourcemap-read failed)"
    echo ""

    echo "--- BLACKLIST: Do not touch ---"
    bash "$PROJECT_ROOT/bin/sourcemap-read" manim blacklist 2>/dev/null || echo "  (sourcemap-read failed)"
    echo ""

    echo "--- EXTENSION: Future work ---"
    bash "$PROJECT_ROOT/bin/sourcemap-read" manim extension 2>/dev/null || echo "  (sourcemap-read failed)"
    echo ""

    show_redirects
else
    echo "  WARN: SOURCEMAP.md not found. Run: macode sourcemap init manim"
    echo ""

    # 回退：动态查询
    echo "--- Built-in Mobjects (dynamic) ---"
    "$PYTHON" -c "
import manim
mobjects = [
    'Circle', 'Square', 'Rectangle', 'Triangle', 'Line', 'Arrow', 'Text',
    'MathTex', 'VGroup', 'Axes', 'NumberPlane', 'Graph',
]
for name in mobjects:
    if hasattr(manim, name):
        print(f'  {name}')
" 2>&1
    echo ""

    echo "--- Package Path ---"
    "$PYTHON" -c "import manim; print(manim.__path__[0])" 2>&1
fi

echo ""
echo "--- Quick API lookup ---"
echo "  Run 'macode inspect --grep <keyword>' to search SOURCEMAP."
echo "  Run 'engines/manim/scripts/validate_sourcemap.sh' to verify paths."
