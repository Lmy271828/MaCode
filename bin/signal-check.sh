#!/usr/bin/env bash
set -euo pipefail

# bin/signal-check.sh
# 检查人类介入信号的统一脚本。
#
# 用法: signal-check.sh [scene_name]
#   scene_name - 可选，用于 scene-specific 信号（预留）
# 输出 JSON 到 stdout

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SIGNALS_DIR="$PROJECT_ROOT/.agent/signals"

mkdir -p "$SIGNALS_DIR"

python3 -c "
import json
import os
import sys

signals_dir = '$SIGNALS_DIR'

def file_exists(name):
    return os.path.isfile(os.path.join(signals_dir, name))

def read_human_override():
    path = os.path.join(signals_dir, 'human_override.json')
    if not os.path.isfile(path):
        return None
    try:
        with open(path, 'r') as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return None

result = {
    'pause': file_exists('pause'),
    'abort': file_exists('abort'),
    'review_needed': file_exists('review_needed'),
    'human_override': read_human_override(),
    'reject': file_exists('reject')
}

print(json.dumps(result, indent=2, ensure_ascii=False))
"
