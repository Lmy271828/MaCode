#!/usr/bin/env bash
set -euo pipefail

# bin/security-run.sh
# Thin orchestrator for all security checks.
# Runs checks in parallel, aggregates exit codes.
#
# Usage: security-run.sh <scene_dir> [--staged]
#   --staged  Only check files staged in git (for pre-commit)
#
# Design (Harness 2.0 four-questions):
#   Q1: Pure orchestration, no side effects
#   Q2: Each checker fails independently
#   Q3: Parallel execution via background jobs
#   Q4: Exit codes aggregated, no shared state

if [[ "${1:-}" == "--help" || "${1:-}" == "-h" ]]; then
    cat <<'EOF'
Usage: security-run.sh <scene_dir> [--staged]

Run all security checks on a scene directory.
Checks (parallel):
  - api-gate.py      Import/API blacklist
  - sandbox-check.py Dangerous Python calls
  - primitive-gate.py Low-level primitive writes
  - fs-guard.py      Filesystem boundary

Exit: 0 = all pass, 1 = any violation, 2 = argument error
EOF
    exit 0
fi

SCENE_DIR="${1:-}"
STAGED=false
if [[ "${2:-}" == "--staged" ]]; then
    STAGED=true
fi

if [[ -z "$SCENE_DIR" ]]; then
    echo "Usage: $0 <scene_dir> [--staged]" >&2
    exit 2
fi

SCENE_DIR="${SCENE_DIR%/}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

# Find scene source file and infer engine
SCENE_PY="$SCENE_DIR/scene.py"
SCENE_TSX="$SCENE_DIR/scene.tsx"
MANIFEST="$SCENE_DIR/manifest.json"

if [[ -f "$SCENE_PY" ]]; then
    SCENE_FILE="$SCENE_PY"
    # Infer engine: manifest.json takes precedence
    if [[ -f "$MANIFEST" ]]; then
        ENGINE="$(python3 -c "import json,sys; d=json.load(open('$MANIFEST')); print(d.get('engine','manim'))" 2>/dev/null || echo manim)"
    else
        ENGINE="manim"
    fi
elif [[ -f "$SCENE_TSX" ]]; then
    SCENE_FILE="$SCENE_TSX"
    ENGINE="motion_canvas"
else
    echo "Error: no scene.py or scene.tsx found in $SCENE_DIR" >&2
    exit 2
fi

SOURCEMAP_JSON="$PROJECT_ROOT/engines/$ENGINE/sourcemap.json"

# ── Run checks in parallel ──
RESULTS=()

# api-gate (import/API blacklist)
if [[ -f "$SOURCEMAP_JSON" ]]; then
    python3 "$SCRIPT_DIR/api-gate.py" "$SCENE_FILE" "$SOURCEMAP_JSON" --engine "$ENGINE" >/dev/null 2>&1 &
    PIDS=($!)
else
    PIDS=()
fi

# sandbox-check (dangerous calls)
python3 "$SCRIPT_DIR/sandbox-check.py" "$SCENE_FILE" >/dev/null 2>&1 &
PIDS+=("$!")

# primitive-gate (low-level primitives)
python3 "$SCRIPT_DIR/primitive-gate.py" "$SCENE_DIR" >/dev/null 2>&1 &
PIDS+=("$!")

# fs-guard (filesystem boundary)
python3 "$SCRIPT_DIR/fs-guard.py" "$SCENE_DIR" >/dev/null 2>&1 &
PIDS+=("$!")

# Wait and collect
FAILED=0
for pid in "${PIDS[@]}"; do
    if ! wait "$pid"; then
        FAILED=$((FAILED + 1))
    fi
done

if [[ "$FAILED" -gt 0 ]]; then
    echo ""
    echo "========================================"
    echo "  SECURITY_FAIL: $FAILED check(s) failed for $SCENE_DIR"
    echo "========================================"
    echo ""

    # Re-run failed checkers with --advise for LLM-friendly output
    # Use temp files to avoid subshell pipeline issues
    TMP_OUT=$(mktemp)

    if [[ -f "$SOURCEMAP_JSON" ]]; then
        python3 "$SCRIPT_DIR/api-gate.py" "$SCENE_FILE" "$SOURCEMAP_JSON" --engine "$ENGINE" >"$TMP_OUT" 2>&1 || true
        while IFS= read -r line || [[ -n "$line" ]]; do
            if [[ "$line" == "  -"* ]]; then
                violation="${line#  - }"
                python3 "$SCRIPT_DIR/security-advise.py" api-gate --location "$SCENE_FILE" "$violation" 2>/dev/null || true
            fi
        done < "$TMP_OUT"
    fi

    python3 "$SCRIPT_DIR/sandbox-check.py" "$SCENE_FILE" >"$TMP_OUT" 2>&1 || true
    while IFS= read -r line || [[ -n "$line" ]]; do
        if [[ "$line" == "  -"* ]]; then
            violation="${line#  - }"
            python3 "$SCRIPT_DIR/security-advise.py" sandbox --location "$SCENE_FILE" "$violation" 2>/dev/null || true
        fi
    done < "$TMP_OUT"

    python3 "$SCRIPT_DIR/primitive-gate.py" "$SCENE_DIR" >"$TMP_OUT" 2>&1 || true
    while IFS= read -r line || [[ -n "$line" ]]; do
        if [[ "$line" == "  -"* ]]; then
            violation="${line#  - }"
            python3 "$SCRIPT_DIR/security-advise.py" primitive --location "$SCENE_DIR" "$violation" 2>/dev/null || true
        fi
    done < "$TMP_OUT"

    python3 "$SCRIPT_DIR/fs-guard.py" "$SCENE_DIR" >"$TMP_OUT" 2>&1 || true
    while IFS= read -r line || [[ -n "$line" ]]; do
        if [[ "$line" == FS_VIOLATION:* ]]; then
            violation="${line#FS_VIOLATION: }"
            python3 "$SCRIPT_DIR/security-advise.py" fs --location "$SCENE_DIR" "$violation" 2>/dev/null || true
        fi
    done < "$TMP_OUT"

    rm -f "$TMP_OUT"

    echo ""
    echo "If you believe this is a false positive, run individual checkers for raw output:"
    echo "  api-gate.py $SCENE_FILE $SOURCEMAP_JSON --engine $ENGINE"
    echo "  sandbox-check.py $SCENE_FILE"
    echo "  primitive-gate.py $SCENE_DIR"
    echo "  fs-guard.py $SCENE_DIR"
    exit 1
fi

echo "SECURITY_OK: $SCENE_DIR"
exit 0
