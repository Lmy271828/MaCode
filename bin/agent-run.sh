#!/usr/bin/env bash
set -euo pipefail

# bin/agent-run.sh
# Git 原子操作包装器。

if [[ "${1:-}" == "--help" || "${1:-}" == "-h" ]]; then
    cat <<'EOF'
Usage: agent-run.sh <scene_dir> <command> [args...]

Git atomic-operation wrapper for scene rendering.
Ensures clean git state before rendering.
  Success → git commit (record changes)
  Failure → git checkout -- + git clean -f (clean untracked artifacts)

Arguments:
  <scene_dir>   Scene directory, e.g. scenes/01_test/
  <command>     Command to run (e.g. bash pipeline/render.sh)
  [args...]     Additional arguments passed to <command>

Examples:
  agent-run.sh scenes/01_test bash pipeline/render.sh scenes/01_test
EOF
    exit 0
fi

SCENE="${1:-}"
shift 2>/dev/null || true

if [[ -z "${1:-}" ]]; then
    echo "Usage: $0 <scene_dir> <command> [args...]" >&2
    exit 1
fi

COMMAND="$1"
shift 2>/dev/null || true

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

if ! git rev-parse --git-dir >/dev/null 2>&1; then
    echo "[agent-run] Not a git repository, running without safety net"
    exec "$COMMAND" "$@"
fi

SCENE_NAME=$(basename "${SCENE%/}")

# 确认场景文件在 git 跟踪中（或至少存在）
if [[ ! -f "$SCENE/scene.py" ]] && [[ ! -f "$SCENE/scene.tsx" ]]; then
    echo "[agent-run] No scene file found in $SCENE" >&2
    exit 1
fi

echo "[agent-run] Scene: $SCENE_NAME"

# 运行命令
set +e
"$COMMAND" "$@"
EXIT_CODE=$?
set -e

if [[ $EXIT_CODE -eq 0 ]]; then
    echo "[agent-run] Success"

    # 只提交 scenes/ 和 .agent/ 下的变更
    if ! git diff --quiet -- "$SCENE" 2>/dev/null || \
       ! git diff --cached --quiet -- "$SCENE" 2>/dev/null || \
       [[ -n $(git ls-files --others --exclude-standard -- "$SCENE" 2>/dev/null) ]]; then
        GIT_LOCK_FILE="$PROJECT_ROOT/.agent/.git_lock"
        mkdir -p "$(dirname "$GIT_LOCK_FILE")"
        (
            flock -x 200 || exit 1
            git add "$SCENE"
            git commit -m "agent: render $SCENE_NAME — success" 2>/dev/null || true
        ) 200>"$GIT_LOCK_FILE"
    fi
else
    echo "[agent-run] Failed (exit $EXIT_CODE). Rolling back scene changes..."
    # 回滚场景源码变更，但保留日志和帧用于调试
    git checkout -- "$SCENE" 2>/dev/null || true
    git clean -fd "$SCENE" 2>/dev/null || true
    exit $EXIT_CODE
fi
