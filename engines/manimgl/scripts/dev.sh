#!/usr/bin/env bash
set -euo pipefail

# engines/manimgl/scripts/dev.sh
# Launch ManimGL interactive preview with auto-reload.
#
# ManimGL is an interactive engine with built-in hot-reload (--autoreload).
# This script handles: env setup, signal checks, argument assembly.
#
# Usage: dev.sh <scene_dir> [--segment <seg_id>]

if [[ "${1:-}" == "--help" || "${1:-}" == "-h" ]]; then
    cat <<'EOF'
Usage: dev.sh <scene_dir> [--segment <seg_id>]

Launch ManimGL interactive preview.

Arguments:
  <scene_dir>     Scene directory, e.g. scenes/01_test/
  --segment <id>  Jump to segment (requires animation_index in manifest)

Notes:
  ManimGL auto-reloads on file changes. Use arrow keys / space to navigate.

Examples:
  dev.sh scenes/01_test
  dev.sh scenes/01_test --segment intro
EOF
    exit 0
fi

# ── Parse args ──
SCENE_DIR=""
SEG_ID=""

while [[ $# -gt 0 ]]; do
    case "$1" in
        --segment)
            SEG_ID="${2:-}"
            shift 2
            ;;
        -*)
            echo "Unknown option: $1" >&2
            echo "Usage: $0 <scene_dir> [--segment <seg_id>]" >&2
            exit 1
            ;;
        *)
            if [[ -z "$SCENE_DIR" ]]; then
                SCENE_DIR="$1"
            else
                echo "Unknown argument: $1" >&2
                exit 1
            fi
            shift
            ;;
    esac
done

if [[ -z "$SCENE_DIR" ]]; then
    echo "Usage: $0 <scene_dir> [--segment <seg_id>]" >&2
    exit 1
fi

SCENE_DIR="${SCENE_DIR%/}"
SCENE_PY="$SCENE_DIR/scene.py"
MANIFEST="$SCENE_DIR/manifest.json"
SCENE_NAME=$(basename "$SCENE_DIR")

if [[ ! -f "$SCENE_PY" ]]; then
    echo "Error: scene.py not found in $SCENE_DIR" >&2
    exit 1
fi

# ── Environment ──
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../../.." && pwd)"
VENV_PYTHON="$PROJECT_ROOT/.venv-manimgl/bin/python"

if [[ ! -x "$VENV_PYTHON" ]]; then
    echo "Error: ManimGL not installed. Run: bash bin/setup.sh" >&2
    exit 1
fi

ENGINE_SRC="$PROJECT_ROOT/engines/manimgl/src"
export PYTHONPATH="${ENGINE_SRC}${PYTHONPATH:+:$PYTHONPATH}"

# ── Signal check (pre-launch only) ──
if [[ -f "$PROJECT_ROOT/bin/signal-check.py" ]]; then
    ABORT=$("$VENV_PYTHON" "$PROJECT_ROOT/bin/signal-check.py" --scene "$SCENE_NAME" 2>/dev/null \
        | "$VENV_PYTHON" -c "
import json, sys
d = json.load(sys.stdin)
print(d.get('scenes', {}).get('$SCENE_NAME', {}).get('abort',
      d.get('global', {}).get('abort', False)))
" 2>/dev/null || echo "False")

    if [[ "$ABORT" == "True" || "$ABORT" == "true" ]]; then
        echo "[manimgl dev] ABORT signal active. Exiting." >&2
        exit 0
    fi
fi

# ── Assemble launch args ──
ARGS=(--autoreload)

# Resolution / quality
if [[ -f "$MANIFEST" ]]; then
    read -r WIDTH HEIGHT FPS <<< "$("$VENV_PYTHON" -c "
import json
d = json.load(open('$MANIFEST'))
res = d.get('resolution', [1920, 1080])
print(res[0], res[1], d.get('fps', 30))
" 2>/dev/null || echo "1920 1080 30")"

    if [[ "$WIDTH" -le 854 && "$HEIGHT" -le 480 ]]; then
        ARGS+=(-l)
    elif [[ "$WIDTH" -le 1280 && "$HEIGHT" -le 720 ]]; then
        ARGS+=(-m)
    elif [[ "$WIDTH" -le 1920 && "$HEIGHT" -le 1080 ]]; then
        ARGS+=(--hd)
    elif [[ "$WIDTH" -le 3840 && "$HEIGHT" -le 2160 ]]; then
        ARGS+=(--uhd)
    else
        ARGS+=(-r "${WIDTH}x${HEIGHT}")
    fi

    ARGS+=(--fps "$FPS")
fi

# Segment seek (animation index only; ManimGL has no time-seek)
if [[ -n "$SEG_ID" ]]; then
    ANIM_INDEX=""
    LOOKUP_RESULT=""
    if [[ -f "$MANIFEST" ]]; then
        LOOKUP_RESULT=$("$VENV_PYTHON" -c "
import json
try:
    segments = json.load(open('$MANIFEST')).get('segments', [])
    for seg in segments:
        if seg.get('id') == '$SEG_ID':
            idx = seg.get('animation_index')
            if idx is None:
                print('MISSING_INDEX')
            else:
                print(idx)
            break
    else:
        print('NOT_FOUND')
except Exception as e:
    print('ERROR:', e)
" 2>/dev/null || true)
    fi

    if [[ "$LOOKUP_RESULT" == "NOT_FOUND" ]]; then
        available=$("$VENV_PYTHON" -c "
import json
try:
    ids = [s.get('id','?') for s in json.load(open('$MANIFEST')).get('segments', [])]
    print(', '.join(ids) if ids else '(none)')
except:
    print('(unknown)')
" 2>/dev/null || true)
        echo "[manimgl dev] Error: segment '$SEG_ID' not found in manifest." >&2
        echo "[manimgl dev]        Available segments: $available" >&2
        echo "[manimgl dev]        Starting from beginning. Use arrow keys to navigate."
    elif [[ "$LOOKUP_RESULT" == "MISSING_INDEX" ]]; then
        echo "[manimgl dev] Warning: segment '$SEG_ID' exists but has no animation_index."
        echo "[manimgl dev]          Starting from beginning. Use arrow keys to navigate."
        echo "[manimgl dev]          To fix, add 'animation_index': N to the segment in manifest.json."
    elif [[ -n "$LOOKUP_RESULT" && "$LOOKUP_RESULT" != "ERROR"* ]]; then
        ANIM_INDEX="$LOOKUP_RESULT"
        ARGS+=(-n "$ANIM_INDEX")
        echo "[manimgl dev] Starting at animation $ANIM_INDEX (segment '$SEG_ID')"
    else
        echo "[manimgl dev] Warning: could not resolve segment '$SEG_ID'."
        echo "[manimgl dev]          Starting from beginning. Use arrow keys to navigate."
    fi
fi

# ── Launch ──
echo "[manimgl dev] Scene: $SCENE_NAME"
echo "[manimgl dev] Launching: $SCENE_PY"
echo "[manimgl dev] Args: ${ARGS[*]}"
echo "[manimgl dev] Press 'q' or close window to exit. Auto-reload enabled."

cd "$PROJECT_ROOT"
exec "$VENV_PYTHON" -m manimlib "$SCENE_PY" "${ARGS[@]}"
