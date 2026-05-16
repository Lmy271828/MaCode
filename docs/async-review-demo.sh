#!/usr/bin/env bash
# docs/async-review-demo.sh
# > ARCHIVED: This demo references the old `review_needed` + exit 3 blocking
# > mechanism which was removed in P0-3. The `human_override.json` channel
# > (approve/reject/retry) is still active; see `bin/signal-check.py`.
#
# End-to-end demonstration of the async review workflow:
#   Agent marks state → Human async decision → Agent next-round execution
#
# Usage:
#   bash docs/async-review-demo.sh

set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SCENE="01_test"
SCENE_DIR="$PROJECT_ROOT/scenes/$SCENE"
SIGNALS_DIR="$PROJECT_ROOT/.agent/signals/per-scene/$SCENE"

echo "═══════════════════════════════════════════════════════════════"
echo "  MaCode Async Review Model — End-to-End Demo"
echo "═══════════════════════════════════════════════════════════════"
echo ""
echo "Scene: $SCENE"
echo ""

# ── Cleanup ──
rm -rf "$SIGNALS_DIR"
mkdir -p "$SIGNALS_DIR"

echo "Step 1: First Agent round — render completes, marks review_needed"
echo "----------------------------------------------------------------"
# Simulate what render-scene.py does after deliver:
touch "$SIGNALS_DIR/review_needed"
echo "  [Agent] Created: $SIGNALS_DIR/review_needed"
echo "  [Agent] Exits immediately (non-blocking). Human can review anytime."
echo ""

echo "Step 2: Human checks review queue"
echo "----------------------------------------------------------------"
"$PROJECT_ROOT/bin/macode" review list
echo ""

echo "Step 3: Second Agent round — no human response yet"
echo "----------------------------------------------------------------"
echo "  [Agent] Calls: macode render scenes/$SCENE"
echo "  [render-scene.py] Detects review_needed exists, no override → exit 3"
# Simulate by checking the signal directly:
if [[ -f "$SIGNALS_DIR/review_needed" && ! -f "$SIGNALS_DIR/human_override.json" ]]; then
    echo '  {"status": "awaiting_review", "scene": "'$SCENE'", "message": "..."}'
    echo "  [Agent] Exit code 3 → no re-render, waits for next scheduling round."
fi
echo ""

echo "Step 4: Human reviews and approves"
echo "----------------------------------------------------------------"
"$PROJECT_ROOT/bin/macode" review approve "$SCENE"
echo ""

echo "Step 5: Third Agent round — human_override detected"
echo "----------------------------------------------------------------"
echo "  [Agent] Calls: macode render scenes/$SCENE"
echo "  [render-scene.py] Detects human_override.json with action='approve'"
# Simulate:
if [[ -f "$SIGNALS_DIR/human_override.json" ]]; then
    ACTION=$(python3 -c "import json; print(json.load(open('$SIGNALS_DIR/human_override.json')).get('action',''))")
    if [[ "$ACTION" == "approve" ]]; then
        echo "  [render-scene.py] Cleans up review_needed + override → exit 0"
        rm -f "$SIGNALS_DIR/review_needed" "$SIGNALS_DIR/human_override.json"
        echo "  [Agent] Scene approved. Workflow complete."
    fi
fi
echo ""

echo "═══════════════════════════════════════════════════════════════"
echo "  Demo complete. Review queue is now empty:"
echo "═══════════════════════════════════════════════════════════════"
"$PROJECT_ROOT/bin/macode" review list
