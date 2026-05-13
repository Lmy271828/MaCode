#!/usr/bin/env bash
set -euo pipefail

source "$(dirname "$0")/lib.sh"

PROJECT_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"

# Skip all MC tests if Chromium is not available
_has_chromium() {
    command -v chromium-browser >/dev/null 2>&1 || \
    command -v chromium >/dev/null 2>&1 || \
    command -v google-chrome >/dev/null 2>&1 || \
    [[ -n "${PUPPETEER_EXECUTABLE_PATH:-}" ]] || \
    # Playwright downloads its own Chromium to ~/.cache/ms-playwright/
    ls /home/*/.cache/ms-playwright/chromium-*/chrome-linux*/chrome >/dev/null 2>&1 || \
    ls /root/.cache/ms-playwright/chromium-*/chrome-linux*/chrome >/dev/null 2>&1
}

if ! _has_chromium; then
    echo -e "${SKIP_COLOR}[SKIP]${RESET} Chromium not available, skipping all Motion Canvas tests"
fi

test_mc_single_render() {
    if ! _has_chromium; then
        test_start "test_mc_single_render"
        echo -e "${SKIP_COLOR}[SKIP]${RESET} Chromium not available"
        LAST_ASSERT_OK=0
        test_end
        return 0
    fi
    test_start "test_mc_single_render"

    cd "$PROJECT_ROOT"
    ./bin/macode render scenes/01_test_mc --fps 2 --duration 1 >/dev/null 2>&1
    assert_exit_code 0

    assert_file_exists ".agent/tmp/01_test_mc/frames/frame_0001.png"
    assert_file_not_empty ".agent/tmp/01_test_mc/frames/frame_0001.png"

    # MC engine (render-cli.mjs) does not use macode-run, so state.json is not created
    # assert_state_json is skipped for MC. Progress jsonl is written by render-cli.mjs.
    assert_progress_phases ".agent/progress/01_test_mc.jsonl" "init" "serve" "capture" "cleanup"

    assert_frame_count ".agent/tmp/01_test_mc/frames/" 2 1

    test_end
}

test_mc_dev_server_lifecycle() {
    if ! _has_chromium; then
        test_start "test_mc_dev_server_lifecycle"
        echo -e "${SKIP_COLOR}[SKIP]${RESET} Chromium not available"
        LAST_ASSERT_OK=0
        test_end
        return 0
    fi
    test_start "test_mc_dev_server_lifecycle"

    cd "$PROJECT_ROOT"

    local_cleanup() {
        ./bin/macode mc stop scenes/01_test_mc >/dev/null 2>&1 || true
        cleanup_tmp
    }
    trap local_cleanup EXIT

    timeout 10 ./bin/macode mc serve scenes/01_test_mc >/dev/null 2>&1 &
    local bg_pid=$!

    sleep 3

    assert_file_exists ".agent/tmp/01_test_mc/state.json"

    local port
    port="$(python3 -c "import json,sys; d=json.load(open('.agent/tmp/01_test_mc/state.json')); print(d.get('outputs',{}).get('port',''))" 2>/dev/null || true)"
    if [[ -z "$port" || "$port" == "null" ]]; then
        echo -e "${FAIL_COLOR}[FAIL]${RESET} assert: expected valid port in state.json at ${CURRENT_TEST:-unknown}"
        LAST_ASSERT_OK=1
        test_end
        return 1
    fi
    LAST_ASSERT_OK=0

    curl -s "http://localhost:${port}/" > /dev/null
    assert_exit_code 0

    ./bin/macode mc stop scenes/01_test_mc >/dev/null 2>&1

    sleep 2

    if curl -s "http://localhost:${port}/" > /dev/null 2>&1; then
        echo -e "${FAIL_COLOR}[FAIL]${RESET} assert: expected port $port to be closed at ${CURRENT_TEST:-unknown}"
        LAST_ASSERT_OK=1
        test_end
        return 1
    fi
    LAST_ASSERT_OK=0

    # Restore original trap since we already stopped the server
    trap cleanup_tmp EXIT

    test_end
}

test_mc_shaderframe() {
    if ! _has_chromium; then
        test_start "test_mc_shaderframe"
        echo -e "${SKIP_COLOR}[SKIP]${RESET} Chromium not available"
        LAST_ASSERT_OK=0
        test_end
        return 0
    fi
    test_start "test_mc_shaderframe"

    cd "$PROJECT_ROOT"

    if [[ ! -d "scenes/02_shader_mc" ]]; then
        echo -e "${SKIP_COLOR}[SKIP]${RESET} scenes/02_shader_mc does not exist, skipping test"
        LAST_ASSERT_OK=0
        test_end
        return 0
    fi

    local shader_id
    shader_id="$(python3 -c "import json,sys; d=json.load(open('scenes/02_shader_mc/manifest.json')); print(d.get('shaders',[''])[0])" 2>/dev/null || true)"
    if [[ -n "$shader_id" && ! -d "assets/shaders/$shader_id" ]]; then
        echo -e "${SKIP_COLOR}[SKIP]${RESET} shader asset '$shader_id' missing, skipping test"
        LAST_ASSERT_OK=0
        test_end
        return 0
    fi

    ./bin/macode render scenes/02_shader_mc --fps 2 --duration 1 >/dev/null 2>&1
    assert_exit_code 0

    assert_frame_count ".agent/tmp/02_shader_mc/frames/" 2 1

    test_end
}
