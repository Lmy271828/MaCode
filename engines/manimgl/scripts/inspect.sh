#!/usr/bin/env bash
set -euo pipefail

# engines/manimgl/scripts/inspect.sh
# 打印该引擎可用的模板与工具函数。
# 通过 sourcemap-read 消费 JSON，不再直接解析 Markdown。

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../../.." && pwd)"
VENV_PYTHON="$PROJECT_ROOT/.venv-manimgl/bin/python"
if [[ -x "$VENV_PYTHON" ]]; then
    PYTHON="$VENV_PYTHON"
else
    PYTHON="python3"
fi

SOURCEMAP="$SCRIPT_DIR/../SOURCEMAP.md"

# ── 确保 JSON 机器接口新鲜 ───────────────────────────
if [[ -f "$SOURCEMAP" ]]; then
    if ! python3 "$PROJECT_ROOT/bin/sourcemap-sync.py" --check manimgl >/dev/null 2>&1; then
        python3 "$PROJECT_ROOT/bin/sourcemap-sync.py" manimgl >/dev/null 2>&1 || true
    fi
fi

show_redirects() {
    echo "--- REDIRECT: Common Pitfall Corrections ---"
    bash "$PROJECT_ROOT/bin/sourcemap-read" manimgl redirect 2>/dev/null || echo "  (sourcemap-read failed)"
    echo ""
}

echo "=== ManimGL Engine Inspection ==="
echo ""

# ── 版本信息 ─────────────────────────────────────────
if [[ -f "$SOURCEMAP" ]]; then
    grep "引擎版本" "$SOURCEMAP" | head -1 | sed 's/>[[:space:]]*//'
    grep "适配层版本" "$SOURCEMAP" | head -1 | sed 's/>[[:space:]]*//'
fi
if [[ -x "$VENV_PYTHON" ]]; then
    "$PYTHON" -c "import manimlib; print('  Installed: v' + manimlib.__version__)" 2>/dev/null || echo "  (manimlib not available in current environment)"
else
    echo "  (ManimGL not installed — static list below)"
fi
echo ""

# ── WHITELIST / BLACKLIST / EXTENSION ────────────────
if [[ -f "$SOURCEMAP" ]]; then
    echo "--- WHITELIST: Safe API paths ---"
    bash "$PROJECT_ROOT/bin/sourcemap-read" manimgl whitelist 2>/dev/null || echo "  (sourcemap-read failed)"
    echo ""

    echo "--- BLACKLIST: Do not touch ---"
    bash "$PROJECT_ROOT/bin/sourcemap-read" manimgl blacklist 2>/dev/null || echo "  (sourcemap-read failed)"
    echo ""

    echo "--- EXTENSION: Future work ---"
    bash "$PROJECT_ROOT/bin/sourcemap-read" manimgl extension 2>/dev/null || echo "  (sourcemap-read failed)"
    echo ""

    show_redirects
else
    echo "  WARN: SOURCEMAP.md not found. Run: macode sourcemap init manimgl"
    echo ""

    # 回退：静态列表
    echo "--- Built-in Mobjects (static fallback) ---"
    cat <<'EOF'
  Circle  Square  Rectangle  Triangle  Line  Arrow
  Tex  Text  TextMobject  NumberLine  Axes  ComplexPlane
  VGroup  Mobject  VMobject  Dot  Ellipse  Polygon
EOF
    echo ""

    echo "--- Common Animations ---"
    cat <<'EOF'
  ShowCreation  Transform  ReplacementTransform
  FadeIn  FadeOut  FadeToColor
  MoveToTarget  ComplexHomotopy
  Flash  FocusOn  Indicate
EOF
    echo ""

    echo "--- Package Path ---"
    if [[ -x "$VENV_PYTHON" ]]; then
        "$PYTHON" -c "import manimlib; print(manimlib.__path__[0])" 2>/dev/null || echo "  (manimlib not installed)"
    else
        echo "  (manimlib not installed)"
    fi
fi

echo ""
echo "--- Quick API lookup ---"
echo "  Run 'macode inspect --grep <keyword>' to search SOURCEMAP."
echo "  Run 'engines/manimgl/scripts/validate_sourcemap.sh' to verify paths."
