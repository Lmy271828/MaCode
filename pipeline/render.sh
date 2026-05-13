#!/usr/bin/env bash
set -euo pipefail

# pipeline/render.sh
# Thin dispatcher: reads scene manifest and routes to the appropriate renderer.
# Preserves the CLI contract: render.sh <scene_dir> [--json]

if [[ "${1:-}" == "--help" || "${1:-}" == "-h" ]]; then
    SCRIPT_NAME=$(basename "$0")
    cat <<EOF
Usage: $SCRIPT_NAME [--json] <scene_dir>

Render a scene directory by reading manifest.json and invoking the engine.

Arguments:
  <scene_dir>  Scene directory containing manifest.json and scene file
  --json       Output rendering result as JSON to stdout

Examples:
  $SCRIPT_NAME scenes/01_test
  $SCRIPT_NAME --json scenes/01_test
EOF
    exit 0
fi

# ── Parameter parsing ─────────────────────────────────
JSON_OUTPUT=false
SCENE_DIR=""
EXTRA_ARGS=()

for arg in "$@"; do
    if [[ "$arg" == "--json" ]]; then
        JSON_OUTPUT=true
    elif [[ -z "$SCENE_DIR" && "$arg" != --* ]]; then
        SCENE_DIR="$arg"
    else
        EXTRA_ARGS+=("$arg")
    fi
done

if [[ -z "$SCENE_DIR" ]]; then
    echo "Usage: $0 [--json] <scene_dir>" >&2
    exit 1
fi

SCENE_DIR="${SCENE_DIR%/}"
SCENE_NAME=$(basename "$SCENE_DIR")

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

MANIFEST="$SCENE_DIR/manifest.json"
if [[ ! -f "$MANIFEST" ]]; then
    echo "Error: manifest.json not found in $SCENE_DIR" >&2
    exit 1
fi

# ── Detect manifest type ──────────────────────────────
MANIFEST_TYPE=$(jq -r '.type // "scene"' "$MANIFEST" 2>/dev/null || \
    python3 -c "import json,sys; print(json.load(open('$MANIFEST')).get('type','scene'))" 2>/dev/null || \
    echo "scene")

json_arg=""
if [[ "$JSON_OUTPUT" == true ]]; then
    json_arg="--json"
fi

# ── Route by type ─────────────────────────────────────
# Per PRD D2: composite-unified is the canonical composite path (preserves
# narrative state continuity). Legacy "composite" manifests are auto-routed
# to composite-unified with a deprecation warning. The old split-render
# composite-render.py remains available via MACODE_USE_LEGACY_COMPOSITE=1.

case "$MANIFEST_TYPE" in
    composite|composite-unified)
        if [[ "$MANIFEST_TYPE" == "composite" && "${MACODE_USE_LEGACY_COMPOSITE:-0}" == "1" ]]; then
            echo "[render.sh] MACODE_USE_LEGACY_COMPOSITE=1 → using composite-render.py (deprecated)" >&2
            exec "$PROJECT_ROOT/pipeline/composite-render.py" "$SCENE_DIR" $json_arg
        fi
        if [[ "$MANIFEST_TYPE" == "composite" ]]; then
            echo "[render.sh] manifest.type='composite' is deprecated — auto-routing to composite-unified" >&2
            echo "  Set 'type: composite-unified' in manifest.json to silence this warning." >&2
        fi
        exec "$PROJECT_ROOT/pipeline/composite-unified-render.py" "$SCENE_DIR" $json_arg "${EXTRA_ARGS[@]}"
        ;;
    *)
        # Default: single scene (Manim, ManimGL, Motion Canvas, etc.)
        exec "$PROJECT_ROOT/pipeline/render-scene.py" "$SCENE_DIR" $json_arg "${EXTRA_ARGS[@]}"
        ;;
esac
