#!/usr/bin/env bash
set -euo pipefail

source "$(dirname "$0")/lib.sh"

PROJECT_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"

test_manim_cache_hit() {
    test_start "test_manim_cache_hit"

    local scene_dir="$PROJECT_ROOT/scenes/01_test"
    local tmp_dir="$PROJECT_ROOT/.agent/tmp/01_test"
    local progress_path="$PROJECT_ROOT/.agent/progress/01_test.jsonl"
    local log_dir="$PROJECT_ROOT/.agent/log"

    # Clean slate: remove cache, output, progress
    rm -rf "$PROJECT_ROOT/.agent/cache"/*
    rm -rf "$tmp_dir"
    rm -f "$progress_path"

    # ---- First render: cache miss ----
    cd "$PROJECT_ROOT"
    ./bin/macode render scenes/01_test --fps 2 --duration 1 --no-review >/dev/null 2>&1
    assert_exit_code 0

    assert_file_exists "$tmp_dir/final.mp4"
    assert_file_not_empty "$tmp_dir/final.mp4"

    # Verify engine actually ran: progress should contain "capture" phase
    if [[ -f "$progress_path" ]]; then
        LAST_ASSERT_OK=1
        if grep -q '"phase": "capture"' "$progress_path"; then
            LAST_ASSERT_OK=0
        else
            echo -e "${FAIL_COLOR}[FAIL]${RESET} expected 'capture' phase in first render progress at ${CURRENT_TEST:-unknown}"
            test_end
            return 1
        fi
    fi

    # Save frame count for later comparison
    local frame_count_first=0
    if [[ -d "$tmp_dir/frames" ]]; then
        frame_count_first=$(find "$tmp_dir/frames" -maxdepth 1 -name '*.png' | wc -l)
    fi

    # ---- Second render: cache hit ----
    # Delete output but keep cache
    rm -rf "$tmp_dir"
    rm -f "$progress_path"

    # Capture log to verify cache hit message
    local log_file
    log_file="$log_dir/macode_render_01_test_cache_hit.log"
    rm -f "$log_file"

    cd "$PROJECT_ROOT"
    ./bin/macode render scenes/01_test --fps 2 --duration 1 --no-review >"$log_file" 2>&1
    assert_exit_code 0

    assert_file_exists "$tmp_dir/final.mp4"
    assert_file_not_empty "$tmp_dir/final.mp4"

    # Verify cache hit message in log
    LAST_ASSERT_OK=1
    if grep -q "Using cached frames, skipping engine render" "$log_file"; then
        LAST_ASSERT_OK=0
    else
        echo -e "${FAIL_COLOR}[FAIL]${RESET} expected cache hit message in log at ${CURRENT_TEST:-unknown}"
        test_end
        return 1
    fi

    # Verify engine was skipped: progress should NOT contain "capture" phase
    if [[ -f "$progress_path" ]]; then
        LAST_ASSERT_OK=1
        if ! grep -q '"phase": "capture"' "$progress_path"; then
            LAST_ASSERT_OK=0
        else
            echo -e "${FAIL_COLOR}[FAIL]${RESET} expected NO 'capture' phase in second render progress at ${CURRENT_TEST:-unknown}"
            test_end
            return 1
        fi
    fi

    # Verify frame count matches first render
    local frame_count_second=0
    if [[ -d "$tmp_dir/frames" ]]; then
        frame_count_second=$(find "$tmp_dir/frames" -maxdepth 1 -name '*.png' | wc -l)
    fi
    LAST_ASSERT_OK=1
    if [[ "$frame_count_first" -eq "$frame_count_second" ]]; then
        LAST_ASSERT_OK=0
    else
        echo -e "${FAIL_COLOR}[FAIL]${RESET} frame count mismatch: first=$frame_count_first second=$frame_count_second at ${CURRENT_TEST:-unknown}"
        test_end
        return 1
    fi

    test_end
}

test_mc_cache_hit() {
    test_start "test_mc_cache_hit"

    # Skip if Chromium not available
    local has_chromium=false
    if command -v chromium-browser >/dev/null 2>&1 || \
       command -v chromium >/dev/null 2>&1 || \
       command -v google-chrome >/dev/null 2>&1 || \
       [[ -n "${PUPPETEER_EXECUTABLE_PATH:-}" ]] || \
       ls /home/*/.cache/ms-playwright/chromium-*/chrome-linux*/chrome >/dev/null 2>&1 || \
       ls /root/.cache/ms-playwright/chromium-*/chrome-linux*/chrome >/dev/null 2>&1; then
        has_chromium=true
    fi

    if [[ "$has_chromium" != "true" ]]; then
        echo -e "${SKIP_COLOR}[SKIP]${RESET} Chromium not available"
        LAST_ASSERT_OK=0
        test_end
        return 0
    fi

    local scene_dir="$PROJECT_ROOT/scenes/01_test_mc"
    local tmp_dir="$PROJECT_ROOT/.agent/tmp/01_test_mc"
    local progress_path="$PROJECT_ROOT/.agent/progress/01_test_mc.jsonl"
    local log_dir="$PROJECT_ROOT/.agent/log"

    # Clean slate
    rm -rf "$PROJECT_ROOT/.agent/cache"/*
    rm -rf "$tmp_dir"
    rm -f "$progress_path"

    # ---- First render: cache miss ----
    cd "$PROJECT_ROOT"
    ./bin/macode render scenes/01_test_mc --fps 2 --duration 1 --no-review >/dev/null 2>&1
    assert_exit_code 0

    assert_file_exists "$tmp_dir/final.mp4"
    assert_file_not_empty "$tmp_dir/final.mp4"

    # Verify engine actually ran: progress should contain "capture" phase
    if [[ -f "$progress_path" ]]; then
        LAST_ASSERT_OK=1
        if grep -q '"phase": "capture"' "$progress_path"; then
            LAST_ASSERT_OK=0
        else
            echo -e "${FAIL_COLOR}[FAIL]${RESET} expected 'capture' phase in first MC render progress at ${CURRENT_TEST:-unknown}"
            test_end
            return 1
        fi
    fi

    # Save frame count
    local frame_count_first=0
    if [[ -d "$tmp_dir/frames" ]]; then
        frame_count_first=$(find "$tmp_dir/frames" -maxdepth 1 -name '*.png' | wc -l)
    fi

    # ---- Second render: cache hit ----
    rm -rf "$tmp_dir"
    rm -f "$progress_path"

    local log_file
    log_file="$log_dir/macode_render_01_test_mc_cache_hit.log"
    rm -f "$log_file"

    cd "$PROJECT_ROOT"
    ./bin/macode render scenes/01_test_mc --fps 2 --duration 1 --no-review >"$log_file" 2>&1
    assert_exit_code 0

    assert_file_exists "$tmp_dir/final.mp4"
    assert_file_not_empty "$tmp_dir/final.mp4"

    # Verify cache hit message
    LAST_ASSERT_OK=1
    if grep -q "Using cached frames, skipping engine render" "$log_file"; then
        LAST_ASSERT_OK=0
    else
        echo -e "${FAIL_COLOR}[FAIL]${RESET} expected cache hit message in MC log at ${CURRENT_TEST:-unknown}"
        test_end
        return 1
    fi

    # Verify engine was skipped
    if [[ -f "$progress_path" ]]; then
        LAST_ASSERT_OK=1
        if ! grep -q '"phase": "capture"' "$progress_path"; then
            LAST_ASSERT_OK=0
        else
            echo -e "${FAIL_COLOR}[FAIL]${RESET} expected NO 'capture' phase in second MC render progress at ${CURRENT_TEST:-unknown}"
            test_end
            return 1
        fi
    fi

    # Verify frame count
    local frame_count_second=0
    if [[ -d "$tmp_dir/frames" ]]; then
        frame_count_second=$(find "$tmp_dir/frames" -maxdepth 1 -name '*.png' | wc -l)
    fi
    LAST_ASSERT_OK=1
    if [[ "$frame_count_first" -eq "$frame_count_second" ]]; then
        LAST_ASSERT_OK=0
    else
        echo -e "${FAIL_COLOR}[FAIL]${RESET} MC frame count mismatch: first=$frame_count_first second=$frame_count_second at ${CURRENT_TEST:-unknown}"
        test_end
        return 1
    fi

    test_end
}
