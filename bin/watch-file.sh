#!/usr/bin/env bash
set -euo pipefail

# bin/watch-file.sh
# Poll a file for mtime changes and execute a command when it changes.
# Fallback for systems without inotifywait.
#
# Usage: watch-file.sh <file> --exec "<command>" [--interval <seconds>]
#   --exec      Command to run on change (required)
#   --interval  Polling interval in seconds (default: 2)

if [[ "${1:-}" == "--help" || "${1:-}" == "-h" ]]; then
    cat <<'EOF'
Usage: watch-file.sh <file> --exec "<command>" [--interval <seconds>]

Poll a file for mtime changes and execute a command when changed.

Arguments:
  <file>              Path to file to watch
  --exec "<cmd>"      Command to execute on change (required)
  --interval <n>      Polling interval in seconds (default: 2)

Examples:
  watch-file.sh scenes/01_test/scene.py --exec "echo changed"
  watch-file.sh scenes/01_test/scene.py --exec "make preview" --interval 1
EOF
    exit 0
fi

FILE="${1:-}"
if [[ -z "$FILE" ]]; then
    echo "Usage: $0 <file> --exec '<command>' [--interval <seconds>]" >&2
    exit 1
fi

shift

CMD=""
INTERVAL=2

while [[ $# -gt 0 ]]; do
    case "$1" in
        --exec)
            CMD="${2:-}"
            shift 2
            ;;
        --interval)
            INTERVAL="${2:-2}"
            shift 2
            ;;
        *)
            echo "Unknown option: $1" >&2
            echo "Usage: $0 <file> --exec '<command>' [--interval <seconds>]" >&2
            exit 1
            ;;
    esac
done

if [[ -z "$CMD" ]]; then
    echo "Usage: $0 <file> --exec '<command>' [--interval <seconds>]" >&2
    exit 1
fi

if [[ ! -f "$FILE" ]]; then
    echo "Error: file not found: $FILE" >&2
    exit 1
fi

LAST_MTIME=$(stat -c %Y "$FILE" 2>/dev/null || echo "0")

echo "[watch] Watching $FILE for changes..."
echo "[watch] Press Ctrl+C to stop."

while true; do
    sleep "$INTERVAL"
    CURRENT_MTIME=$(stat -c %Y "$FILE" 2>/dev/null || echo "0")
    if [[ "$CURRENT_MTIME" != "$LAST_MTIME" && -n "$LAST_MTIME" ]]; then
        LAST_MTIME="$CURRENT_MTIME"
        echo "[watch] Change detected at $(date '+%H:%M:%S')"
        bash -c "$CMD"
    else
        LAST_MTIME="$CURRENT_MTIME"
    fi
done
