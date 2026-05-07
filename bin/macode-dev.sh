#!/usr/bin/env bash
set -euo pipefail

# bin/macode-dev.sh
# macode dev 的入口逻辑。
#
# 用法: macode-dev.sh <scene_dir> [--act <act_id>]
#   scene_dir - 场景目录，如 scenes/01_test/
#   --act     - 可选，指定幕 ID，用于引擎 seek

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

SCENE_DIR=""
ACT_ID=""

# 解析参数
while [[ $# -gt 0 ]]; do
    case "$1" in
        --act)
            ACT_ID="${2:-}"
            shift 2
            ;;
        -*)
            echo "Unknown option: $1" >&2
            echo "Usage: $0 <scene_dir> [--act <act_id>]" >&2
            exit 1
            ;;
        *)
            if [[ -z "$SCENE_DIR" ]]; then
                SCENE_DIR="$1"
            fi
            shift
            ;;
    esac
done

if [[ -z "$SCENE_DIR" ]]; then
    echo "Usage: $0 <scene_dir> [--act <act_id>]" >&2
    exit 1
fi

SCENE_DIR="${SCENE_DIR%/}"
MANIFEST="$SCENE_DIR/manifest.json"

if [[ ! -f "$MANIFEST" ]]; then
    echo "Error: manifest.json not found in $SCENE_DIR" >&2
    exit 1
fi

# 读取引擎类型
if command -v jq >/dev/null 2>&1; then
    ENGINE=$(jq -r '.engine // "manim"' "$MANIFEST")
else
    ENGINE=$(python3 -c "import json,sys; print(json.load(open('$MANIFEST')).get('engine','manim'))")
fi

SCENE_NAME=$(basename "$SCENE_DIR")

echo "[macode dev] Scene: $SCENE_NAME"
echo "[macode dev] Engine: $ENGINE"
if [[ -n "$ACT_ID" ]]; then
    echo "[macode dev] Act: $ACT_ID"
fi

case "$ENGINE" in
    manim)
        bash "$PROJECT_ROOT/engines/manim/scripts/dev.sh" "$SCENE_DIR"
        ;;

    manimgl)
        SCENE_PY="$SCENE_DIR/scene.py"
        if [[ ! -f "$SCENE_PY" ]]; then
            echo "Error: scene.py not found in $SCENE_DIR" >&2
            exit 1
        fi

        VENV_PYTHON="$PROJECT_ROOT/.venv-manimgl/bin/python"
        if [[ ! -x "$VENV_PYTHON" ]]; then
            echo "Error: ManimGL not installed. Run: bash bin/setup.sh" >&2
            exit 1
        fi

        # 计算 seek 时间（如果指定了 act）
        SEEK_ARG=""
        if [[ -n "$ACT_ID" ]]; then
            SEEK_TIME=""
            if command -v jq >/dev/null 2>&1; then
                SEEK_TIME=$(jq -r --arg act "$ACT_ID" '.acts[] | select(.id == \$act) | .time_range[0]' "$MANIFEST" 2>/dev/null || true)
            fi
            if [[ -z "$SEEK_TIME" || "$SEEK_TIME" == "null" ]]; then
                # fallback: 用 python 解析
                SEEK_TIME=$(python3 -c "
import json
try:
    m = json.load(open('$MANIFEST'))
    for act in m.get('acts', []):
        if act['id'] == '$ACT_ID':
            print(act['time_range'][0])
            break
except:
    pass
" 2>/dev/null || true)
            fi
            if [[ -n "$SEEK_TIME" && "$SEEK_TIME" != "null" ]]; then
                SEEK_ARG="--seek $SEEK_TIME"
                echo "[manimgl] Seeking to act '$ACT_ID' at ${SEEK_TIME}s"
            else
                echo "[manimgl] Warning: act '$ACT_ID' not found in manifest, starting from beginning"
            fi
        fi

        # 将引擎适配层加入 Python 路径
        ENGINE_SRC="$PROJECT_ROOT/engines/manimgl/src"
        export PYTHONPATH="${ENGINE_SRC}${PYTHONPATH:+:$PYTHONPATH}"

        echo "[manimgl] Launching interactive preview: $SCENE_PY"
        cd "$PROJECT_ROOT"
        # shellcheck disable=SC2086
        exec "$VENV_PYTHON" -m manimlib "$SCENE_PY" $SEEK_ARG
        ;;

    motion_canvas)
        SCENE_TSX="$SCENE_DIR/scene.tsx"
        if [[ ! -f "$SCENE_TSX" ]]; then
            echo "Error: scene.tsx not found in $SCENE_DIR" >&2
            exit 1
        fi

        if [[ ! -d "$PROJECT_ROOT/node_modules" ]]; then
            echo "Error: node_modules not found. Run 'bash bin/setup.sh' first." >&2
            exit 1
        fi

        echo "[motion_canvas] Starting watcher for $SCENE_TSX"
        cd "$PROJECT_ROOT"

        # Motion Canvas 项目通常用 npm run dev 启动热重载服务器
        # 如果项目 package.json 中有 dev script，则使用它
        if grep -q '"dev"' "$PROJECT_ROOT/package.json" 2>/dev/null; then
            npm run dev
        else
            # fallback: 用 npx tsx watch 或简单轮询提示
            echo "[motion_canvas] No 'dev' script found in package.json."
            echo "[motion_canvas] Starting basic file watcher..."
            echo "[motion_canvas] Press Ctrl+C to stop."

            LAST_MTIME=""
            while true; do
                CURRENT_MTIME=$(stat -c %Y "$SCENE_TSX" 2>/dev/null || echo "0")
                if [[ "$CURRENT_MTIME" != "$LAST_MTIME" && -n "$LAST_MTIME" ]]; then
                    echo "[motion_canvas] File changed: $SCENE_TSX"
                    echo "[motion_canvas] Run 'macode render $SCENE_DIR' to rebuild."
                fi
                LAST_MTIME="$CURRENT_MTIME"
                sleep 2
            done
        fi
        ;;

    *)
        echo "Error: unknown engine '$ENGINE'" >&2
        exit 1
        ;;
esac
