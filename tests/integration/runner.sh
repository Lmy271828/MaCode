#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
LIB_PATH="$PROJECT_ROOT/tests/integration/lib.sh"
source "$LIB_PATH"

# Defaults
VERBOSE=0
PATTERN=""
FAIL_FAST=0
REPORT_PATH=""

while [[ $# -gt 0 ]]; do
    case "$1" in
        --verbose)
            VERBOSE=1
            shift
            ;;
        -k)
            PATTERN="$2"
            shift 2
            ;;
        --fail-fast)
            FAIL_FAST=1
            shift
            ;;
        --report)
            REPORT_PATH="$2"
            shift 2
            ;;
        *)
            echo "Unknown option: $1"
            exit 1
            ;;
    esac
done

# Counters
TOTAL_PASSED=0
TOTAL_FAILED=0
TOTAL_SKIPPED=0
TOTAL_RUN=0

declare -a TEST_NAMES=()
declare -a TEST_STATUSES=()
declare -a TEST_DURATIONS=()
declare -a TEST_ERRORS=()

run_test() {
    local func="$1"
    local file="$2"
    local start_time end_time duration_ms status error_msg result

    status="passed"
    error_msg=""
    start_time="$(date +%s%3N 2>/dev/null || echo "0")"

    if [[ "$VERBOSE" -eq 1 ]]; then
        (
            set +e
            "$func"
        )
    else
        (
            set +e
            "$func" >/dev/null 2>&1
        )
    fi
    result=$?

    end_time="$(date +%s%3N 2>/dev/null || echo "0")"
    duration_ms=$(( end_time - start_time ))

    if [[ "$result" -ne 0 ]]; then
        status="failed"
        error_msg="Test function returned non-zero or assertion failed"
        if [[ "$VERBOSE" -eq 0 ]]; then
            echo -e "${FAIL_COLOR}[FAIL]${RESET} $func (re-run with --verbose for output)"
        fi
    fi

    TEST_NAMES+=("$func")
    TEST_STATUSES+=("$status")
    TEST_DURATIONS+=("$duration_ms")
    TEST_ERRORS+=("$error_msg")

    if [[ "$result" -eq 0 ]]; then
        TOTAL_PASSED=$((TOTAL_PASSED + 1))
    else
        TOTAL_FAILED=$((TOTAL_FAILED + 1))
    fi
    TOTAL_RUN=$((TOTAL_RUN + 1))

    if [[ "$status" == "failed" && "$FAIL_FAST" -eq 1 ]]; then
        echo -e "${FAIL_COLOR}[FAIL-FAST]${RESET} Stopping on first failure."
        return 1
    fi
    return 0
}

# Collect and run
for test_file in "$PROJECT_ROOT"/tests/integration/test_*.sh; do
    [[ -e "$test_file" ]] || continue
    source "$test_file"
    local_funcs="$(grep -oE '^test_[a-zA-Z0-9_]+\(\)' "$test_file" | sed 's/()//')"
    for func in $local_funcs; do
        if [[ -n "$PATTERN" && ! "$func" == *"$PATTERN"* ]]; then
            TOTAL_SKIPPED=$((TOTAL_SKIPPED + 1))
            continue
        fi
        if ! run_test "$func" "$test_file"; then
            break 2
        fi
    done
done

# Summary
echo ""
echo "========================================"
echo "  INTEGRATION TEST SUMMARY"
echo "========================================"
echo -e "  ${PASS_COLOR}Passed:${RESET}  $TOTAL_PASSED"
echo -e "  ${FAIL_COLOR}Failed:${RESET}  $TOTAL_FAILED"
echo -e "  ${SKIP_COLOR}Skipped:${RESET} $TOTAL_SKIPPED"
echo "========================================"

# Report
TIMESTAMP="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
DEFAULT_REPORT_DIR="$PROJECT_ROOT/.agent/test_reports"
mkdir -p "$DEFAULT_REPORT_DIR"
if [[ -z "$REPORT_PATH" ]]; then
    REPORT_PATH="$DEFAULT_REPORT_DIR/integration-$(date +%Y%m%d_%H%M%S).json"
fi
mkdir -p "$(dirname "$REPORT_PATH")"

{
    echo "{"
    echo "  \"suite\": \"integration\","
    echo "  \"timestamp\": \"$TIMESTAMP\","
    echo "  \"total\": $TOTAL_RUN,"
    echo "  \"passed\": $TOTAL_PASSED,"
    echo "  \"failed\": $TOTAL_FAILED,"
    echo "  \"skipped\": $TOTAL_SKIPPED,"
    echo "  \"tests\": ["
    count="${#TEST_NAMES[@]}"
    for i in "${!TEST_NAMES[@]}"; do
        name="${TEST_NAMES[$i]}"
        st="${TEST_STATUSES[$i]}"
        dur="${TEST_DURATIONS[$i]}"
        err="${TEST_ERRORS[$i]}"
        if [[ -n "$err" ]]; then
            echo -n "    { \"name\": \"$name\", \"status\": \"$st\", \"duration_ms\": $dur, \"error\": \"$err\" }"
        else
            echo -n "    { \"name\": \"$name\", \"status\": \"$st\", \"duration_ms\": $dur }"
        fi
        if [[ $i -lt $(( count - 1 )) ]]; then
            echo ","
        else
            echo ""
        fi
    done
    echo "  ]"
    echo "}"
} > "$REPORT_PATH"

echo "Report written to: $REPORT_PATH"

if [[ "$TOTAL_FAILED" -gt 0 ]]; then
    exit 1
fi
exit 0
