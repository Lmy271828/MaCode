#!/usr/bin/env bash
set -euo pipefail

# Re-use smoke test assertions
PROJECT_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
source "$PROJECT_ROOT/tests/smoke/lib.sh"

# Integration-specific helpers

assert_exit_code() {
    local expected="$1"
    local actual="$?"
    LAST_ASSERT_OK=1
    if [[ "$actual" -eq "$expected" ]]; then
        LAST_ASSERT_OK=0
    else
        echo -e "${FAIL_COLOR}[FAIL]${RESET} assert_exit_code: expected $expected, got $actual at ${CURRENT_TEST:-unknown}"
        return 1
    fi
}

assert_dir_equals() {
    local dir_a="$1"
    local dir_b="$2"
    LAST_ASSERT_OK=1
    if diff -r "$dir_a" "$dir_b" >/dev/null 2>&1; then
        LAST_ASSERT_OK=0
    else
        echo -e "${FAIL_COLOR}[FAIL]${RESET} assert_dir_equals: directories differ at ${CURRENT_TEST:-unknown}"
        return 1
    fi
}

assert_key_stability() {
    local dir="$1"
    local key1 key2
    key1="$($PROJECT_ROOT/bin/cache-key.py "$dir")"
    key2="$($PROJECT_ROOT/bin/cache-key.py "$dir")"
    LAST_ASSERT_OK=1
    if [[ "$key1" == "$key2" ]]; then
        LAST_ASSERT_OK=0
    else
        echo -e "${FAIL_COLOR}[FAIL]${RESET} assert_key_stability: $key1 != $key2 at ${CURRENT_TEST:-unknown}"
        return 1
    fi
}

assert_key_changes() {
    local dir="$1"
    local old_key="$2"
    local new_key
    new_key="$($PROJECT_ROOT/bin/cache-key.py "$dir")"
    LAST_ASSERT_OK=1
    if [[ "$new_key" != "$old_key" ]]; then
        LAST_ASSERT_OK=0
    else
        echo -e "${FAIL_COLOR}[FAIL]${RESET} assert_key_changes: key unchanged ($new_key) at ${CURRENT_TEST:-unknown}"
        return 1
    fi
}

assert_key_unchanged() {
    local dir="$1"
    local old_key="$2"
    local new_key
    new_key="$($PROJECT_ROOT/bin/cache-key.py "$dir")"
    LAST_ASSERT_OK=1
    if [[ "$new_key" == "$old_key" ]]; then
        LAST_ASSERT_OK=0
    else
        echo -e "${FAIL_COLOR}[FAIL]${RESET} assert_key_unchanged: key changed ($old_key -> $new_key) at ${CURRENT_TEST:-unknown}"
        return 1
    fi
}
