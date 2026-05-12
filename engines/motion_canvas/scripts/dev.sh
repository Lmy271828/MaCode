#!/usr/bin/env bash
set -euo pipefail

# engines/motion_canvas/scripts/dev.sh
# Motion Canvas dev mode: Vite dev server + optional snapshot/watch.
#
# Usage: dev.sh <scene_dir> [--snapshot [time]] [--watch] [--port <n>]

# ── Help check (any position) ──
for _arg in "$@"; do
    if [[ "$_arg" == "--help" || "$_arg" == "-h" ]]; then
        cat <<'EOF'
Usage: dev.sh <scene_dir> [--snapshot [time]] [--watch] [--port <n>]

Motion Canvas dev mode.

Arguments:
  <scene_dir>      Scene directory, e.g. scenes/01_test_mc/
  --snapshot [t]   Capture a single frame at time t (default: 0)
  --watch          Watch scene.tsx and auto-snapshot on change
  --port <n>       Dev server port (default: 4567)

Examples:
  dev.sh scenes/01_test_mc
  dev.sh scenes/01_test_mc --snapshot 2.5
  dev.sh scenes/01_test_mc --watch --port 3000
EOF
        exit 0
    fi
done

# ── Parse args ──
SCENE_DIR=""
DO_SNAPSHOT=false
SNAPSHOT_TIME="0"
DO_WATCH=false
DEV_PORT=4567

while [[ $# -gt 0 ]]; do
    case "$1" in
        --snapshot)
            DO_SNAPSHOT=true
            if [[ -n "${2:-}" && "${2:0:1}" != "-" ]]; then
                SNAPSHOT_TIME="$2"
                shift 2
            else
                SNAPSHOT_TIME="0"
                shift
            fi
            ;;
        --watch)
            DO_WATCH=true
            shift
            ;;
        --port)
            DEV_PORT="${2:-4567}"
            shift 2
            ;;
        -*)
            echo "Unknown option: $1" >&2
            echo "Usage: $0 <scene_dir> [--snapshot [time]] [--watch] [--port <n>]" >&2
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
    echo "Usage: $0 <scene_dir> [--snapshot [time]] [--watch] [--port <n>]" >&2
    exit 1
fi

SCENE_DIR="${SCENE_DIR%/}"
SCENE_TSX="$SCENE_DIR/scene.tsx"
MANIFEST="$SCENE_DIR/manifest.json"
SCENE_NAME=$(basename "$SCENE_DIR")

if [[ ! -f "$SCENE_TSX" ]]; then
    echo "Error: scene.tsx not found in $SCENE_DIR" >&2
    exit 1
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../../.." && pwd)"

if [[ ! -d "$PROJECT_ROOT/node_modules" ]]; then
    echo "Error: node_modules not found. Run 'bash bin/setup.sh' first." >&2
    exit 1
fi

# ── Read manifest params ──
read -r MC_FPS MC_WIDTH MC_HEIGHT <<< "$(python3 -c "
import json
d = json.load(open('$MANIFEST'))
res = d.get('resolution', [1920, 1080])
print(d.get('fps', 30), res[0], res[1])
" 2>/dev/null || echo "30 1920 1080")"

TMP_DIR="$PROJECT_ROOT/.agent/tmp/$SCENE_NAME"
mkdir -p "$TMP_DIR"

# ── Snapshot mode ──
if $DO_SNAPSHOT; then
    PREVIEW_DIR="$TMP_DIR/dev_preview"
    mkdir -p "$PREVIEW_DIR"
    echo "[motion_canvas] Capturing snapshot @ ${SNAPSHOT_TIME}s ..."
    node "$PROJECT_ROOT/engines/motion_canvas/scripts/snapshot.mjs" \
        "$SCENE_TSX" \
        "$PREVIEW_DIR/latest.png" \
        "$SNAPSHOT_TIME" \
        "$MC_FPS" \
        "$MC_WIDTH" \
        "$MC_HEIGHT"
    exit 0
fi

# ── Watch mode ──
if $DO_WATCH; then
    # Start persistent dev server (serve.mjs detaches Vite and exits)
    node "$PROJECT_ROOT/engines/motion_canvas/scripts/serve.mjs" "$SCENE_DIR" "$DEV_PORT" >/dev/null 2>&1
    sleep 2

    ACTUAL_PORT="$DEV_PORT"
    if [[ -f "$TMP_DIR/dev.port" ]]; then
        ACTUAL_PORT=$(cat "$TMP_DIR/dev.port")
    fi

    VITE_PID=""
    if [[ -f "$TMP_DIR/dev.pid" ]]; then
        VITE_PID=$(cat "$TMP_DIR/dev.pid")
    fi

    echo "[motion_canvas] Dev server on port $ACTUAL_PORT (PID ${VITE_PID:-?})"
    echo "[motion_canvas] Watching $SCENE_TSX for changes..."
    echo "[motion_canvas] Press Ctrl+C to stop."

    PREVIEW_DIR="$TMP_DIR/dev_preview"
    mkdir -p "$PREVIEW_DIR"
    LAST_MTIME=""

    cleanup_watch() {
        echo ""
        echo "[motion_canvas] Stopping dev server..."
        node "$PROJECT_ROOT/engines/motion_canvas/scripts/stop.mjs" "$SCENE_DIR" >/dev/null 2>&1 || true
        exit 0
    }
    trap cleanup_watch INT TERM EXIT

    while true; do
        CURRENT_MTIME=$(stat -c %Y "$SCENE_TSX" 2>/dev/null || echo "0")
        if [[ "$CURRENT_MTIME" != "$LAST_MTIME" && -n "$LAST_MTIME" ]]; then
            echo "[motion_canvas] File changed: $SCENE_TSX"
            echo "[motion_canvas] Capturing preview snapshot..."
            node "$PROJECT_ROOT/engines/motion_canvas/scripts/snapshot.mjs" \
                "$SCENE_TSX" \
                "$PREVIEW_DIR/latest.png" \
                "0" \
                "$MC_FPS" \
                "$MC_WIDTH" \
                "$MC_HEIGHT" 2>&1 | grep '^\[snapshot\]'
        fi
        LAST_MTIME="$CURRENT_MTIME"
        sleep 1
    done
fi

# ── Default mode: start dev server and keep foreground ──
node "$PROJECT_ROOT/engines/motion_canvas/scripts/serve.mjs" "$SCENE_DIR" "$DEV_PORT"

sleep 2

ACTUAL_PORT="$DEV_PORT"
if [[ -f "$TMP_DIR/dev.port" ]]; then
    ACTUAL_PORT=$(cat "$TMP_DIR/dev.port")
fi
VITE_PID=""
if [[ -f "$TMP_DIR/dev.pid" ]]; then
    VITE_PID=$(cat "$TMP_DIR/dev.pid")
fi

echo "[motion_canvas] Dev server running on http://localhost:$ACTUAL_PORT"
[[ -n "$VITE_PID" ]] && echo "[motion_canvas] PID: $VITE_PID"
echo "[motion_canvas] Press Ctrl+C to stop."

cleanup_default() {
    echo ""
    echo "[motion_canvas] Stopping dev server..."
    node "$PROJECT_ROOT/engines/motion_canvas/scripts/stop.mjs" "$SCENE_DIR" >/dev/null 2>&1 || true
    exit 0
}
trap cleanup_default INT TERM EXIT

# Keep shell alive until interrupted
while true; do sleep 1; done
