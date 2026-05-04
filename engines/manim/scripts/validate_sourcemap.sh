#!/usr/bin/env bash
set -euo pipefail

# engines/manim/scripts/validate_sourcemap.sh
# 验证 SOURCEMAP.md 中 WHITELIST/BLACKLIST 路径的真实性。
#
# 用法: validate_sourcemap.sh

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SOURCEMAP="$SCRIPT_DIR/../SOURCEMAP.md"

if [[ ! -f "$SOURCEMAP" ]]; then
    echo "FATAL: SOURCEMAP.md not found at $SOURCEMAP" >&2
    exit 1
fi

echo "=== Validating SOURCEMAP for: manim ==="
echo "  Source: $SOURCEMAP"
echo ""

PASS=0
FAIL=0
SKIP=0

# 提取指定 section 的表格行（在下一个 ## 之前截断）
extract_section() {
    local section="$1"
    local file="$2"
    awk "/^## ${section}/ {found=1; next} /^## / {if(found) exit} found && /^\\|/" "$file"
}

# ── WHITELIST ────────────────────────────────────────
echo "[WHITELIST]"

while IFS='|' read -r _ id path purpose priority; do
    id=$(echo "$id" | xargs)
    [[ -z "$id" || "$id" == "标识" ]] && continue

    path_expr=$(echo "$path" | sed -n 's/.*`\(.*\)`.*/\1/p')
    if [[ -z "$path_expr" ]]; then
        echo "  ~ $id: no path expression, skipping"
        SKIP=$((SKIP + 1))
        continue
    fi

    # eval 动态路径
    resolved=$(eval echo "$path_expr" 2>/dev/null) || true
    if [[ -z "$resolved" ]]; then
        echo "  ~ $id: eval empty for '$path_expr' (engine not installed?)"
        SKIP=$((SKIP + 1))
        continue
    fi

    if [[ -e "$resolved" ]] || [[ -d "$resolved" ]]; then
        echo "  ✓ $id: $resolved"
        PASS=$((PASS + 1))
    else
        # TODO 标记的路径允许不存在
        if echo "$purpose" | grep -qi "TODO\|待创建"; then
            echo "  ○ $id: '$path_expr' (TODO, expected)"
            SKIP=$((SKIP + 1))
        else
            echo "  ✗ $id: '$path_expr' → '$resolved' NOT FOUND" >&2
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

    path_expr=$(echo "$path" | sed -n 's/.*`\(.*\)`.*/\1/p')
    if [[ -z "$path_expr" ]]; then
        echo "  ○ $id: import path (no file to verify)"
        SKIP=$((SKIP + 1))
        continue
    fi

    resolved=$(eval echo "$path_expr" 2>/dev/null) || true
    if [[ -z "$resolved" ]]; then
        echo "  ○ $id: '$path_expr' (import path or not installed)"
        SKIP=$((SKIP + 1))
    elif [[ -e "$resolved" ]] || [[ -d "$resolved" ]]; then
        echo "  ✓ $id: $resolved (exists, correctly blacklisted)"
        SKIP=$((SKIP + 1))
    else
        echo "  ~ $id: '$path_expr' not found (may be import path or removed)"
        SKIP=$((SKIP + 1))
    fi
done < <(extract_section "BLACKLIST" "$SOURCEMAP")

# ── EXTENSION ────────────────────────────────────────
echo ""
echo "[EXTENSION]"

while IFS='|' read -r _ id desc status; do
    id=$(echo "$id" | xargs)
    [[ -z "$id" || "$id" == "标识" ]] && continue
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
