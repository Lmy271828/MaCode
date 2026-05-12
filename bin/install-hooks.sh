#!/usr/bin/env bash
set -euo pipefail

# bin/install-hooks.sh
# Install tracked git hook templates from .githooks/ into .git/hooks/.
# Idempotent: safe to run multiple times.
#
# Usage:
#   install-hooks.sh [--check]
#     --check   Verify hooks are installed and up-to-date (exit 0/1)

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
SOURCE_DIR="$PROJECT_ROOT/.githooks"
TARGET_DIR="$PROJECT_ROOT/.git/hooks"

CHECK_MODE=false
if [[ "${1:-}" == "--check" ]]; then
    CHECK_MODE=true
fi

if [[ ! -d "$TARGET_DIR" ]]; then
    echo "[install-hooks] No .git/hooks directory found. Is this a git repository?" >&2
    exit 1
fi

if [[ ! -d "$SOURCE_DIR" ]]; then
    echo "[install-hooks] No .githooks/ directory found. Nothing to install." >&2
    exit 1
fi

MISMATCH=0
INSTALLED=0

for hook in "$SOURCE_DIR"/*; do
    [[ -f "$hook" ]] || continue
    name=$(basename "$hook")
    target="$TARGET_DIR/$name"

    if $CHECK_MODE; then
        if [[ ! -f "$target" ]]; then
            echo "  ✗ $name: not installed"
            MISMATCH=$((MISMATCH + 1))
        elif ! diff -q "$hook" "$target" >/dev/null 2>&1; then
            echo "  ✗ $name: out of date (run install-hooks.sh to update)"
            MISMATCH=$((MISMATCH + 1))
        else
            echo "  ✓ $name: up to date"
        fi
        continue
    fi

    # Install / update
    if [[ ! -f "$target" ]] || ! diff -q "$hook" "$target" >/dev/null 2>&1; then
        cp "$hook" "$target"
        chmod +x "$target"
        echo "[install-hooks] $name → .git/hooks/"
        INSTALLED=$((INSTALLED + 1))
    fi
done

if $CHECK_MODE; then
    if [[ "$MISMATCH" -gt 0 ]]; then
        echo "[install-hooks] $MISMATCH hook(s) need attention."
        exit 1
    else
        echo "[install-hooks] All hooks up to date."
        exit 0
    fi
fi

if [[ "$INSTALLED" -gt 0 ]]; then
    echo "[install-hooks] $INSTALLED hook(s) installed/updated."
else
    echo "[install-hooks] All hooks already up to date."
fi
