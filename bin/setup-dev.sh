#!/usr/bin/env bash
set -euo pipefail

# bin/setup-dev.sh
# 开发版项目初始化：在用户版基础上安装测试/开发依赖，并验证测试环境。
# 适用于开发者、CI、以及需要运行测试套件的 Host Agent。

if [[ "${1:-}" == "--help" || "${1:-}" == "-h" ]]; then
    cat <<'EOF'
Usage: setup-dev.sh [--help] [--skip-tests]

Initialize MaCode project (DEVELOPMENT edition):
  1. Run bin/setup.sh (user-level initialization)
  2. Install Python dev dependencies (pytest, ruff)
  3. Verify test tooling and run smoke tests

Options:
  --skip-tests   Skip test execution (install only)

For end-users who only need to render scenes, use: bin/setup.sh
EOF
    exit 0
fi

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_ROOT"

SKIP_TESTS=0
for arg in "$@"; do
    if [[ "$arg" == "--skip-tests" ]]; then
        SKIP_TESTS=1
        break
    fi
done

echo "========================================"
echo "  MaCode Setup (Development Edition)"
echo "========================================"
echo ""

# ── Step 1: User-level setup ────────────────────────
echo "[dev] Running user-level setup..."
if [[ -f "bin/setup.sh" ]]; then
    bash bin/setup.sh
else
    echo "ERROR: bin/setup.sh not found." >&2
    exit 1
fi

# ── Step 2: Python dev dependencies ─────────────────
echo ""
echo "[dev] Installing Python development dependencies..."
UV_BIN=""
if command -v uv >/dev/null 2>&1; then
    UV_BIN="uv"
elif [[ -x ".agent/bin/uv" ]]; then
    UV_BIN=".agent/bin/uv"
else
    echo "ERROR: uv not found. Please run bin/setup.sh first." >&2
    exit 1
fi

if [[ -f "requirements-dev.txt" ]]; then
    $UV_BIN pip install -p .venv -r requirements-dev.txt
    echo "        ✓ Dev dependencies installed"
else
    echo "        ~ requirements-dev.txt not found, skipping"
fi

# ── Step 3: Verify tooling ──────────────────────────
echo ""
echo "[dev] Verifying development tooling..."
DEV_MISSING=0

check_tool() {
    local cmd="$1"
    local name="$2"
    if command -v "$cmd" >/dev/null 2>&1; then
        echo "        ✓ $name"
        return 0
    else
        echo "        ✗ $name — NOT FOUND"
        return 1
    fi
}

# Python test framework
if .venv/bin/python -m pytest --version >/dev/null 2>&1; then
    echo "        ✓ pytest ($(.venv/bin/python -m pytest --version | head -1))"
else
    echo "        ✗ pytest — NOT FOUND"
    DEV_MISSING=$((DEV_MISSING + 1))
fi

# Linter
if .venv/bin/python -m ruff --version >/dev/null 2>&1; then
    echo "        ✓ ruff ($(.venv/bin/python -m ruff --version))"
else
    echo "        ✗ ruff — NOT FOUND"
    DEV_MISSING=$((DEV_MISSING + 1))
fi

# Node test runner (playwright is a runtime dep for MC, but good to verify)
if npx playwright --version >/dev/null 2>&1; then
    echo "        ✓ playwright ($(npx playwright --version))"
else
    echo "        ~ playwright — not available (motion_canvas tests will skip)"
fi

if [[ $DEV_MISSING -gt 0 ]]; then
    echo ""
    echo "WARNING: $DEV_MISSING dev tool(s) missing. Some checks/tests may fail." >&2
fi

# ── Step 4: Run smoke tests ─────────────────────────
if [[ $SKIP_TESTS -eq 0 ]]; then
    echo ""
    echo "[dev] Running smoke tests..."
    SMOKE_OK=0
    SMOKE_TOTAL=0

    run_smoke() {
        local script="$1"
        local name="$2"
        SMOKE_TOTAL=$((SMOKE_TOTAL + 1))
        echo "        Running $name..."
        if bash "$script" >/dev/null 2>&1; then
            echo "        ✓ $name passed"
            SMOKE_OK=$((SMOKE_OK + 1))
        else
            echo "        ✗ $name failed"
        fi
    }

    if [[ -f "tests/smoke/test_render_manim.sh" ]]; then
        run_smoke "tests/smoke/test_render_manim.sh" "smoke/render_manim"
    fi
    if [[ -f "tests/smoke/test_render_manimgl.sh" ]]; then
        run_smoke "tests/smoke/test_render_manimgl.sh" "smoke/render_manimgl"
    fi
    if [[ -f "tests/smoke/test_composite.sh" ]]; then
        run_smoke "tests/smoke/test_composite.sh" "smoke/composite"
    fi
    if [[ -f "tests/smoke/test_cache_hit.sh" ]]; then
        run_smoke "tests/smoke/test_cache_hit.sh" "smoke/cache_hit"
    fi

    echo ""
    echo "        Smoke result: $SMOKE_OK/$SMOKE_TOTAL passed"

    # Run unit tests (quick subset)
    echo ""
    echo "[dev] Running unit tests..."
    if .venv/bin/python -m pytest tests/unit/ -q --tb=short 2>/dev/null; then
        echo "        ✓ All unit tests passed"
    else
        echo "        ⚠ Some unit tests failed (see output above)"
    fi
else
    echo ""
    echo "[dev] --skip-tests specified; skipping test execution."
fi

# ── Step 5: Git hooks ───────────────────────────────
echo ""
echo "[dev] Installing Git hooks..."
if [[ -f "bin/install-hooks.sh" ]]; then
    bash bin/install-hooks.sh
else
    echo "        ~ bin/install-hooks.sh not found, skipping"
fi

echo ""
echo "========================================"
echo "  Dev Setup complete"
echo "========================================"
echo ""
echo "Development commands:"
echo "  macode test --all                    # Run all tests (unit + smoke + integration)"
echo "  macode test --lint                   # Run ruff lint"
echo "  .venv/bin/python -m pytest tests/unit/ -v   # Run unit tests verbosely"
echo "  bash tests/smoke/runner.sh           # Run all smoke tests"
echo "  bash tests/integration/runner.sh     # Run integration tests"
echo ""
echo "Quality gates (run before commit):"
echo "  ruff check bin/ pipeline/ engines/ tests/"
echo "  bin/api-gate.py scenes/01_test/scene.py engines/manim/sourcemap.json --engine manim"
echo ""
