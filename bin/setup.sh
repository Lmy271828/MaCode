#!/usr/bin/env bash
set -euo pipefail

# bin/setup.sh
# 项目初始化：修复权限、创建目录、检查依赖、配置引擎环境。

if [[ "${1:-}" == "--help" || "${1:-}" == "-h" ]]; then
    cat <<'EOF'
Usage: setup.sh [--help]

Initialize MaCode project: fix permissions, create directories,
check dependencies, configure engine environments (Manim, ManimGL, Motion Canvas).
Run once after clone.
EOF
    exit 0
fi

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_ROOT"

echo "========================================"
echo "  MaCode Setup"
echo "========================================"
echo ""

# ── 合并初始化：基础设施 + 引擎环境 ───────────────────
echo "[Setup] Initializing MaCode project and engine environments..."
echo ""

# 1. 修复权限
echo "  [1/6] Fixing script permissions..."
chmod +x bin/* 2>/dev/null || true
chmod +x pipeline/* 2>/dev/null || true
for engine_dir in engines/*/; do
    chmod +x "$engine_dir"scripts/* 2>/dev/null || true
done
echo "        Done."

# 2. 创建目录
echo "  [2/6] Creating directory structure..."
mkdir -p .agent/tmp .agent/cache .agent/log .agent/context .agent/bin output
echo "        Done."

# 3. 检查核心依赖
echo "  [3/6] Checking core dependencies..."
MISSING=0
check_cmd() {
    if command -v "$1" >/dev/null 2>&1; then
        echo "        ✓ $1"
        return 0
    else
        echo "        ✗ $1 — NOT FOUND"
        return 1
    fi
}
check_cmd bash  || MISSING=$((MISSING + 1))
check_cmd git   || MISSING=$((MISSING + 1))
check_cmd ffmpeg || MISSING=$((MISSING + 1))
check_cmd ffprobe || MISSING=$((MISSING + 1))
if command -v python3 >/dev/null 2>&1; then
    echo "        ✓ python3"
else
    echo "        ✗ python3 — NOT FOUND (required by uv venv)"
    MISSING=$((MISSING + 1))
fi
if command -v node >/dev/null 2>&1; then
    echo "        ✓ node"
else
    echo "        ~ node — not found (only needed for motion_canvas)"
fi
if [[ $MISSING -gt 0 ]]; then
    echo ""
    echo "ERROR: $MISSING required core dependencies missing. Install them first."
    exit 1
fi
echo "        All core dependencies present."

# 4. 获取/安装 uv
echo "  [4/6] Setting up uv (Python package manager)..."
UV_BIN=""
if command -v uv >/dev/null 2>&1; then
    UV_BIN="uv"
    echo "        ✓ uv found: $($UV_BIN --version 2>/dev/null || echo 'unknown')"
elif [[ -x ".agent/bin/uv" ]]; then
    UV_BIN=".agent/bin/uv"
    echo "        ✓ uv found (cached): $($UV_BIN --version 2>/dev/null || echo 'unknown')"
else
    echo "        ~ uv not found, downloading standalone binary..."
    mkdir -p .agent/bin
    PLATFORM=$(uname -s)
    ARCH=$(uname -m)
    case "$PLATFORM" in
        Linux)  PLATFORM_SLUG="unknown-linux-gnu" ;;
        Darwin) PLATFORM_SLUG="apple-darwin" ;;
        *) echo "        ✗ Unsupported platform: $PLATFORM"; exit 1 ;;
    esac
    case "$ARCH" in
        x86_64)        ARCH_SLUG="x86_64" ;;
        aarch64|arm64) ARCH_SLUG="aarch64" ;;
        *) echo "        ✗ Unsupported architecture: $ARCH"; exit 1 ;;
    esac
    UV_URL="https://github.com/astral-sh/uv/releases/latest/download/uv-${ARCH_SLUG}-${PLATFORM_SLUG}"
    echo "        Downloading uv from GitHub releases..."
    if curl -Lfso .agent/bin/uv "$UV_URL"; then
        chmod +x .agent/bin/uv
        UV_BIN=".agent/bin/uv"
        echo "        ✓ uv downloaded: $($UV_BIN --version)"
    else
        echo "        ✗ Failed to download uv."
        echo "        Please install manually: https://docs.astral.sh/uv/getting-started/installation/"
        exit 1
    fi
fi

# Ensure .agent/bin is in PATH for subsequent tools
export PATH="$PROJECT_ROOT/.agent/bin:$PATH"

# 5. 配置 Manim（Python 引擎）
echo "  [5/8] Configuring ManimCE (Python engine)..."
if [[ ! -d ".venv" ]]; then
    echo "        Creating virtual environment with uv..."
    $UV_BIN venv .venv
fi
echo "        Installing Python dependencies..."
if [[ -f "requirements.txt" ]]; then
    $UV_BIN pip install -p .venv -r requirements.txt
else
    echo "        ~ requirements.txt not found, installing latest manim (unpinned)"
    $UV_BIN pip install -p .venv manim
fi
MANIM_VER=$(.venv/bin/python -c "import manim; print(manim.__version__)" 2>/dev/null || echo "installed")
echo "        ✓ ManimCE ready: v$MANIM_VER"

# 5b. 配置 ManimGL（交互式 Python 引擎）
echo "  [5b/8] Configuring ManimGL (interactive Python engine)..."
if [[ ! -d ".venv-manimgl" ]]; then
    echo "        Creating virtual environment with uv..."
    $UV_BIN venv .venv-manimgl
fi
echo "        Installing ManimGL..."
$UV_BIN pip install -p .venv-manimgl manimgl
MANIMGL_VER=$(.venv-manimgl/bin/python -c "import manimlib; print(manimlib.__version__)" 2>/dev/null || echo "installed")
echo "        ✓ ManimGL ready: v$MANIMGL_VER"

# 5c. 检测硬件并选择渲染后端
echo "  [5c/8] Detecting hardware and selecting render backend..."
if [[ -f "bin/detect-hardware.sh" ]]; then
    bash bin/detect-hardware.sh
    if [[ -f ".agent/hardware_profile.json" ]]; then
        echo "        ✓ Hardware profile written"
        bash bin/select-backend.sh --print
    else
        echo "        ⚠ Hardware detection failed (non-fatal)"
    fi
else
    echo "        ~ bin/detect-hardware.sh not found, skipping"
fi

# 6. 配置 Motion Canvas（Node.js 引擎）
echo "  [6/8] Configuring Motion Canvas (Node.js engine)..."
if [[ -f "package.json" ]]; then
    if [[ ! -d "node_modules" ]]; then
        echo "        Installing Node.js dependencies..."
        npm install
    else
        echo "        ✓ node_modules already present"
    fi
    echo "        ✓ Motion Canvas ready (via npx)"
else
    echo "        ~ package.json not found, skipping Motion Canvas setup"
fi

echo ""

# ── 7. 验证 SOURCEMAP 新鲜度 ────────────────────────
echo "  [7/8] Validating SOURCEMAP freshness..."

# 7a. 同步 SOURCEMAP JSON
if [[ -f "bin/sourcemap-sync.py" ]]; then
    echo "        Syncing SOURCEMAP to JSON..."
    if python3 bin/sourcemap-sync.py --all; then
        echo "        ✓ SOURCEMAP JSON synced"
    else
        echo "        ⚠ sourcemap-sync.py failed (non-fatal)" >&2
    fi
else
    echo "        ~ bin/sourcemap-sync.py not found, skipping JSON sync"
fi

# 7b. 验证 SOURCEMAP 路径
SOURCEMAP_WARN=0
for engine_dir in engines/*/; do
    engine_name=$(basename "$engine_dir")
    sourcemap="$engine_dir/SOURCEMAP.md"
    validate_script="$engine_dir/scripts/validate_sourcemap.sh"
    if [[ -f "$sourcemap" && -x "$validate_script" ]]; then
        echo "        Checking $engine_name..."
        if bash "$validate_script" >/dev/null 2>&1; then
            echo "        ✓ $engine_name SOURCEMAP valid"
        else
            echo "        ⚠ $engine_name SOURCEMAP has INVALID paths" >&2
            echo "          Run: bash $validate_script" >&2
            SOURCEMAP_WARN=$((SOURCEMAP_WARN + 1))
        fi
    fi
done
if [[ $SOURCEMAP_WARN -gt 0 ]]; then
    echo ""
    echo "WARNING: $SOURCEMAP_WARN engine(s) have outdated SOURCEMAPs." >&2
    echo "  The engine version may have changed since SOURCEMAP was last updated." >&2
    echo "  Run the validate scripts above and update engines/*/SOURCEMAP.md accordingly." >&2
fi
# ────────────────────────────────────────────────────

echo ""
echo "========================================"
echo "  Setup complete"
echo "========================================"
echo ""
echo "Quick start:"
echo "  bin/agent-shell                      # Enter agent environment"
echo "  macode status                        # View project status"
echo "  macode inspect --level P0            # Browse engine API"
echo "  python3 bin/sourcemap-sync.py --all  # Regenerate JSON after editing SOURCEMAP"
echo ""
echo "Engines:"
echo "  .venv/         → ManimCE  (batch rendering, final output)"
echo "  .venv-manimgl/ → ManimGL  (interactive preview, dev iteration)"
echo "  node_modules/  → Motion Canvas (browser HMR)"
echo ""
