#!/usr/bin/env bash
set -euo pipefail

# bin/agent-run.sh
# Git 原子操作包装器。
#
# 用法: agent-run.sh <scene_dir> <command> [args...]
#   渲染场景前确保 git 状态干净可回滚。
#   成功 → git commit（记录变更）
#   失败 → git checkout -- + git clean -f（仅清理未追踪的渲染产物）

SCENE="${1:-}"
shift 2>/dev/null || true

if [[ -z "${1:-}" ]]; then
    echo "Usage: $0 <scene_dir> <command> [args...]" >&2
    exit 1
fi

COMMAND="$1"
shift 2>/dev/null || true

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
        git add "$SCENE"
        git commit -m "agent: render $SCENE_NAME — success" 2>/dev/null || true
    fi
else
    echo "[agent-run] Failed (exit $EXIT_CODE). Rolling back scene changes..."
    # 回滚场景源码变更，但保留日志和帧用于调试
    git checkout -- "$SCENE" 2>/dev/null || true
    git clean -fd "$SCENE" 2>/dev/null || true
    exit $EXIT_CODE
fi
