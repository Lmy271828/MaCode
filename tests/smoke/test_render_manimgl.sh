#!/usr/bin/env bash
set -euo pipefail

source "$(dirname "$0")/lib.sh"

PROJECT_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"

test_manimgl_headless_render() {
    test_start "test_manimgl_headless_render"

    cd "$PROJECT_ROOT"
    MACODE_HEADLESS=1 ./bin/macode render scenes/09_zone_test --fps 2 --duration 1 --no-review >/dev/null 2>&1
    assert_exit_code 0

    local scene_name
    scene_name="09_zone_test"

    # ManimGL (interactive mode) writes frames directly to tmp_dir, not tmp_dir/frames/
    assert_file_exists ".agent/tmp/$scene_name/frame_0001.png"
    assert_file_exists ".agent/tmp/$scene_name/frame_0002.png"

    if [[ -f ".agent/tmp/$scene_name/state.json" ]]; then
        assert_state_json_v1 ".agent/tmp/$scene_name" "completed"
    fi

    if [[ -f ".agent/progress/$scene_name.jsonl" ]]; then
        assert_progress_phases ".agent/progress/$scene_name.jsonl" "init" "capture"
    fi

    test_end
}
