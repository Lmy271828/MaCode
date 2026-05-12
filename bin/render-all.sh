#!/usr/bin/env bash
set -euo pipefail

# bin/render-all.sh
# 批量渲染 scenes/ 目录下所有场景。

if [[ "${1:-}" == "--help" || "${1:-}" == "-h" ]]; then
    cat <<'EOF'
Usage: render-all.sh [--parallel [N]] [scene_prefix]

Batch-render all scenes under scenes/.

Arguments:
  [scene_prefix]       Only render scenes matching prefix (e.g. 01_)

Options:
  --parallel [N]       Parallel rendering with up to N concurrent scenes
                       (default: max_concurrent_scenes from project.yaml, else 4)

Examples:
  render-all.sh
  render-all.sh --parallel
  render-all.sh --parallel 4
  render-all.sh 01_
EOF
    exit 0
fi

PARALLEL=false
MAX_JOBS=4
SCENE_PREFIX=""

# 解析参数
while [[ $# -gt 0 ]]; do
    case "$1" in
        --parallel)
            PARALLEL=true
            # 检查下一个参数是否为数字
            if [[ "${2:-}" =~ ^[0-9]+$ ]]; then
                MAX_JOBS="$2"
                shift
            else
                # 从 project.yaml 读取默认值
                if command -v yq >/dev/null 2>&1; then
                    MAX_JOBS=$(yq '.agent.resource_limits.max_concurrent_scenes // 4' project.yaml)
                elif command -v python3 >/dev/null 2>&1; then
                    MAX_JOBS=$(python3 -c "
import json, sys
try:
    import yaml
    with open('project.yaml') as f:
        c = yaml.safe_load(f)
    print(c.get('agent',{}).get('resource_limits',{}).get('max_concurrent_scenes',4))
except: print(4)
" 2>/dev/null || echo 4)
                fi
            fi
            ;;
        *)
            SCENE_PREFIX="$1"
            ;;
    esac
    shift
done

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_ROOT"

# 收集所有场景目录（排除 test_marker 等非场景文件导致的目录）
SCENES=$(find scenes -maxdepth 1 -mindepth 1 -type d -name "[0-9]*" | sort)

if [[ -z "$SCENES" ]]; then
    echo "No scenes found in scenes/" >&2
    exit 1
fi

# 按前缀过滤
if [[ -n "$SCENE_PREFIX" ]]; then
    SCENES=$(echo "$SCENES" | while read -r d; do
        name=$(basename "$d")
        [[ "$name" == "$SCENE_PREFIX"* ]] && echo "$d"
    done)
fi

SCENE_COUNT=$(echo "$SCENES" | wc -l)
if [[ "$SCENE_COUNT" -eq 0 ]]; then
    echo "No scenes matching prefix '$SCENE_PREFIX'" >&2
    exit 1
fi

# ── 构建依赖图（场景名 → 依赖列表）────────────────────
declare -A DEPS
declare -A SCENE_NAMES

build_dep_graph() {
    for scene_dir in $SCENES; do
        local name
        name=$(basename "$scene_dir")
        SCENE_NAMES["$name"]="$scene_dir"

        local manifest="$scene_dir/manifest.json"
        if [[ -f "$manifest" ]]; then
            if command -v jq >/dev/null 2>&1; then
                local dep_json
                dep_json=$(jq -r '.dependencies // [] | .[]' "$manifest" 2>/dev/null || true)
                DEPS["$name"]=$(echo "$dep_json" | while read -r dep; do
                    # 将依赖路径转为场景名
                    basename "$dep" 2>/dev/null || true
                done | sort -u)
            else
                DEPS["$name"]=""
            fi
        else
            DEPS["$name"]=""
        fi
    done
}

build_dep_graph

# ── 串行渲染 ──────────────────────────────────────────
render_serial() {
    local total=$SCENE_COUNT
    local current=0
    local success=0
    local failed=0

    for scene_dir in $SCENES; do
        local scene_name
        scene_name=$(basename "$scene_dir")
        current=$((current + 1))
        echo "[$current/$total] Rendering $scene_dir..."

        if bash "$PROJECT_ROOT/pipeline/render.sh" "$scene_dir"; then
            echo "[$current/$total] Rendering $scene_dir... OK"
            success=$((success + 1))
        else
            echo "[$current/$total] Rendering $scene_dir... FAILED" >&2
            failed=$((failed + 1))
        fi
    done

    echo ""
    echo "Done: $success succeeded, $failed failed (total $current)"

    if [[ "$failed" -gt 0 ]]; then
        return 1
    fi
}

# ── 并行渲染（拓扑层级调度）───────────────────────────
render_parallel() {
    echo "Parallel mode: max $MAX_JOBS concurrent renders"
    echo ""

    # 构建就绪队列（无未完成依赖的场景）
    local -a completed=()
    local -a in_progress=()
    local -a remaining=()

    for scene_dir in $SCENES; do
        remaining+=("$scene_dir")
    done

    local success=0
    local failed=0
    local total=${#remaining[@]}

    # 渲染单个场景的后台任务
    render_one() {
        local scene_dir="$1"
        local scene_name
        scene_name=$(basename "$scene_dir")
        local status_file=".agent/tmp/.render_status_${scene_name}"

        echo "[parallel] Starting: $scene_name"

        if bash "$PROJECT_ROOT/pipeline/render.sh" "$scene_dir" > "$status_file.log" 2>&1; then
            echo "OK" > "$status_file"
        else
            echo "FAILED" > "$status_file"
            # 保留日志用于调试
            cat "$status_file.log" >> ".agent/log/render_all_errors.log" 2>/dev/null || true
        fi
    }

    # 检查场景的所有依赖是否已满足
    deps_satisfied() {
        local name="$1"
        local dep_list="${DEPS[$name]:-}"

        if [[ -z "$dep_list" ]]; then
            return 0  # 无依赖
        fi

        for dep in $dep_list; do
            local found=false
            for c in "${completed[@]}"; do
                if [[ "$c" == "$dep" ]]; then
                    found=true
                    break
                fi
            done
            if [[ "$found" == false ]]; then
                return 1  # 依赖未满足
            fi
        done
        return 0
    }

    local round=0
    while [[ ${#completed[@]} -lt $total ]]; do
        round=$((round + 1))

        # 找到所有就绪场景
        local -a ready=()
        local -a new_remaining=()
        for scene_dir in "${remaining[@]}"; do
            local name
            name=$(basename "$scene_dir")
            if deps_satisfied "$name"; then
                ready+=("$scene_dir")
            else
                new_remaining+=("$scene_dir")
            fi
        done
        remaining=("${new_remaining[@]}")

        if [[ ${#ready[@]} -eq 0 ]]; then
            echo "ERROR: deadlock - no ready scenes but ${#remaining[@]} remaining" >&2
            return 1
        fi

        # 限制并发数：取 ready 和 MAX_JOBS 的最小值
        local batch_size=${#ready[@]}
        if [[ $batch_size -gt $MAX_JOBS ]]; then
            batch_size=$MAX_JOBS
        fi

        # 启动本轮任务（最多 MAX_JOBS 个）
        local launched=0
        for scene_dir in "${ready[@]}"; do
            if [[ $launched -ge $MAX_JOBS ]]; then
                # 放回 remaining 等待下一轮
                remaining+=("$scene_dir")
                continue
            fi
            render_one "$scene_dir" &
            in_progress+=("$(basename "$scene_dir")")
            launched=$((launched + 1))
        done

        # 等待本轮所有任务完成
        wait

        # 收集结果
        for name in "${in_progress[@]}"; do
            local status_file=".agent/tmp/.render_status_${name}"
            if [[ -f "$status_file" ]]; then
                local status
                status=$(cat "$status_file")
                if [[ "$status" == "OK" ]]; then
                    echo "[parallel] Completed: $name ✓"
                    completed+=("$name")
                    success=$((success + 1))
                else
                    echo "[parallel] Failed: $name ✗" >&2
                    # 失败不阻止其他场景，但依赖它的场景不会启动
                    completed+=("$name")  # 标记为"完成"以解除依赖
                    failed=$((failed + 1))
                fi
                rm -f "$status_file" "$status_file.log"
            fi
        done
        in_progress=()
    done

    echo ""
    echo "Done: $success succeeded, $failed failed (total $total)"

    if [[ "$failed" -gt 0 ]]; then
        return 1
    fi
}

# ── 入口 ──────────────────────────────────────────────
if $PARALLEL; then
    render_parallel
else
    render_serial
fi
