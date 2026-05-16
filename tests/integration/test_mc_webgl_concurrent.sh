#!/usr/bin/env bash
set -euo pipefail

# tests/integration/test_mc_webgl_concurrent.sh
# Integration test: concurrent Motion Canvas scene rendering with WebGL shaders.
#
# Verifies that multiple MC scenes can render simultaneously without WebGL
# context conflicts, and that ShaderFrame's real-time WebGL rendering produces
# valid output frames.

source "$(dirname "${BASH_SOURCE[0]}")/lib.sh"

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
RENDER_SCENE="$PROJECT_ROOT/pipeline/render-scene.py"

_cleanup() {
    rm -rf "$PROJECT_ROOT/.agent/tmp/test_mc_webgl_1"
    rm -rf "$PROJECT_ROOT/.agent/tmp/test_mc_webgl_2"
    rm -f "$PROJECT_ROOT/.agent/log/"*"_test_mc_webgl_"*.log
}

test_single_mc_webgl_render() {
    test_start "test_single_mc_webgl_render"

    _cleanup

    # Render 02_shader_mc with low quality for speed
    python3 "$RENDER_SCENE" "$PROJECT_ROOT/scenes/02_shader_mc" \
        --fps 2 --duration 1 --width 640 --height 360 \
        2>&1 | tee /tmp/test_mc_webgl_single.log

    assert_exit_code 0

    # Verify frames exist
    local frames_dir="$PROJECT_ROOT/.agent/tmp/02_shader_mc/frames"
    assert_file_exists "$frames_dir/frame_0001.png"
    assert_file_exists "$frames_dir/frame_0002.png"

    # Verify frames are non-empty ( > 1KB )
    local frame1_size
    frame1_size=$(stat -c%s "$frames_dir/frame_0001.png")
    if [[ "$frame1_size" -lt 1000 ]]; then
        echo "FAIL: frame_0001.png too small (${frame1_size} bytes)" >&2
        exit 1
    fi

    # Verify final MP4
    assert_file_exists "$PROJECT_ROOT/.agent/tmp/02_shader_mc/final.mp4"

    test_end
}

test_concurrent_mc_webgl_render() {
    test_start "test_concurrent_mc_webgl_render"

    _cleanup

    # Copy scene to two temp directories for concurrent rendering
    mkdir -p "$PROJECT_ROOT/.agent/tmp/test_mc_webgl_1"
    mkdir -p "$PROJECT_ROOT/.agent/tmp/test_mc_webgl_2"
    cp -r "$PROJECT_ROOT/scenes/02_shader_mc/"* "$PROJECT_ROOT/.agent/tmp/test_mc_webgl_1/"
    cp -r "$PROJECT_ROOT/scenes/02_shader_mc/"* "$PROJECT_ROOT/.agent/tmp/test_mc_webgl_2/"

    # Render both concurrently in background
    python3 "$RENDER_SCENE" "$PROJECT_ROOT/.agent/tmp/test_mc_webgl_1" \
        --fps 2 --duration 1 --width 640 --height 360 \
        > /tmp/test_mc_webgl_c1.log 2>&1 &
    local pid1=$!

    python3 "$RENDER_SCENE" "$PROJECT_ROOT/.agent/tmp/test_mc_webgl_2" \
        --fps 2 --duration 1 --width 640 --height 360 \
        > /tmp/test_mc_webgl_c2.log 2>&1 &
    local pid2=$!

    # Wait for both
    local exit1=0 exit2=0
    wait "$pid1" || exit1=$?
    wait "$pid2" || exit2=$?

    if [[ "$exit1" -ne 0 ]]; then
        echo "FAIL: First concurrent render failed (exit $exit1)" >&2
        cat /tmp/test_mc_webgl_c1.log >&2
        exit 1
    fi
    if [[ "$exit2" -ne 0 ]]; then
        echo "FAIL: Second concurrent render failed (exit $exit2)" >&2
        cat /tmp/test_mc_webgl_c2.log >&2
        exit 1
    fi

    # Verify both outputs
    assert_file_exists "$PROJECT_ROOT/.agent/tmp/test_mc_webgl_1/frames/frame_0001.png"
    assert_file_exists "$PROJECT_ROOT/.agent/tmp/test_mc_webgl_2/frames/frame_0001.png"
    assert_file_exists "$PROJECT_ROOT/.agent/tmp/test_mc_webgl_1/final.mp4"
    assert_file_exists "$PROJECT_ROOT/.agent/tmp/test_mc_webgl_2/final.mp4"

    test_end
}

test_mc_webgl_no_shader_prepare() {
    test_start "test_mc_webgl_no_shader_prepare"

    # Verify that shader-prepare.mjs is NOT called during MC render
    # by checking the render log for absence of [shader-prepare]
    _cleanup

    python3 "$RENDER_SCENE" "$PROJECT_ROOT/scenes/02_shader_mc" \
        --fps 2 --duration 1 --width 640 --height 360 \
        > /tmp/test_mc_webgl_noprerep.log 2>&1

    assert_exit_code 0

    if grep -q "shader-prepare" /tmp/test_mc_webgl_noprerep.log; then
        echo "FAIL: shader-prepare.mjs was called (should be removed from pipeline)" >&2
        exit 1
    fi

    test_end
}

# Run all tests
test_single_mc_webgl_render
test_concurrent_mc_webgl_render
test_mc_webgl_no_shader_prepare

echo ""
echo "All MC WebGL concurrent tests passed."
