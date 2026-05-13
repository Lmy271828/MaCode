#!/usr/bin/env bash
set -euo pipefail

source "$(dirname "$0")/lib.sh"

PROJECT_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"

test_manim_single_render() {
    test_start "test_manim_single_render"

    cd "$PROJECT_ROOT"
    ./bin/macode render scenes/01_test --fps 2 --duration 1 >/dev/null 2>&1
    assert_exit_code 0

    assert_file_exists ".agent/tmp/01_test/final.mp4"
    assert_file_not_empty ".agent/tmp/01_test/final.mp4"
    # state.json is written by macode-run during actual engine render;
    # skip if missing (e.g. cache hit or engine not yet instrumented)
    if [[ -f ".agent/tmp/01_test/state.json" ]]; then
        assert_state_json_v1 ".agent/tmp/01_test" "completed"
    fi
    # progress.jsonl is Phase 3 instrumentation; skip if not yet implemented
    if [[ -f ".agent/progress/01_test.jsonl" ]]; then
        assert_progress_phases ".agent/progress/01_test.jsonl" "completed"
    fi
    # Manim --format png produces extra frames (preview + partial); just verify non-empty dir
    local frame_count
    frame_count=$(find ".agent/tmp/01_test/frames" -maxdepth 1 -name '*.png' | wc -l)
    if [[ "$frame_count" -eq 0 ]]; then
        echo -e "${FAIL_COLOR}[FAIL]${RESET} expected at least 1 PNG frame, got 0 at ${CURRENT_TEST:-unknown}"
        LAST_ASSERT_OK=1
    fi

    test_end
}

test_manim_param_override() {
    test_start "test_manim_param_override"

    cd "$PROJECT_ROOT"
    ./bin/macode render scenes/01_test --fps 5 --duration 2 >/dev/null 2>&1
    assert_exit_code 0

    local frame_count
    frame_count=$(find ".agent/tmp/01_test/frames" -maxdepth 1 -name '*.png' | wc -l)
    if [[ "$frame_count" -eq 0 ]]; then
        echo -e "${FAIL_COLOR}[FAIL]${RESET} expected at least 1 PNG frame, got 0 at ${CURRENT_TEST:-unknown}"
        LAST_ASSERT_OK=1
    fi
    assert_file_exists ".agent/tmp/01_test/final.mp4"

    test_end
}

test_manifest_validation_fail() {
    test_start "test_manifest_validation_fail"

    local invalid_scene="$PROJECT_ROOT/.agent/tmp/test_invalid_scene"
    mkdir -p "$invalid_scene"
    echo '{}' > "$invalid_scene/manifest.json"

    cd "$PROJECT_ROOT"
    ./bin/macode render "$invalid_scene" >/dev/null 2>&1
    local exit_code=$?

    LAST_ASSERT_OK=1
    if [[ "$exit_code" -ne 0 ]]; then
        LAST_ASSERT_OK=0
    else
        echo -e "${FAIL_COLOR}[FAIL]${RESET} expected non-zero exit code, got $exit_code at ${CURRENT_TEST:-unknown}"
        return 1
    fi

    test_end
}
