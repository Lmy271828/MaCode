#!/usr/bin/env bash
set -euo pipefail

# engines/manim/scripts/inspect.sh
# 打印该引擎可用的模板与工具函数。
# 优先从 SOURCEMAP.md 读取结构化信息，回退到动态查询。

CONDA_PYTHON="$HOME/miniconda3/envs/math/bin/python"
if [[ -x "$CONDA_PYTHON" ]]; then
    PYTHON="$CONDA_PYTHON"
else
    PYTHON="python3"
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SOURCEMAP="$SCRIPT_DIR/../SOURCEMAP.md"

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

# ── WHITELIST (safe to explore) ───────────────────
if [[ -f "$SOURCEMAP" ]]; then
    echo "--- WHITELIST: Safe API paths ---"
    awk '/^## WHITELIST/ {found=1; next} /^## / {if(found) exit} found && /^\|/ && !/ 标识 /' "$SOURCEMAP" | \
        while IFS='|' read -r _ id path purpose priority; do
            id=$(echo "$id" | xargs)
            priority=$(echo "$priority" | xargs)
            purpose=$(echo "$purpose" | xargs)
            printf "  %-30s [%s]  %s\n" "$id" "$priority" "$purpose"
        done
    echo ""

    echo "--- BLACKLIST: Do not touch ---"
    awk '/^## BLACKLIST/ {found=1; next} /^## / {if(found) exit} found && /^\|/ && !/ 标识 /' "$SOURCEMAP" | \
        while IFS='|' read -r _ id path reason; do
            id=$(echo "$id" | xargs)
            reason=$(echo "$reason" | xargs)
            printf "  %-30s  %s\n" "$id" "$reason"
        done
    echo ""

    echo "--- EXTENSION: Future work ---"
    awk '/^## EXTENSION/ {found=1; next} /^## / {if(found) exit} found && /^\|/ && !/ 标识 /' "$SOURCEMAP" | \
        while IFS='|' read -r _ id desc status; do
            id=$(echo "$id" | xargs)
            status=$(echo "$status" | xargs)
            desc=$(echo "$desc" | xargs)
            printf "  %-30s [%-8s] %s\n" "$id" "$status" "$desc"
        done
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
