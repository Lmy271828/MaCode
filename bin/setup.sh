#!/usr/bin/env bash
set -euo pipefail

# bin/setup.sh
# 项目初始化：修复权限、创建必要目录、验证依赖。
# clone 后运行一次即可。

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_ROOT"

echo "=== MaCode Setup ==="
echo ""

# ── 1. 修复脚本权限 ──────────────────────────────────
echo "[1/4] Fixing script permissions..."
chmod +x bin/* 2>/dev/null || true
chmod +x pipeline/* 2>/dev/null || true
for engine_dir in engines/*/; do
    chmod +x "$engine_dir"scripts/* 2>/dev/null || true
done
echo "  Done."

# ── 2. 创建必要目录 ──────────────────────────────────
echo "[2/4] Creating directory structure..."
mkdir -p .agent/tmp
mkdir -p .agent/cache
mkdir -p .agent/log
mkdir -p .agent/context
mkdir -p output
echo "  Done."

# ── 3. 依赖检查 ──────────────────────────────────────
echo "[3/4] Checking dependencies..."

check_cmd() {
    if command -v "$1" >/dev/null 2>&1; then
        echo "  ✓ $1"
        return 0
    else
        echo "  ✗ $1 — NOT FOUND"
        return 1
    fi
}

MISSING=0
check_cmd bash || MISSING=$((MISSING + 1))
check_cmd git || MISSING=$((MISSING + 1))
check_cmd ffmpeg || MISSING=$((MISSING + 1))
check_cmd ffprobe || MISSING=$((MISSING + 1))

# Python (manim)
if command -v python3 >/dev/null 2>&1 || command -v python >/dev/null 2>&1; then
    echo "  ✓ python"
else
    echo "  ✗ python — NOT FOUND (manim requires Python)"
    MISSING=$((MISSING + 1))
fi

# Node.js (motion_canvas)
if command -v node >/dev/null 2>&1; then
    echo "  ✓ node"
else
    echo "  ~ node — not found (only needed for motion_canvas engine)"
fi

# Optional: jq / yq
check_cmd jq || echo "    (optional, for faster JSON parsing)"
check_cmd yq || echo "    (optional, for YAML parsing)"

# ── 4. 配置检查 ──────────────────────────────────────
echo "[4/4] Checking configuration..."

if [[ -f ".macode/settings.json" ]]; then
    echo "  ✓ .macode/settings.json"
else
    echo "  ! .macode/settings.json not found — Agent API calls will fail"
    echo "    Create it with: cp .macode/settings.example.json .macode/settings.json"
fi

if [[ -f "project.yaml" ]]; then
    echo "  ✓ project.yaml"
else
    echo "  ✗ project.yaml not found"
    MISSING=$((MISSING + 1))
fi

echo ""
echo "=== Setup complete ==="
if [[ $MISSING -gt 0 ]]; then
    echo "WARNING: $MISSING required dependencies missing."
    echo "Install them before rendering scenes."
    exit 1
else
    echo "All required dependencies present."
    echo ""
    echo "Quick start:"
    echo "  bin/agent-shell          # Enter agent environment"
    echo "  macode status             # View project status"
    echo "  macode inspect --level P0 # Browse engine API"
fi
