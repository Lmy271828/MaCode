#!/usr/bin/env bash
set -euo pipefail

# Colors
PASS_COLOR='\033[0;32m'
FAIL_COLOR='\033[0;31m'
SKIP_COLOR='\033[1;33m'
RESET='\033[0m'

# Global counters
TESTS_RUN=0
TESTS_PASSED=0
TESTS_FAILED=0

# Last assertion result
LAST_ASSERT_OK=1

# Test name
CURRENT_TEST=""

assert_exit_code() {
    local expected="$1"
    local actual="$?"
    LAST_ASSERT_OK=1
    if [[ "$actual" -eq "$expected" ]]; then
        LAST_ASSERT_OK=0
    else
        echo -e "${FAIL_COLOR}[FAIL]${RESET} assert_exit_code: expected $expected, got $actual at ${CURRENT_TEST:-unknown}"
        TEST_ANY_ASSERT_FAILED=1
        return 1
    fi
}

assert_file_exists() {
    local path="$1"
    LAST_ASSERT_OK=1
    if [[ -e "$path" ]]; then
        LAST_ASSERT_OK=0
    else
        echo -e "${FAIL_COLOR}[FAIL]${RESET} assert_file_exists: expected file '$path' to exist, got missing at ${CURRENT_TEST:-unknown}"
        TEST_ANY_ASSERT_FAILED=1
        return 1
    fi
}

assert_file_not_empty() {
    local path="$1"
    LAST_ASSERT_OK=1
    if [[ -s "$path" ]]; then
        LAST_ASSERT_OK=0
    else
        echo -e "${FAIL_COLOR}[FAIL]${RESET} assert_file_not_empty: expected file '$path' to not be empty, got empty at ${CURRENT_TEST:-unknown}"
        TEST_ANY_ASSERT_FAILED=1
        return 1
    fi
}

assert_state_json() {
    local path="$1"
    local expected_status="$2"
    LAST_ASSERT_OK=1
    if [[ ! -e "$path" ]]; then
        echo -e "${FAIL_COLOR}[FAIL]${RESET} assert_state_json: expected state file '$path' to exist, got missing at ${CURRENT_TEST:-unknown}"
        TEST_ANY_ASSERT_FAILED=1
        return 1
    fi
    local actual_status
    actual_status="$(python3 -c "import json,sys; d=json.load(open('$path')); print(d.get('status','null'))" 2>/dev/null || echo 'null')"
    if [[ "$actual_status" == "$expected_status" ]]; then
        LAST_ASSERT_OK=0
    else
        echo -e "${FAIL_COLOR}[FAIL]${RESET} assert_state_json: expected status '$expected_status', got '$actual_status' at ${CURRENT_TEST:-unknown}"
        TEST_ANY_ASSERT_FAILED=1
        return 1
    fi
}

assert_state_json_v1() {
    local state_dir="$1"
    local expected_status="$2"
    local expected_tool="${3:-}"
    LAST_ASSERT_OK=1
    local state_path
    state_path="${state_dir}/state.json"
    if [[ ! -e "$state_path" ]]; then
        echo -e "${FAIL_COLOR}[FAIL]${RESET} assert_state_json_v1: expected state file '$state_path' to exist, got missing at ${CURRENT_TEST:-unknown}"
        TEST_ANY_ASSERT_FAILED=1
        return 1
    fi

    local project_root
    project_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
    local version status tool
    version="$(python3 "$project_root/bin/state-read.py" "$state_dir" --jq .version 2>/dev/null || echo '')"
    status="$(python3 "$project_root/bin/state-read.py" "$state_dir" --jq .status 2>/dev/null || echo '')"
    tool="$(python3 "$project_root/bin/state-read.py" "$state_dir" --jq .tool 2>/dev/null || echo '')"

    if [[ "$version" != "1.0" ]]; then
        echo -e "${FAIL_COLOR}[FAIL]${RESET} assert_state_json_v1: expected version '1.0', got '$version' at ${CURRENT_TEST:-unknown}"
        TEST_ANY_ASSERT_FAILED=1
        return 1
    fi
    if [[ "$status" != "$expected_status" ]]; then
        echo -e "${FAIL_COLOR}[FAIL]${RESET} assert_state_json_v1: expected status '$expected_status', got '$status' at ${CURRENT_TEST:-unknown}"
        TEST_ANY_ASSERT_FAILED=1
        return 1
    fi
    if [[ -n "$expected_tool" && "$tool" != "$expected_tool" ]]; then
        echo -e "${FAIL_COLOR}[FAIL]${RESET} assert_state_json_v1: expected tool '$expected_tool', got '$tool' at ${CURRENT_TEST:-unknown}"
        TEST_ANY_ASSERT_FAILED=1
        return 1
    fi
    LAST_ASSERT_OK=0
}

assert_progress_phases() {
    local path="$1"
    shift
    LAST_ASSERT_OK=1
    if [[ ! -e "$path" ]]; then
        echo -e "${FAIL_COLOR}[FAIL]${RESET} assert_progress_phases: expected progress file '$path' to exist, got missing at ${CURRENT_TEST:-unknown}"
        return 1
    fi
    local phases=()
    for p in "$@"; do
        phases+=("$p")
    done
    local idx=0
    local total="${#phases[@]}"
    while IFS= read -r line; do
        local phase
        phase="$(echo "$line" | python3 -c "import json,sys; print(json.load(sys.stdin).get('phase',''))" 2>/dev/null || true)"
        if [[ "$phase" == "${phases[$idx]}" ]]; then
            idx=$((idx + 1))
            if [[ "$idx" -ge "$total" ]]; then
                LAST_ASSERT_OK=0
                return 0
            fi
        fi
    done < "$path"
    LAST_ASSERT_OK=1
    echo -e "${FAIL_COLOR}[FAIL]${RESET} assert_progress_phases: expected phases '${phases[*]}' in order, not all found at ${CURRENT_TEST:-unknown}"
    return 1
}

assert_frame_count() {
    local frames_dir="$1"
    local expected_count="$2"
    local tolerance="${3:-1}"
    LAST_ASSERT_OK=1
    if [[ ! -d "$frames_dir" ]]; then
        echo -e "${FAIL_COLOR}[FAIL]${RESET} assert_frame_count: expected directory '$frames_dir' to exist, got missing at ${CURRENT_TEST:-unknown}"
        TEST_ANY_ASSERT_FAILED=1
        return 1
    fi
    local actual_count
    actual_count="$(find "$frames_dir" -maxdepth 1 -name '*.png' | wc -l)"
    local diff=$(( actual_count - expected_count ))
    if [[ "$diff" -lt 0 ]]; then
        diff=$(( -diff ))
    fi
    if [[ "$diff" -le "$tolerance" ]]; then
        LAST_ASSERT_OK=0
    else
        echo -e "${FAIL_COLOR}[FAIL]${RESET} assert_frame_count: expected ~$expected_count frames (tolerance $tolerance), got $actual_count at ${CURRENT_TEST:-unknown}"
        TEST_ANY_ASSERT_FAILED=1
        return 1
    fi
}

test_start() {
    local name="$1"
    CURRENT_TEST="$name"
    LAST_ASSERT_OK=1
    TEST_ANY_ASSERT_FAILED=0
    echo ""
    echo "========================================"
    echo "  TEST: $name"
    echo "========================================"
}

test_end() {
    local ok=$(( TEST_ANY_ASSERT_FAILED == 0 ? 0 : 1 ))
    if [[ "$ok" -eq 0 ]]; then
        TESTS_PASSED=$((TESTS_PASSED + 1))
        TESTS_RUN=$((TESTS_RUN + 1))
        echo -e "${PASS_COLOR}[PASS]${RESET} $CURRENT_TEST"
    else
        TESTS_FAILED=$((TESTS_FAILED + 1))
        TESTS_RUN=$((TESTS_RUN + 1))
        echo -e "${FAIL_COLOR}[FAIL]${RESET} $CURRENT_TEST"
    fi
    CURRENT_TEST=""
    LAST_ASSERT_OK=1
    TEST_ANY_ASSERT_FAILED=0
    return $(( ok ))
}
