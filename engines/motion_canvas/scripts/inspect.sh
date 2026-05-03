#!/usr/bin/env bash
set -euo pipefail

# engines/motion_canvas/scripts/inspect.sh
# 打印该引擎可用的模板与工具函数。

echo "=== Motion Canvas Engine Inspection ==="
echo ""

echo "--- Installed Packages ---"
cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && npm ls @motion-canvas/core @motion-canvas/2d @motion-canvas/vite-plugin 2>&1 || true
echo ""

echo "--- Scene Templates ---"
echo "  makeScene2D"
echo ""

echo "--- Common Nodes ---"
cat <<'EOF'
  Circle
  Rect
  Line
  Text
  Layout
  Node
  Img
  Video
  Latex
  SVG
EOF
echo ""

echo "--- Common Signals / Hooks ---"
cat <<'EOF'
  createSignal
  createRef
  all / sequence / loop
  useLogger
  useProject
  useScene
  useThread
EOF
echo ""

echo "--- Package Paths ---"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../../.." && pwd)"
if [[ -d "$PROJECT_ROOT/node_modules/@motion-canvas" ]]; then
    ls -d "$PROJECT_ROOT/node_modules/@motion-canvas/"*
fi
