#!/usr/bin/env bash
set -euo pipefail

# bin/agent-run.sh
# Git 原子操作包装器。
#
# 用法: agent-run.sh "<command>"
#   任务前: git stash + git checkout -b agent/<task_id>
#   任务后: 成功 → git commit + merge --no-ff
#           失败 → git checkout - + git branch -D（自动回滚）

COMMAND="${1:-}"
if [[ -z "$COMMAND" ]]; then
    echo "Usage: $0 '\lt;command\gt;'" >&2
    exit 1
fi

# 生成任务 ID
TASK_ID="agent_$(date +%Y%m%d_%H%M%S)_$(printf '%04x' $RANDOM)"
BRANCH="agent/$TASK_ID"

echo "[agent] Task ID: $TASK_ID"

# 检查 git 状态
if ! git rev-parse --git-dir >/dev/null 2>&1; then
    echo "[agent] Error: not a git repository" >&2
    exit 1
fi

# 检查是否有未提交的更改
NEED_STASH=false
if ! git diff --quiet 2>/dev/null || ! git diff --cached --quiet 2>/dev/null; then
    NEED_STASH=true
fi

# 1. 保存当前状态
if [[ "$NEED_STASH" == true ]]; then
    echo "[agent] Stashing current changes..."
    git stash push -m "pre-task-$TASK_ID" >/dev/null
fi

# 2. 创建任务分支
echo "[agent] Creating branch $BRANCH..."
git checkout -b "$BRANCH" >/dev/null

# 3. 运行命令
echo "[agent] Running: $COMMAND"
set +e
bash -c "$COMMAND"
EXIT_CODE=$?
set -e

# 4. 处理结果
if [[ "$EXIT_CODE" -eq 0 ]]; then
    echo "[agent] Command succeeded. Committing..."

    # 检查是否有变更要提交（包括 untracked 文件）
    if ! git diff --quiet 2>/dev/null || ! git diff --cached --quiet 2>/dev/null || [[ -n $(git status --short 2>/dev/null) ]]; then
        git add -A
        git commit -m "agent: $TASK_ID — $COMMAND" >/dev/null
    fi

    # 合并回主分支
    git checkout - >/dev/null
    git merge --no-ff "$BRANCH" -m "merge: $TASK_ID — $COMMAND" >/dev/null
    git branch -d "$BRANCH" >/dev/null

    echo "[agent] Done. Merged to $(git branch --show-current)."
else
    echo "[agent] Command failed with exit code $EXIT_CODE. Auto-rollback..."

    # 回到原分支
    git checkout - >/dev/null

    # 删除失败的任务分支
    git branch -D "$BRANCH" >/dev/null 2>&1 || true

    # 恢复 stash
    if [[ "$NEED_STASH" == true ]]; then
        git stash pop >/dev/null
    fi

    echo "[agent] State restored to pre-task."
    exit "$EXIT_CODE"
fi
