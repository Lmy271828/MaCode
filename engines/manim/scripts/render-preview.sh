#!/usr/bin/env bash
set -euo pipefail

# engines/manim/scripts/render-preview.sh
# Render a single preview for a ManimCE scene.
# Expects manifest.json to already be patched with preview parameters.
#
# Usage: render-preview.sh <scene_dir> [output_mp4]

if [[ "${1:-}" == "--help" || "${1:-}" == "-h" ]]; then
    cat <<'EOF'
Usage: render-preview.sh <scene_dir> [output_mp4]

Render a preview for a ManimCE scene.
The manifest must already contain preview settings (low fps, small resolution).

Arguments:
  <scene_dir>   Scene directory containing manifest.json and scene.py
  [output_mp4]  Optional output path (default: .agent/tmp/{scene}/preview.mp4)
EOF
    exit 0
fi

SCENE_DIR="${1:-}"
if [[ -z "$SCENE_DIR" ]]; then
    echo "Usage: $0 <scene_dir> [output_mp4]" >&2
    exit 1
fi

SCENE_DIR="${SCENE_DIR%/}"
SCENE_NAME=$(basename "$SCENE_DIR")

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../../.." && pwd)"

OUTPUT_DIR="$PROJECT_ROOT/.agent/tmp/$SCENE_NAME"
mkdir -p "$OUTPUT_DIR"

PREVIEW_MP4="${2:-$OUTPUT_DIR/preview.mp4}"

# Ensure log directory exists
mkdir -p "$PROJECT_ROOT/.agent/log"
LOG_FILE="$PROJECT_ROOT/.agent/log/$(date +%Y%m%d_%H%M%S)_${SCENE_NAME}_preview.log"

echo "[render-preview] Rendering $SCENE_NAME..."
if bash "$PROJECT_ROOT/pipeline/render.sh" "$SCENE_DIR" >> "$LOG_FILE" 2>&1; then
    RAW_MP4="$OUTPUT_DIR/raw.mp4"
    FINAL_MP4="$OUTPUT_DIR/final.mp4"
    SRC_MP4=""

    if [[ -f "$RAW_MP4" ]]; then
        SRC_MP4="$RAW_MP4"
    elif [[ -f "$FINAL_MP4" ]]; then
        SRC_MP4="$FINAL_MP4"
    fi

    if [[ -n "$SRC_MP4" && -f "$SRC_MP4" ]]; then
        # Extract preview settings from manifest for preview.sh
        MANIFEST="$SCENE_DIR/manifest.json"
        PREVIEW_WIDTH=640
        PREVIEW_FPS=10
        if command -v jq >/dev/null 2>&1; then
            PREVIEW_WIDTH=$(jq -r '.resolution[0] // 640' "$MANIFEST" 2>/dev/null || echo "640")
            PREVIEW_FPS=$(jq -r '.fps // 10' "$MANIFEST" 2>/dev/null || echo "10")
        fi

        bash "$PROJECT_ROOT/pipeline/preview.sh" "$SRC_MP4" "$PREVIEW_MP4" "$PREVIEW_WIDTH" "$PREVIEW_FPS" >> "$LOG_FILE" 2>&1
        echo "[render-preview] Preview ready: $PREVIEW_MP4"
    else
        echo "[render-preview] Warning: no output video found after render" >&2
    fi
else
    echo "[render-preview] Render failed. Check log: $LOG_FILE" >&2
    exit 1
fi
