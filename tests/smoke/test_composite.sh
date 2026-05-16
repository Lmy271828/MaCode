#!/usr/bin/env bash
set -euo pipefail

source "$(dirname "$0")/lib.sh"

PROJECT_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"

test_composite_render() {
    test_start "test_composite_render"

    local scene_dir="$PROJECT_ROOT/scenes/04_composite_demo"
    if [[ ! -d "$scene_dir" ]]; then
        echo "[SKIP] Scene 04_composite_demo not found, skipping test"
        LAST_ASSERT_OK=0
        test_end
        return 0
    fi

    cd "$PROJECT_ROOT"
    # type: composite-unified; segment-level
    # .agent/tmp/{shot}/state.json are no longer written (legacy path removed).
    ./bin/macode composite render scenes/04_composite_demo --fps 2 --duration 1
    assert_exit_code 0

    assert_file_exists "output/04_composite_demo.mp4"
    assert_file_not_empty "output/04_composite_demo.mp4"

    assert_state_json ".agent/tmp/04_composite_demo/state.json" "completed"

    test_end
}

test_composite_unified_render() {
    test_start "test_composite_unified_render"

    local scene_dir="$PROJECT_ROOT/scenes/04_composite_unified_demo"
    if [[ ! -d "$scene_dir" ]]; then
        echo "[SKIP] Scene 04_composite_unified_demo not found, skipping test"
        LAST_ASSERT_OK=0
        test_end
        return 0
    fi

    cd "$PROJECT_ROOT"
    ./bin/macode render scenes/04_composite_unified_demo --fps 2 --duration 1
    assert_exit_code 0

    assert_file_exists "output/04_composite_unified_demo.mp4"

    test_end
}

test_hybrid_overlay() {
    test_start "test_hybrid_overlay"

    local scene_dir="$PROJECT_ROOT/scenes/99_hybrid_demo"
    if [[ ! -d "$scene_dir" ]]; then
        echo "[SKIP] Scene 99_hybrid_demo not found, skipping test"
        LAST_ASSERT_OK=0
        test_end
        return 0
    fi

    cd "$PROJECT_ROOT"
    ./bin/macode render scenes/99_hybrid_demo --fps 2 --duration 1
    assert_exit_code 0

    assert_file_exists "output/99_hybrid_demo.mp4"
    assert_file_not_empty "output/99_hybrid_demo.mp4"

    test_end
}
