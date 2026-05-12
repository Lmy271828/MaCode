#!/usr/bin/env bash
set -euo pipefail

# bin/macode-dev.sh
# MaCode unified dev mode entrypoint.
# Pure dispatcher: extracts scene_dir, discovers engine, delegates to engine dev.sh.
#
# Usage: macode-dev.sh <scene_dir> [engine-specific-options...]
#
# Engine-specific options (passed through transparently):
#   manim:         (none — dev.sh reads manifest internally)
#   manimgl:       [--segment <seg_id>]
#   motion_canvas: [--snapshot [time]] [--watch] [--port <n>]

# Intercept --help / -h at any argument position before parsing
for _arg in "$@"; do
    if [[ "$_arg" == "--help" || "$_arg" == "-h" ]]; then
        cat <<'EOF'
Usage: macode-dev.sh <scene_dir> [options...]

MaCode unified dev mode entrypoint. Delegates to engine-specific dev.sh.

Arguments:
  <scene_dir>    Scene directory, e.g. scenes/01_test/

Common options (availability depends on engine):
  --segment <id>      Seek to segment (manimgl)
  --snapshot [time]   Capture a preview frame (motion_canvas)
  --watch             Watch files and auto-snapshot (motion_canvas)
  --port <n>          Dev server port (motion_canvas)

Examples:
  macode-dev.sh scenes/01_test
  macode-dev.sh scenes/01_test --segment intro
  macode-dev.sh scenes/01_test_mc --snapshot 2.5
  macode-dev.sh scenes/01_test_mc --watch --port 3000
EOF
        exit 0
    fi
done

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

# Extract SCENE_DIR (first non-option argument)
SCENE_DIR=""
for arg in "$@"; do
    if [[ "$arg" != -* && -z "$SCENE_DIR" ]]; then
        SCENE_DIR="$arg"
        break
    fi
done

if [[ -z "$SCENE_DIR" ]]; then
    echo "Usage: $0 <scene_dir> [options...]" >&2
    exit 1
fi

SCENE_DIR="${SCENE_DIR%/}"
MANIFEST="$SCENE_DIR/manifest.json"

if [[ ! -f "$MANIFEST" ]]; then
    echo "Error: manifest.json not found in $SCENE_DIR" >&2
    exit 1
fi

ENGINE=$(python3 -c "
import json, sys, os
manifest = json.load(open('$MANIFEST'))
engine = manifest.get('engine')
if engine:
    print(engine)
else:
    scene_dir = os.path.dirname('$MANIFEST')
    files = os.listdir(scene_dir)
    if any(f.endswith('.tsx') for f in files):
        print('motion_canvas')
    elif any(f.endswith('.py') for f in files):
        print('manimgl')
    else:
        print('manimgl')
")
SCENE_NAME=$(basename "$SCENE_DIR")

echo "[macode dev] Scene: $SCENE_NAME"
echo "[macode dev] Engine: $ENGINE"

ENGINE_DEV="$PROJECT_ROOT/engines/$ENGINE/scripts/dev.sh"
if [[ ! -f "$ENGINE_DEV" ]]; then
    echo "Error: dev.sh not found for engine '$ENGINE'" >&2
    echo "       Expected: $ENGINE_DEV" >&2
    exit 1
fi

# Delegate all original arguments to engine dev.sh.
# Engine dev.sh is responsible for parsing its own options.
exec bash "$ENGINE_DEV" "$@"
