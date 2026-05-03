#!/usr/bin/env bash
set -euo pipefail

# bin/safety-gate.sh
# 命令白名单拦截器。
#
# 用法: safety-gate.sh "<bash_command>"
#   解析命令，检查是否只使用了白名单中的工具。
#   如果包含非白名单工具或匹配阻塞模式，拒绝执行。

COMMAND="${1:-}"
if [[ -z "$COMMAND" ]]; then
    echo "Usage: $0 '\lt;bash_command\gt;'" >&2
    exit 1
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

# 加载白名单和阻塞模式（从 project.yaml）
ALLOWED_COMMANDS=()
BLOCKED_PATTERNS=()

if [[ -f "$PROJECT_ROOT/project.yaml" ]]; then
    if command -v yq >/dev/null 2>&1; then
        # 使用 yq 读取
        while IFS= read -r cmd; do
            ALLOWED_COMMANDS+=("$cmd")
        done < <(yq -r '.agent.allowed_commands[]' "$PROJECT_ROOT/project.yaml" 2>/dev/null || true)

        while IFS= read -r pat; do
            BLOCKED_PATTERNS+=("$pat")
        done < <(yq -r '.agent.blocked_patterns[]' "$PROJECT_ROOT/project.yaml" 2>/dev/null || true)
    fi
fi

# 默认白名单（如果 project.yaml 未配置）
if [[ ${#ALLOWED_COMMANDS[@]} -eq 0 ]]; then
    ALLOWED_COMMANDS=(
        manim ffmpeg ffprobe jq yq git find grep sed awk just
        du df cat ls cp mv rm mkdir touch python3 node npm npx
        bash echo tee tail head wc dirname basename pwd date
        sort uniq xargs chmod test '[' '[[', printf read
    )
fi

# 默认阻塞模式
if [[ ${#BLOCKED_PATTERNS[@]} -eq 0 ]]; then
    BLOCKED_PATTERNS=(
        'rm -rf /'
        'rm -rf ~'
        'curl|wget'
        'eval|exec|bash -c'
        'pip install'
        'npm install'
        'sudo|su -'
    )
fi

# 提取命令中的工具名
# 简单解析：提取命令字符串中的每个单词，检查是否在白名单中
ERRORS=()

# 检查阻塞模式
for pattern in "${BLOCKED_PATTERNS[@]}"; do
    if echo "$COMMAND" | grep -qiE "$pattern"; then
        ERRORS+=("Blocked pattern matched: '$pattern'")
    fi
done

# 检查命令白名单
# 提取所有看起来像命令的词（不在引号内、不是参数）
# 简化版本：提取所有独立单词，排除明显的参数和路径
WORDS=$(echo "$COMMAND" | tr ';|&<>(){}$`' '\n' | tr -s ' ' '\n' | sed 's/^ *//;s/ *$//')

for word in $WORDS; do
    # 跳过空字符串、参数、路径、变量
    if [[ -z "$word" ]]; then
        continue
    fi
    # 跳过以 - 开头的选项
    if [[ "$word" == -* ]]; then
        continue
    fi
    # 跳过路径
    if [[ "$word" == */* ]]; then
        continue
    fi
    # 跳过文件/URL（包含 . 但不是赋值）
    if [[ "$word" == *.* ]] && [[ "$word" != *=* ]]; then
        continue
    fi
    # 跳过变量
    if [[ "$word" == \$* ]]; then
        continue
    fi
    # 跳过数字
    if [[ "$word" =~ ^[0-9]+$ ]]; then
        continue
    fi
    # 跳过字符串常量（简单判断）
    if [[ "$word" == \"* ]] || [[ "$word" == \'* ]] || [[ "$word" == *\" ]] || [[ "$word" == *\' ]]; then
        continue
    fi
    # 跳过已知的 shell 关键字和结构
    case "$word" in
        if|then|else|elif|fi|for|while|do|done|case|esac|in|\
        shift|exit|return|continue|break|source|.)
            continue
            ;;
    esac

    # 检查是否在白名单中
    FOUND=false
    for allowed in "${ALLOWED_COMMANDS[@]}"; do
        if [[ "$word" == "$allowed" ]]; then
            FOUND=true
            break
        fi
    done

    if [[ "$FOUND" == false ]]; then
        # 检查是否是赋值语句（KEY=value）
        if [[ "$word" == *=* ]]; then
            continue
        fi
        ERRORS+=("Command not in whitelist: '$word'")
    fi
done

# 输出结果
if [[ ${#ERRORS[@]} -gt 0 ]]; then
    echo "[safety-gate] REJECTED" >&2
    for err in "${ERRORS[@]}"; do
        echo "  - $err" >&2
    done
    exit 1
fi

echo "[safety-gate] ALLOWED"
