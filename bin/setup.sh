#!/usr/bin/env bash
set -euo pipefail

# bin/setup.sh
# 项目初始化：修复权限、创建必要目录、验证依赖、配置 API。
# clone 后运行一次即可。

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_ROOT"

echo "========================================"
echo "  MaCode Setup"
echo "========================================"
echo ""

# ── 1. 修复脚本权限 ──────────────────────────────────
echo "[1/5] Fixing script permissions..."
chmod +x bin/* 2>/dev/null || true
chmod +x pipeline/* 2>/dev/null || true
for engine_dir in engines/*/; do
    chmod +x "$engine_dir"scripts/* 2>/dev/null || true
done
echo "  Done."
echo ""

# ── 2. 创建必要目录 ──────────────────────────────────
echo "[2/5] Creating directory structure..."
mkdir -p .agent/tmp
mkdir -p .agent/cache
mkdir -p .agent/log
mkdir -p .agent/context
mkdir -p output
echo "  Done."
echo ""

# ── 3. 依赖检查 ──────────────────────────────────────
echo "[3/5] Checking dependencies..."

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
if command -v python3 >/dev/null 2>&1 || command -v python >/dev/null 2>&1; then
    echo "  ✓ python"
else
    echo "  ✗ python — NOT FOUND (manim requires Python)"
    MISSING=$((MISSING + 1))
fi
if command -v node >/dev/null 2>&1; then
    echo "  ✓ node"
else
    echo "  ~ node — not found (only needed for motion_canvas)"
fi
check_cmd jq || echo "    (optional, faster JSON parsing)"
check_cmd yq || echo "    (optional, YAML parsing)"
echo ""

# ── 4. 交互式 API 配置 ───────────────────────────────
echo "[4/5] Configure Anthropic-compatible API..."

SETTINGS_FILE=".macode/settings.json"

# 如果已存在，询问是否重新配置
if [[ -f "$SETTINGS_FILE" ]]; then
    echo ""
    echo "  Existing config found:"
    if command -v python3 >/dev/null 2>&1; then
        python3 -c "
import json
with open('$SETTINGS_FILE') as f:
    c = json.load(f)
print(f\"    Provider : {c.get('provider', '?')}\")
print(f\"    Base URL : {c.get('env',{}).get('ANTHROPIC_BASE_URL','?')}\")
print(f\"    Model    : {c.get('model', '?')}\")
key = c.get('env',{}).get('ANTHROPIC_API_KEY','')
if key:
    print(f\"    API Key  : {key[:12]}...{key[-8:]}\")
" 2>/dev/null || true
    fi
    echo ""
    read -r -p "  Reconfigure? [y/N]: " RECONFIGURE
    if [[ ! "$RECONFIGURE" =~ ^[Yy]$ ]]; then
        echo "  Keeping existing config."
        echo ""
        SKIP_API=1
    fi
fi

if [[ "${SKIP_API:-0}" -eq 0 ]]; then
    echo ""
    echo "  Choose an API provider:"
    echo ""
    echo "    1) Kimi For Coding       (https://api.kimi.com/coding)"
    echo "    2) Anthropic (Official)  (https://api.anthropic.com)"
    echo "    3) OpenRouter            (https://openrouter.ai/api/v1)"
    echo "    4) Custom (enter manually)"
    echo ""

    while true; do
        read -r -p "  Your choice [1-4]: " CHOICE
        case "$CHOICE" in
            1)
                PROVIDER="kimi-for-coding"
                BASE_URL="https://api.kimi.com/coding"
                DEFAULT_MODEL="kimi-for-coding"
                break
                ;;
            2)
                PROVIDER="anthropic"
                BASE_URL="https://api.anthropic.com"
                DEFAULT_MODEL="claude-sonnet-4-6"
                break
                ;;
            3)
                PROVIDER="openrouter"
                BASE_URL="https://openrouter.ai/api/v1"
                DEFAULT_MODEL="anthropic/claude-sonnet-4-6"
                break
                ;;
            4)
                read -r -p "  Provider name: " PROVIDER
                read -r -p "  Base URL: " BASE_URL
                DEFAULT_MODEL=""
                break
                ;;
            *)
                echo "  Please enter 1, 2, 3, or 4."
                ;;
        esac
    done

    echo ""

    # Model ID
    if [[ -n "$DEFAULT_MODEL" ]]; then
        read -r -p "  Model ID [$DEFAULT_MODEL]: " MODEL
        MODEL="${MODEL:-$DEFAULT_MODEL}"
    else
        read -r -p "  Model ID: " MODEL
    fi

    # API Key（隐藏输入）
    echo -n "  API Key (input hidden): "
    read -r -s API_KEY
    echo ""

    # 写入配置
    mkdir -p .macode
    cat > "$SETTINGS_FILE" << JSONEOF
{
  "provider": "${PROVIDER}",
  "env": {
    "ANTHROPIC_API_KEY": "${API_KEY}",
    "ANTHROPIC_BASE_URL": "${BASE_URL}"
  },
  "model": "${MODEL}"
}
JSONEOF

    echo ""
    echo "  Config saved: $SETTINGS_FILE"
fi

echo ""

# ── 5. 项目配置检查 ──────────────────────────────────
echo "[5/5] Checking project configuration..."

if [[ -f "project.yaml" ]]; then
    echo "  ✓ project.yaml"
else
    echo "  ✗ project.yaml not found"
    MISSING=$((MISSING + 1))
fi

echo ""

# ── 完成 ──────────────────────────────────────────────
echo "========================================"
echo "  Setup complete"
echo "========================================"
echo ""

if [[ $MISSING -gt 0 ]]; then
    echo "WARNING: $MISSING required dependencies missing."
    echo "Install them before rendering scenes."
    echo ""
    exit 1
else
    echo "All required dependencies present."
    echo ""
    echo "Quick start:"
    echo "  bin/agent-shell              # Enter agent environment"
    echo "  macode status                 # View project status"
    echo "  macode inspect --level P0     # Browse engine API"
    echo ""
fi
