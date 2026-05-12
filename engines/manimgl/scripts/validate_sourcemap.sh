#!/usr/bin/env bash
set -euo pipefail

# engines/manimgl/scripts/validate_sourcemap.sh
# 验证 SOURCEMAP.md 中 WHITELIST/BLACKLIST 路径的真实性。
#
# 用法: validate_sourcemap.sh

if [[ "${1:-}" == "--help" || "${1:-}" == "-h" ]]; then
    cat <<EOF
Usage: $(basename "$0")

验证 SOURCEMAP.md 中 WHITELIST/BLACKLIST 路径的真实性。

Arguments:
  (无)

Examples:
  $(basename "$0")
EOF
    exit 0
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../../.." && pwd)"
SOURCEMAP="$SCRIPT_DIR/../SOURCEMAP.md"

if [[ ! -f "$SOURCEMAP" ]]; then
    echo "FATAL: SOURCEMAP.md not found at $SOURCEMAP" >&2
    exit 1
fi

echo "=== Validating SOURCEMAP for: manimgl ==="
echo "  Source: $SOURCEMAP"
echo ""

PASS=0
FAIL=0
SKIP=0

extract_section() {
    local section="$1"
    local file="$2"
    awk "/^## ${section}/ {found=1; next} /^## / {if(found) exit} found && /^\\|/" "$file"
}

# 尝试定位 manimlib 包根目录
MANIMLIB_ROOT=""
VENV_PYTHON="$PROJECT_ROOT/.venv-manimgl/bin/python"
if [[ -x "$VENV_PYTHON" ]]; then
    MANIMLIB_ROOT=$("$VENV_PYTHON" -c "import manimlib, os; print(manimlib.__path__[0])" 2>/dev/null || true)
fi

# ── WHITELIST ────────────────────────────────────────
echo "[WHITELIST]"

while IFS='|' read -r _ id path purpose priority; do
    id=$(echo "$id" | xargs)
    [[ -z "$id" || "$id" == "标识" ]] && continue
    [[ "$id" =~ ^-+$ ]] && continue  # 跳过 Markdown 表格分隔线

    path_expr=$(echo "$path" | sed -n 's/.*`\(.*\)` .*/\1/p')
    if [[ -z "$path_expr" ]]; then
        echo "  ~ $id: no path expression, skipping"
        SKIP=$((SKIP + 1))
        continue
    fi

    # 解析路径
    if [[ "$path_expr" == manimlib/* ]]; then
        if [[ -n "$MANIMLIB_ROOT" ]]; then
            resolved="$MANIMLIB_ROOT/${path_expr#manimlib/}"
        else
            echo "  ~ $id: manimlib not installed, skipping"
            SKIP=$((SKIP + 1))
            continue
        fi
    else
        # 项目内相对路径
        resolved="$PROJECT_ROOT/$path_expr"
    fi

    if [[ "$path_expr" == *"*"* ]]; then
        shopt -s nullglob
        matches=($resolved)
        shopt -u nullglob
        if [[ ${#matches[@]} -gt 0 ]]; then
            echo "  ✓ $id: $path_expr (${#matches[@]} matches)"
            PASS=$((PASS + 1))
        else
            if echo "$purpose" | grep -qi "TODO\|待创建"; then
                echo "  ○ $id: '$path_expr' (TODO, expected)"
                SKIP=$((SKIP + 1))
            else
                echo "  ✗ $id: '$path_expr' → no matches" >&2
                FAIL=$((FAIL + 1))
            fi
        fi
    elif [[ -e "$resolved" ]] || [[ -d "$resolved" ]]; then
        echo "  ✓ $id: $path_expr"
        PASS=$((PASS + 1))
    else
        if echo "$purpose" | grep -qi "TODO\|待创建"; then
            echo "  ○ $id: '$path_expr' (TODO, expected)"
            SKIP=$((SKIP + 1))
        else
            echo "  ✗ $id: '$path_expr' NOT FOUND" >&2
            FAIL=$((FAIL + 1))
        fi
    fi
done < <(extract_section "WHITELIST" "$SOURCEMAP")

# ── BLACKLIST ────────────────────────────────────────
echo ""
echo "[BLACKLIST]"

while IFS='|' read -r _ id path reason; do
    id=$(echo "$id" | xargs)
    [[ -z "$id" || "$id" == "标识" ]] && continue
    [[ "$id" =~ ^-+$ ]] && continue  # 跳过 Markdown 表格分隔线

    path_expr=$(echo "$path" | sed -n 's/.*`\(.*\)` .*/\1/p')
    if [[ -z "$path_expr" ]]; then
        echo "  ○ $id: import path (no file)"
        SKIP=$((SKIP + 1))
        continue
    fi

    if [[ "$path_expr" == manimlib/* ]]; then
        if [[ -n "$MANIMLIB_ROOT" ]]; then
            resolved="$MANIMLIB_ROOT/${path_expr#manimlib/}"
        else
            echo "  ~ $id: '$path_expr' (manimlib not installed)"
            SKIP=$((SKIP + 1))
            continue
        fi
    else
        resolved="$PROJECT_ROOT/$path_expr"
    fi

    if [[ "$path_expr" == *"*"* ]]; then
        shopt -s nullglob
        matches=($resolved)
        shopt -u nullglob
        if [[ ${#matches[@]} -gt 0 ]]; then
            echo "  ✓ $id: $path_expr (${#matches[@]} matches, correctly blacklisted)"
        else
            echo "  ~ $id: '$path_expr' not found (may be import path or removed)"
        fi
    elif [[ -e "$resolved" ]] || [[ -d "$resolved" ]]; then
        echo "  ✓ $id: $path_expr (exists, correctly blacklisted)"
    else
        echo "  ~ $id: '$path_expr' not found (may be import path or removed)"
    fi
    SKIP=$((SKIP + 1))
done < <(extract_section "BLACKLIST" "$SOURCEMAP")

# ── EXTENSION ────────────────────────────────────────
echo ""
echo "[EXTENSION]"

while IFS='|' read -r _ id desc status; do
    id=$(echo "$id" | xargs)
    [[ -z "$id" || "$id" == "标识" ]] && continue
    [[ "$id" =~ ^-+$ ]] && continue  # 跳过 Markdown 表格分隔线
    status=$(echo "$status" | xargs)
    echo "  · $id: [$status] $(echo "$desc" | xargs)"
    SKIP=$((SKIP + 1))
done < <(extract_section "EXTENSION" "$SOURCEMAP")

echo ""
echo "=== Validation complete ==="
echo "  PASS: $PASS  FAIL: $FAIL  SKIP: $SKIP"

if [[ $FAIL -gt 0 ]]; then
    echo "ACTION: Fix or remove the $FAIL invalid path(s)." >&2
    exit 1
fi
