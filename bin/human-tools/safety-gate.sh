#!/usr/bin/env bash
set -euo pipefail

# bin/safety-gate.sh
# 命令白名单拦截器。

if [[ "${1:-}" == "--help" || "${1:-}" == "-h" ]]; then
    cat <<'EOF'
Usage: safety-gate.sh "<bash_command>"

Command whitelist interceptor. Parses a bash command and checks against allowed
tools and blocked patterns from project.yaml.

Arguments:
  <bash_command>   Command string to validate

Exit codes:
  0   Command allowed
  1   Command rejected or argument missing
EOF
    exit 0
fi

COMMAND="${1:-}"
if [[ -z "$COMMAND" ]]; then
    echo "Usage: $0 '<bash_command>'" >&2
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

# 默认阻塞模式（与 project.yaml 保持同步）
if [[ ${#BLOCKED_PATTERNS[@]} -eq 0 ]]; then
    BLOCKED_PATTERNS=(
        'rm -rf /'
        'rm -rf ~'
        'curl|wget'
        'eval|exec|bash -c'
        'pip install|pip3 install'
        'npm install|npm i '
        'sudo|su -'
        '> /dev/sda'
        'dd if='
        'cat .macode|cat .claude|cat .git/config'
        '\.macode/|\.claude/|\.git/config'
        'git push --force|git push -f|git push --delete'
        'git reset --hard'
        'git clean -f'
        'subprocess\.|os\.system\(|os\.popen\(|socket\.|requests\.|urllib\.'
        'shutil\.rmtree|shutil\.move|__import__\('
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
# 策略：按管道/分隔符拆分，每段取第一个词作为主命令，其余是参数
# 主命令必须在白名单中；参数不检查
SEGMENTS=$(echo "$COMMAND" | sed 's/[;&|]\+/\n/g')

while IFS= read -r segment; do
    segment=$(echo "$segment" | sed 's/^[[:space:]]*//;s/[[:space:]]*$//')
    [[ -z "$segment" ]] && continue

    # 取第一个词作为命令
    cmd_word=$(echo "$segment" | awk '{print $1}')

    # 跳过空词、shell 关键字
    [[ -z "$cmd_word" ]] && continue
    case "$cmd_word" in
        if|then|else|elif|fi|for|while|do|done|case|esac|in|\
        shift|exit|return|continue|break|source|.|cd|pwd|echo|export|\
        alias|set|unset|help|type|which|timeout)
            continue ;;
    esac

    # 跳过赋值语句
    [[ "$cmd_word" == *=* ]] && continue
    # 跳过选项
    [[ "$cmd_word" == -* ]] && continue
    # 跳过路径
    [[ "$cmd_word" == */* ]] && continue

    # 检查白名单
    FOUND=false
    for allowed in "${ALLOWED_COMMANDS[@]}"; do
        if [[ "$cmd_word" == "$allowed" ]]; then
            FOUND=true
            break
        fi
    done

    if [[ "$FOUND" == false ]]; then
        ERRORS+=("Command not in whitelist: '$cmd_word'")
    fi
done <<< "$SEGMENTS"

# 输出结果
if [[ ${#ERRORS[@]} -gt 0 ]]; then
    echo "[safety-gate] REJECTED" >&2
    for err in "${ERRORS[@]}"; do
        echo "  - $err" >&2
    done
    exit 1
fi

echo "[safety-gate] ALLOWED"
