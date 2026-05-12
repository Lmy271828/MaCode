#!/usr/bin/env bash
set -euo pipefail

# pipeline/cache.sh
# Backward-compatible adapter for the new UNIX-style cache tool chain.
# Under the hood, delegates to bin/cache-{key,check,restore,store}.py

if [[ "${1:-}" == "--help" || "${1:-}" == "-h" ]]; then
    SCRIPT_NAME=$(basename "$0")
    cat <<EOF
Usage: $SCRIPT_NAME <scene_dir> <check|populate> [output_dir]

Frame-level cache based on scene source + manifest + shader dependency hash.

Arguments:
  <scene_dir>   Scene directory containing scene.* and manifest.json
  <action>      check (restore cached output) or populate (store output)
  [output_dir]  Required for check/populate, output directory path

Examples:
  $SCRIPT_NAME scenes/01_test check .agent/tmp/01_test
  $SCRIPT_NAME scenes/01_test populate .agent/tmp/01_test
EOF
    exit 0
fi

SCENE_DIR="${1:-}"
ACTION="${2:-}"
OUTPUT_DIR="${3:-}"

if [[ -z "$SCENE_DIR" || -z "$ACTION" ]]; then
    echo "Usage: $0 <scene_dir> <check|populate> [output_dir]" >&2
    exit 1
fi

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CACHE_KEY=$(python3 "$PROJECT_ROOT/bin/cache-key.py" "$SCENE_DIR")

case "$ACTION" in
    check)
        if [[ -z "$OUTPUT_DIR" ]]; then
            echo "Usage: $0 <scene_dir> check <output_dir>" >&2
            exit 1
        fi
        if python3 "$PROJECT_ROOT/bin/cache-check.py" "$CACHE_KEY"; then
            python3 "$PROJECT_ROOT/bin/cache-restore.py" "$CACHE_KEY" "$OUTPUT_DIR"
            exit 0
        else
            echo "$CACHE_KEY" > "$OUTPUT_DIR/.cache_path"
            exit 1
        fi
        ;;
    populate)
        if [[ -z "$OUTPUT_DIR" ]]; then
            echo "Usage: $0 <scene_dir> populate <output_dir>" >&2
            exit 1
        fi
        python3 "$PROJECT_ROOT/bin/cache-store.py" "$CACHE_KEY" "$OUTPUT_DIR"
        rm -f "$OUTPUT_DIR/.cache_path"
        ;;
    *)
        echo "[cache] ERROR: unknown action '$ACTION' (use check or populate)" >&2
        exit 1
        ;;
esac
