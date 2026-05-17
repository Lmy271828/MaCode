#!/usr/bin/env bash
set -euo pipefail

source "$(dirname "${BASH_SOURCE[0]}")/lib.sh"

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"

test_manim_state_schema_v1() {
    test_start "test_manim_state_schema_v1"

    cd "$PROJECT_ROOT"
    ./bin/macode render scenes/01_test --fps 2 --duration 1 >/dev/null 2>&1
    assert_exit_code 0

    local state_path=".agent/tmp/01_test/state.json"
    assert_file_exists "$state_path"
    assert_file_not_empty "$state_path"

    local version status task_id exit_code
    version="$(python3 -c "import json; d=json.load(open('$state_path')); print(d.get('version',''))")"
    status="$(python3 -c "import json; d=json.load(open('$state_path')); print(d.get('status',''))")"
    task_id="$(python3 -c "import json; d=json.load(open('$state_path')); print(d.get('taskId',''))")"
    exit_code="$(python3 -c "import json; d=json.load(open('$state_path')); print(d.get('exitCode',''))")"

    if [[ "$version" != "1.1" && "$version" != "1.0" ]]; then
        echo -e "${FAIL_COLOR}[FAIL]${RESET} expected version 1.0/1.1, got '$version' at ${CURRENT_TEST:-unknown}"
        LAST_ASSERT_OK=1
    fi
    if [[ "$status" != "completed" ]]; then
        echo -e "${FAIL_COLOR}[FAIL]${RESET} expected status completed, got '$status' at ${CURRENT_TEST:-unknown}"
        LAST_ASSERT_OK=1
    fi
    if [[ "$task_id" != "01_test" ]]; then
        echo -e "${FAIL_COLOR}[FAIL]${RESET} expected taskId 01_test, got '$task_id' at ${CURRENT_TEST:-unknown}"
        LAST_ASSERT_OK=1
    fi
    if [[ "$exit_code" != "0" ]]; then
        echo -e "${FAIL_COLOR}[FAIL]${RESET} expected exitCode 0, got '$exit_code' at ${CURRENT_TEST:-unknown}"
        LAST_ASSERT_OK=1
    fi

    test_end
}

test_manim_progress_has_completed() {
    test_start "test_manim_progress_has_completed"

    cd "$PROJECT_ROOT"
    ./bin/macode render scenes/01_test --fps 2 --duration 1 >/dev/null 2>&1
    assert_exit_code 0

    local progress_path=".agent/progress/01_test.jsonl"
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

test_manim_final_mp4_exists_and_nonempty() {
    test_start "test_manim_final_mp4_exists_and_nonempty"

    cd "$PROJECT_ROOT"
    ./bin/macode render scenes/01_test --fps 2 --duration 1 >/dev/null 2>&1
    assert_exit_code 0

    assert_file_exists ".agent/tmp/01_test/final.mp4"
    assert_file_not_empty ".agent/tmp/01_test/final.mp4"

    test_end
}

test_manim_frame_count_matches_duration() {
    test_start "test_manim_frame_count_matches_duration"

    cd "$PROJECT_ROOT"
    local fps=2 duration=1
    ./bin/macode render scenes/01_test --fps "$fps" --duration "$duration" >/dev/null 2>&1
    assert_exit_code 0

    local frame_count
    frame_count=$(find ".agent/tmp/01_test/frames" -maxdepth 1 -name '*.png' | wc -l)
    local expected=$((fps * duration))
    #容差 ±1
    local diff=$((frame_count - expected))
    if [[ ${diff#-} -gt 1 ]]; then
        echo -e "${FAIL_COLOR}[FAIL]${RESET} expected ~$expected frames, got $frame_count at ${CURRENT_TEST:-unknown}"
        LAST_ASSERT_OK=1
    fi

    test_end
}
