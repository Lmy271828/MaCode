#!/usr/bin/env bash
set -euo pipefail

source "$(dirname "${BASH_SOURCE[0]}")/lib.sh"

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
MACODE_RUN="$PROJECT_ROOT/bin/macode-run"

# Helpers
_cleanup_macode_run() {
    local task_id="$1"
    rm -rf "$PROJECT_ROOT/.agent/tmp/$task_id"
    rm -f "$PROJECT_ROOT/.agent/log/"*"_${task_id}.log"
}

_wait_for_state() {
    local state_path="$1"
    local max_wait="${2:-30}"
    local waited=0
    while [[ ! -f "$state_path" && "$waited" -lt "$max_wait" ]]; do
        sleep 0.1
        waited=$((waited + 1))
    done
    [[ -f "$state_path" ]]
}

# ---------------------------------------------------------------------------
# Basic execution
# ---------------------------------------------------------------------------

test_macode_run_success() {
    test_start "test_macode_run_success"

    local task_id="test_success_$$"
    _cleanup_macode_run "$task_id"

    "$MACODE_RUN" "$task_id" -- bash -c "echo hello"
    assert_exit_code 0

    test_end
}

test_macode_run_writes_state() {
    test_start "test_macode_run_writes_state"

    local task_id="test_state_$$"
    local state_path="$PROJECT_ROOT/.agent/tmp/$task_id/state.json"
    _cleanup_macode_run "$task_id"

    "$MACODE_RUN" "$task_id" -- bash -c "echo hello"
    assert_exit_code 0

    assert_file_exists "$state_path"
    assert_state_json "$state_path" "completed"

    # Verify exitCode field
    local exit_code_field
    exit_code_field="$(python3 -c "import json,sys; d=json.load(open('$state_path')); print(d.get('exitCode','null'))")"
    LAST_ASSERT_OK=1
    if [[ "$exit_code_field" == "0" ]]; then
        LAST_ASSERT_OK=0
    else
        echo -e "${FAIL_COLOR}[FAIL]${RESET} expected exitCode 0, got $exit_code_field at ${CURRENT_TEST:-unknown}"
        test_end
        return 1
    fi

    test_end
}

test_macode_run_task_json_merge() {
    test_start "test_macode_run_task_json_merge"

    local task_id="test_merge_$$"
    local state_path="$PROJECT_ROOT/.agent/tmp/$task_id/state.json"
    _cleanup_macode_run "$task_id"

    "$MACODE_RUN" "$task_id" -- bash -c \
        'echo "{\"status\": \"completed\", \"outputs\": {\"framesDir\": \"/tmp/frames\"}}" > "$MACODE_STATE_DIR/task.json"'
    assert_exit_code 0

    assert_file_exists "$state_path"

    local frames_dir
    frames_dir="$(python3 -c "import json,sys; d=json.load(open('$state_path')); print(d.get('outputs',{}).get('framesDir','null'))")"
    LAST_ASSERT_OK=1
    if [[ "$frames_dir" == "/tmp/frames" ]]; then
        LAST_ASSERT_OK=0
    else
        echo -e "${FAIL_COLOR}[FAIL]${RESET} expected framesDir=/tmp/frames, got $frames_dir at ${CURRENT_TEST:-unknown}"
        test_end
        return 1
    fi

    test_end
}

test_macode_run_child_failure() {
    test_start "test_macode_run_child_failure"

    local task_id="test_fail_$$"
    local state_path="$PROJECT_ROOT/.agent/tmp/$task_id/state.json"
    _cleanup_macode_run "$task_id"

    set +e
    "$MACODE_RUN" "$task_id" -- bash -c "exit 42"
    local macode_exit=$?
    set -e

    LAST_ASSERT_OK=1
    if [[ "$macode_exit" -eq 42 ]]; then
        LAST_ASSERT_OK=0
    else
        echo -e "${FAIL_COLOR}[FAIL]${RESET} expected macode-run exit 42, got $macode_exit at ${CURRENT_TEST:-unknown}"
        test_end
        return 1
    fi

    assert_state_json "$state_path" "failed"

    test_end
}

# ---------------------------------------------------------------------------
# Timeout handling
# ---------------------------------------------------------------------------

test_macode_run_timeout_sigterm() {
    test_start "test_macode_run_timeout_sigterm"

    local task_id="test_timeout_$$"
    local state_path="$PROJECT_ROOT/.agent/tmp/$task_id/state.json"
    _cleanup_macode_run "$task_id"

    set +e
    "$MACODE_RUN" "$task_id" --timeout 1 -- bash -c "sleep 100"
    local macode_exit=$?
    set -e

    LAST_ASSERT_OK=1
    if [[ "$macode_exit" -ne 0 ]]; then
        LAST_ASSERT_OK=0
    else
        echo -e "${FAIL_COLOR}[FAIL]${RESET} expected non-zero exit on timeout at ${CURRENT_TEST:-unknown}"
        test_end
        return 1
    fi

    assert_file_exists "$state_path"
    assert_state_json "$state_path" "timeout"

    test_end
}

test_macode_run_timeout_sigkill() {
    test_start "test_macode_run_timeout_sigkill"

    local task_id="test_kill_$$"
    local state_path="$PROJECT_ROOT/.agent/tmp/$task_id/state.json"
    _cleanup_macode_run "$task_id"

    # Child ignores SIGTERM, forcing macode-run to escalate to SIGKILL
    set +e
    "$MACODE_RUN" "$task_id" --timeout 1 -- bash -c "trap '' TERM; sleep 100"
    local macode_exit=$?
    set -e

    LAST_ASSERT_OK=1
    if [[ "$macode_exit" -ne 0 ]]; then
        LAST_ASSERT_OK=0
    else
        echo -e "${FAIL_COLOR}[FAIL]${RESET} expected non-zero exit on SIGKILL at ${CURRENT_TEST:-unknown}"
        test_end
        return 1
    fi

    assert_file_exists "$state_path"
    assert_state_json "$state_path" "timeout"

    test_end
}

# ---------------------------------------------------------------------------
# Signal forwarding
# ---------------------------------------------------------------------------

test_macode_run_signal_forwarding() {
    test_start "test_macode_run_signal_forwarding"

    local task_id="test_signal_$$"
    local state_path="$PROJECT_ROOT/.agent/tmp/$task_id/state.json"
    local log_file="$PROJECT_ROOT/.agent/log/${task_id}_signal.log"
    _cleanup_macode_run "$task_id"

    # Start macode-run in background; child catches SIGTERM via Python (sleep is interruptible)
    # Child exits with code 1 when signal arrives, so we can verify macode-run propagates it.
    "$MACODE_RUN" "$task_id" --log "$log_file" -- python3 -c \
        'import signal, sys, time; signal.signal(signal.SIGTERM, lambda s,f: (print("SIGNAL_CAUGHT_TERM"), sys.exit(1))); time.sleep(100)' &
    local bg_pid=$!

    # Wait for child to start and state to be written
    sleep 0.5

    # Send SIGTERM to macode-run itself
    kill -TERM "$bg_pid" 2>/dev/null || true

    # Wait for macode-run to finish (with outer timeout guard)
    set +e
    wait "$bg_pid"
    local macode_exit=$?
    set -e

    # Child was terminated by forwarded signal (exit 1); macode-run should also exit 1.
    # child_terminated flag prevents status from becoming "failed".
    LAST_ASSERT_OK=1
    if [[ "$macode_exit" -eq 1 ]]; then
        LAST_ASSERT_OK=0
    else
        echo -e "${FAIL_COLOR}[FAIL]${RESET} expected exit 1, got $macode_exit at ${CURRENT_TEST:-unknown}"
        test_end
        return 1
    fi

    # Verify child actually received the signal by checking log
    LAST_ASSERT_OK=1
    if grep -q "SIGNAL_CAUGHT_TERM" "$log_file"; then
        LAST_ASSERT_OK=0
    else
        echo -e "${FAIL_COLOR}[FAIL]${RESET} expected SIGNAL_CAUGHT_TERM in log at ${CURRENT_TEST:-unknown}"
        test_end
        return 1
    fi

    test_end
}

# ---------------------------------------------------------------------------
# Options: --no-state, log capture, env var
# ---------------------------------------------------------------------------

test_macode_run_no_state() {
    test_start "test_macode_run_no_state"

    local task_id="test_nostate_$$"
    local state_path="$PROJECT_ROOT/.agent/tmp/$task_id/state.json"
    _cleanup_macode_run "$task_id"

    "$MACODE_RUN" "$task_id" --no-state -- bash -c "echo hello"
    assert_exit_code 0

    LAST_ASSERT_OK=1
    if [[ ! -f "$state_path" ]]; then
        LAST_ASSERT_OK=0
    else
        echo -e "${FAIL_COLOR}[FAIL]${RESET} expected no state.json with --no-state at ${CURRENT_TEST:-unknown}"
        test_end
        return 1
    fi

    test_end
}

test_macode_run_log_capture() {
    test_start "test_macode_run_log_capture"

    local task_id="test_log_$$"
    local log_file="$PROJECT_ROOT/.agent/log/${task_id}_capture.log"
    _cleanup_macode_run "$task_id"
    rm -f "$log_file"

    "$MACODE_RUN" "$task_id" --log "$log_file" -- bash -c \
        'echo STDOUT_LINE; echo STDERR_LINE >&2'
    assert_exit_code 0

    assert_file_exists "$log_file"

    LAST_ASSERT_OK=1
    if grep -q "STDOUT_LINE" "$log_file" && grep -q "STDERR_LINE" "$log_file"; then
        LAST_ASSERT_OK=0
    else
        echo -e "${FAIL_COLOR}[FAIL]${RESET} expected both stdout and stderr in log at ${CURRENT_TEST:-unknown}"
        test_end
        return 1
    fi

    test_end
}

test_macode_run_env_var_passed() {
    test_start "test_macode_run_env_var_passed"

    local task_id="test_env_$$"
    local log_file="$PROJECT_ROOT/.agent/log/${task_id}_env.log"
    _cleanup_macode_run "$task_id"
    rm -f "$log_file"

    "$MACODE_RUN" "$task_id" --log "$log_file" -- bash -c 'echo "STATE_DIR=$MACODE_STATE_DIR"'
    assert_exit_code 0

    assert_file_exists "$log_file"

    # MACODE_STATE_DIR is set as a relative path by macode-run
    local expected_path
    expected_path=".agent/tmp/$task_id"
    LAST_ASSERT_OK=1
    if grep -q "STATE_DIR=$expected_path" "$log_file"; then
        LAST_ASSERT_OK=0
    else
        echo -e "${FAIL_COLOR}[FAIL]${RESET} expected MACODE_STATE_DIR=$expected_path in log at ${CURRENT_TEST:-unknown}"
        test_end
        return 1
    fi

    test_end
}

test_macode_run_missing_cmd() {
    test_start "test_macode_run_missing_cmd"

    set +e
    "$MACODE_RUN" "test_nocmd_$$" --no-state 2>/dev/null
    local macode_exit=$?
    set -e

    LAST_ASSERT_OK=1
    if [[ "$macode_exit" -ne 0 ]]; then
        LAST_ASSERT_OK=0
    else
        echo -e "${FAIL_COLOR}[FAIL]${RESET} expected non-zero exit when missing command at ${CURRENT_TEST:-unknown}"
        test_end
        return 1
    fi

    test_end
}
