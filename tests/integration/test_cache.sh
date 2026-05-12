#!/usr/bin/env bash
set -euo pipefail

source "$(dirname "$0")/lib.sh"

PROJECT_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
PYTHON="${PYTHON:-python3}"

# Temporary directories
tmp_scene=""
tmp_cache=""
tmp_dest=""

cleanup() {
    [[ -n "$tmp_scene" && -d "$tmp_scene" ]] && rm -rf "$tmp_scene"
    [[ -n "$tmp_cache" && -d "$tmp_cache" ]] && rm -rf "$tmp_cache"
    [[ -n "$tmp_dest" && -d "$tmp_dest" ]] && rm -rf "$tmp_dest"
    # Clean cache between tests to avoid key collisions
    rm -rf "$PROJECT_ROOT/.agent/cache"/*
}
trap cleanup EXIT

_make_scene_dir() {
    local dir="$1"
    mkdir -p "$dir"
    cat > "$dir/manifest.json" <<'EOF'
{"version": "1.0", "engine": "manim", "fps": 30, "duration": 1.0}
EOF
    echo "class TestScene: pass" > "$dir/scene.py"
    mkdir -p "$dir/assets"
    echo "body { color: black; }" > "$dir/assets/style.css"
}

# ---------------------------------------------------------------------------
# Cache key determinism
# ---------------------------------------------------------------------------

test_cache_key_idempotent() {
    test_start "test_cache_key_idempotent"

    tmp_scene="$(mktemp -d)"
    _make_scene_dir "$tmp_scene"

    assert_key_stability "$tmp_scene"

    test_end
}

test_cache_key_changes_on_source_edit() {
    test_start "test_cache_key_changes_on_source_edit"

    tmp_scene="$(mktemp -d)"
    _make_scene_dir "$tmp_scene"

    local old_key
    old_key="$($PROJECT_ROOT/bin/cache-key.py "$tmp_scene")"

    echo "class UpdatedScene: pass" > "$tmp_scene/scene.py"

    assert_key_changes "$tmp_scene" "$old_key"

    test_end
}

test_cache_key_changes_on_manifest_edit() {
    test_start "test_cache_key_changes_on_manifest_edit"

    tmp_scene="$(mktemp -d)"
    _make_scene_dir "$tmp_scene"

    local old_key
    old_key="$($PROJECT_ROOT/bin/cache-key.py "$tmp_scene")"

    cat > "$tmp_scene/manifest.json" <<'EOF'
{"version": "1.0", "engine": "manim", "fps": 60, "duration": 1.0}
EOF

    assert_key_changes "$tmp_scene" "$old_key"

    test_end
}

test_cache_key_unchanged_on_log_edit() {
    test_start "test_cache_key_unchanged_on_log_edit"

    tmp_scene="$(mktemp -d)"
    _make_scene_dir "$tmp_scene"

    local old_key
    old_key="$($PROJECT_ROOT/bin/cache-key.py "$tmp_scene")"

    echo "render output log" > "$tmp_scene/render.log"

    assert_key_unchanged "$tmp_scene" "$old_key"

    test_end
}

test_cache_key_unchanged_on_hidden_file() {
    test_start "test_cache_key_unchanged_on_hidden_file"

    tmp_scene="$(mktemp -d)"
    _make_scene_dir "$tmp_scene"

    local old_key
    old_key="$($PROJECT_ROOT/bin/cache-key.py "$tmp_scene")"

    echo "secret" > "$tmp_scene/.secret"

    assert_key_unchanged "$tmp_scene" "$old_key"

    test_end
}

test_cache_key_unchanged_on_excluded_dir() {
    test_start "test_cache_key_unchanged_on_excluded_dir"

    tmp_scene="$(mktemp -d)"
    _make_scene_dir "$tmp_scene"

    local old_key
    old_key="$($PROJECT_ROOT/bin/cache-key.py "$tmp_scene")"

    mkdir -p "$tmp_scene/__pycache__"
    echo "compiled" > "$tmp_scene/__pycache__/module.cpython-312.pyc"

    assert_key_unchanged "$tmp_scene" "$old_key"

    test_end
}

# ---------------------------------------------------------------------------
# Cache store / check / restore
# ---------------------------------------------------------------------------

test_cache_store_and_check_hit() {
    test_start "test_cache_store_and_check_hit"

    rm -rf "$PROJECT_ROOT/.agent/cache"/*

    tmp_scene="$(mktemp -d)"
    _make_scene_dir "$tmp_scene"

    local key
    key="$($PROJECT_ROOT/bin/cache-key.py "$tmp_scene")"

    # Before store: miss
    $PROJECT_ROOT/bin/cache-check.py "$key"
    local check_before=$?
    LAST_ASSERT_OK=1
    if [[ "$check_before" -ne 0 ]]; then
        LAST_ASSERT_OK=0
    else
        echo -e "${FAIL_COLOR}[FAIL]${RESET} expected cache miss before store at ${CURRENT_TEST:-unknown}"
        test_end
        return 1
    fi

    # Store
    $PROJECT_ROOT/bin/cache-store.py "$key" "$tmp_scene"
    assert_exit_code 0

    # After store: hit
    $PROJECT_ROOT/bin/cache-check.py "$key"
    assert_exit_code 0

    test_end
}

test_cache_restore_preserves_content() {
    test_start "test_cache_restore_preserves_content"

    tmp_scene="$(mktemp -d)"
    tmp_dest="$(mktemp -d)"
    _make_scene_dir "$tmp_scene"

    local key
    key="$($PROJECT_ROOT/bin/cache-key.py "$tmp_scene")"

    $PROJECT_ROOT/bin/cache-store.py "$key" "$tmp_scene"
    assert_exit_code 0

    $PROJECT_ROOT/bin/cache-restore.py "$key" "$tmp_dest"
    assert_exit_code 0

    assert_dir_equals "$tmp_scene" "$tmp_dest"

    test_end
}

test_cache_restore_overwrites_existing() {
    test_start "test_cache_restore_overwrites_existing"

    tmp_scene="$(mktemp -d)"
    tmp_dest="$(mktemp -d)"
    _make_scene_dir "$tmp_scene"

    # Pre-populate dest with different content
    echo "old content" > "$tmp_dest/scene.py"
    mkdir -p "$tmp_dest/assets"
    echo "old style" > "$tmp_dest/assets/style.css"

    local key
    key="$($PROJECT_ROOT/bin/cache-key.py "$tmp_scene")"

    $PROJECT_ROOT/bin/cache-store.py "$key" "$tmp_scene"
    assert_exit_code 0

    $PROJECT_ROOT/bin/cache-restore.py "$key" "$tmp_dest"
    assert_exit_code 0

    # After restore, dest should match source
    assert_dir_equals "$tmp_scene" "$tmp_dest"

    test_end
}

test_cache_store_overwrites_existing() {
    test_start "test_cache_store_overwrites_existing"

    tmp_scene="$(mktemp -d)"
    _make_scene_dir "$tmp_scene"

    local key
    key="$($PROJECT_ROOT/bin/cache-key.py "$tmp_scene")"

    # First store
    $PROJECT_ROOT/bin/cache-store.py "$key" "$tmp_scene"
    assert_exit_code 0

    # Modify source and store again
    echo "class UpdatedScene: pass" > "$tmp_scene/scene.py"
    $PROJECT_ROOT/bin/cache-store.py "$key" "$tmp_scene"
    assert_exit_code 0

    # Restore and verify updated content
    tmp_dest="$(mktemp -d)"
    $PROJECT_ROOT/bin/cache-restore.py "$key" "$tmp_dest"
    assert_exit_code 0

    # scene.py should have updated content
    LAST_ASSERT_OK=1
    if grep -q "UpdatedScene" "$tmp_dest/scene.py"; then
        LAST_ASSERT_OK=0
    else
        echo -e "${FAIL_COLOR}[FAIL]${RESET} expected updated scene.py after overwrite store at ${CURRENT_TEST:-unknown}"
        test_end
        return 1
    fi

    test_end
}

test_cache_miss() {
    test_start "test_cache_miss"

    local key="nonexistent_key_1234567890abcdef"

    $PROJECT_ROOT/bin/cache-check.py "$key"
    local code=$?

    LAST_ASSERT_OK=1
    if [[ "$code" -ne 0 ]]; then
        LAST_ASSERT_OK=0
    else
        echo -e "${FAIL_COLOR}[FAIL]${RESET} expected cache miss for nonexistent key at ${CURRENT_TEST:-unknown}"
        test_end
        return 1
    fi

    test_end
}

test_cache_full_cycle() {
    test_start "test_cache_full_cycle"

    rm -rf "$PROJECT_ROOT/.agent/cache"/*

    tmp_scene="$(mktemp -d)"
    tmp_dest="$(mktemp -d)"
    _make_scene_dir "$tmp_scene"

    local key
    key="$($PROJECT_ROOT/bin/cache-key.py "$tmp_scene")"

    # Step 1: miss
    $PROJECT_ROOT/bin/cache-check.py "$key"
    local code=$?
    LAST_ASSERT_OK=1
    if [[ "$code" -ne 0 ]]; then
        LAST_ASSERT_OK=0
    else
        echo -e "${FAIL_COLOR}[FAIL]${RESET} step 1 (miss) failed at ${CURRENT_TEST:-unknown}"
        test_end
        return 1
    fi

    # Step 2: store
    $PROJECT_ROOT/bin/cache-store.py "$key" "$tmp_scene"
    assert_exit_code 0

    # Step 3: hit
    $PROJECT_ROOT/bin/cache-check.py "$key"
    assert_exit_code 0

    # Step 4: restore
    $PROJECT_ROOT/bin/cache-restore.py "$key" "$tmp_dest"
    assert_exit_code 0

    # Step 5: verify
    assert_dir_equals "$tmp_scene" "$tmp_dest"

    test_end
}
