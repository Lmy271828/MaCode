#!/usr/bin/env bash
set -euo pipefail

source "$(dirname "${BASH_SOURCE[0]}")/lib.sh"

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"

_has_chromium() {
    command -v chromium-browser >/dev/null 2>&1 || \
    command -v chromium >/dev/null 2>&1 || \
    command -v google-chrome >/dev/null 2>&1 || \
    [[ -n "${PUPPETEER_EXECUTABLE_PATH:-}" ]] || \
    ls /home/*/.cache/ms-playwright/chromium-*/chrome-linux*/chrome >/dev/null 2>&1 || \
    ls /root/.cache/ms-playwright/chromium-*/chrome-linux*/chrome >/dev/null 2>&1
}

if ! _has_chromium; then
    echo -e "${SKIP_COLOR}[SKIP]${RESET} Chromium not available, skipping all Motion Canvas contract tests"
fi

test_mc_state_schema_v1() {
    if ! _has_chromium; then
        test_start "test_mc_state_schema_v1"
        echo -e "${SKIP_COLOR}[SKIP]${RESET} Chromium not available"
        LAST_ASSERT_OK=0
        test_end
        return 0
    fi

    test_start "test_mc_state_schema_v1"

    cd "$PROJECT_ROOT"
    ./bin/macode render scenes/01_test_mc --fps 2 --duration 1 >/dev/null 2>&1
    assert_exit_code 0

    # MC unified render writes state.json under tmp
    local state_path=".agent/tmp/01_test_mc/state.json"
    if [[ -f "$state_path" ]]; then
        assert_file_exists "$state_path"
        assert_file_not_empty "$state_path"

        local version status
        version="$(python3 -c "import json; d=json.load(open('$state_path')); print(d.get('version',''))")"
        status="$(python3 -c "import json; d=json.load(open('$state_path')); print(d.get('status',''))")"

        if [[ "$version" != "1.1" && "$version" != "1.0" ]]; then
            echo -e "${FAIL_COLOR}[FAIL]${RESET} expected version 1.0/1.1, got '$version' at ${CURRENT_TEST:-unknown}"
            LAST_ASSERT_OK=1
        fi
        if [[ "$status" != "completed" ]]; then
            echo -e "${FAIL_COLOR}[FAIL]${RESET} expected status completed, got '$status' at ${CURRENT_TEST:-unknown}"
            LAST_ASSERT_OK=1
        fi
    else
        # MC may not write state.json in all paths; verify progress instead
        assert_file_exists ".agent/progress/01_test_mc.jsonl"
    fi

    test_end
}

test_mc_progress_has_completed() {
    if ! _has_chromium; then
        test_start "test_mc_progress_has_completed"
        echo -e "${SKIP_COLOR}[SKIP]${RESET} Chromium not available"
        LAST_ASSERT_OK=0
        test_end
        return 0
    fi

    test_start "test_mc_progress_has_completed"

    cd "$PROJECT_ROOT"
    ./bin/macode render scenes/01_test_mc --fps 2 --duration 1 >/dev/null 2>&1
    assert_exit_code 0

    local progress_path=".agent/progress/01_test_mc.jsonl"
    assert_file_exists "$progress_path"

    local has_completed
    has_completed="$(python3 -c "
import json, sys
found = False
with open('$progress_path') as f:
    for line in f:
        if not line.strip(): continue
        d = json.loads(line)
        if d.get('phase') == 'capture' and d.get('status') == 'completed':
            found = True
            break
print('yes' if found else 'no')
")"

    if [[ "$has_completed" != "yes" ]]; then
        echo -e "${FAIL_COLOR}[FAIL]${RESET} expected progress to contain capture/completed at ${CURRENT_TEST:-unknown}"
        LAST_ASSERT_OK=1
    fi

    test_end
}

test_mc_final_mp4_exists_and_nonempty() {
    if ! _has_chromium; then
        test_start "test_mc_final_mp4_exists_and_nonempty"
        echo -e "${SKIP_COLOR}[SKIP]${RESET} Chromium not available"
        LAST_ASSERT_OK=0
        test_end
        return 0
    fi

    test_start "test_mc_final_mp4_exists_and_nonempty"

    cd "$PROJECT_ROOT"
    ./bin/macode render scenes/01_test_mc --fps 2 --duration 1 >/dev/null 2>&1
    assert_exit_code 0

    assert_file_exists ".agent/tmp/01_test_mc/final.mp4"
    assert_file_not_empty ".agent/tmp/01_test_mc/final.mp4"

    test_end
}

test_mc_frame_count_matches_duration() {
    if ! _has_chromium; then
        test_start "test_mc_frame_count_matches_duration"
        echo -e "${SKIP_COLOR}[SKIP]${RESET} Chromium not available"
        LAST_ASSERT_OK=0
        test_end
        return 0
    fi

    test_start "test_mc_frame_count_matches_duration"

    cd "$PROJECT_ROOT"
    local fps=2 duration=1
    ./bin/macode render scenes/01_test_mc --fps "$fps" --duration "$duration" >/dev/null 2>&1
    assert_exit_code 0

    local frame_count
    frame_count=$(find ".agent/tmp/01_test_mc/frames" -maxdepth 1 -name '*.png' | wc -l)
    local expected=$((fps * duration))
    local diff=$((frame_count - expected))
    if [[ ${diff#-} -gt 1 ]]; then
        echo -e "${FAIL_COLOR}[FAIL]${RESET} expected ~$expected frames, got $frame_count at ${CURRENT_TEST:-unknown}"
        LAST_ASSERT_OK=1
    fi

    test_end
}
