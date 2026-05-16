#!/usr/bin/env bash
set -euo pipefail

# macode-status.sh — Project status reporter for macode CLI.
# Usage: macode-status.sh [project_name] [project_root]

PROJECT_NAME="${1:-MaCode}"
PROJECT_ROOT="${2:-$(cd "$(dirname "$0")/.." && pwd)}"

cd "$PROJECT_ROOT"

echo "Project: $PROJECT_NAME"

DEFAULT_ENGINE=""
if [[ -f "$PROJECT_ROOT/project.yaml" ]]; then
    DEFAULT_ENGINE=$(grep "engine:" "$PROJECT_ROOT/project.yaml" | head -1 | sed 's/.*engine:[[:space:]]*//' | xargs)
fi
echo "Default engine: ${DEFAULT_ENGINE:-?}"
echo ""

# 统计场景
SCENE_COUNT=$(find scenes -maxdepth 1 -mindepth 1 -type d 2>/dev/null | wc -l)
echo "Scenes: $SCENE_COUNT"
if [[ "$SCENE_COUNT" -gt 0 ]]; then
    for scene_dir in $(find scenes -maxdepth 1 -mindepth 1 -type d | sort); do
        scene_name=$(basename "$scene_dir")
        manifest="$scene_dir/manifest.json"
        if [[ -f "$manifest" ]]; then
            engine=$(grep -o '"engine"[[:space:]]*:[[:space:]]*"[^"]*"' "$manifest" 2>/dev/null | sed 's/.*"engine"[[:space:]]*:[[:space:]]*"\([^"]*\)".*/\1/' || echo "?")
            dirty=""
            if git diff --quiet -- "$scene_dir" 2>/dev/null; then
                :
            else
                dirty=" (dirty)"
            fi
            echo "  - $scene_name [$engine]$dirty"
        fi
    done
fi
echo ""

# SOURCEMAP 健康状态
echo "SOURCEMAP health:"
if [[ -f "$PROJECT_ROOT/bin/sourcemap-version-check.py" ]]; then
    python3 "$PROJECT_ROOT/bin/sourcemap-version-check.py" --all 2>&1 | sed 's/^/  /'
else
    echo "  ~ sourcemap-version-check.py not found"
fi
echo ""

# 上次渲染
LAST_RENDER=$(find .agent/tmp -name "final.mp4" -type f 2>/dev/null | sort | tail -1)
if [[ -n "$LAST_RENDER" ]]; then
    scene_name=$(basename "$(dirname "$LAST_RENDER")")
    duration=$(ffprobe -v error -show_entries format=duration -of default=noprint_wrappers=1:nokey=1 "$LAST_RENDER" 2>/dev/null || echo "?")
    echo "Last render: $scene_name — ${duration}s"
else
    echo "Last render: none"
fi

echo ""
# Git 状态
if git rev-parse --git-dir >/dev/null 2>&1; then
    BRANCH=$(git branch --show-current 2>/dev/null || echo "?")
    COMMITS=$(git rev-list --count HEAD 2>/dev/null || echo "0")
    echo "Git branch: $BRANCH ($COMMITS commits)"
    if ! git diff --quiet 2>/dev/null; then
        echo "Uncommitted changes: yes"
    fi
fi
