#!/usr/bin/env python3
"""bin/api-gate.py
利用 SOURCEMAP BLACKLIST 做导入静态拦截。

用法:
    bin/api-gate.py <scene_file> <sourcemap_path>

退出码:
    0 - 通过（API_GATE_OK）
    1 - 发现违规导入（API_GATE_VIOLATIONS）
    2 - 参数错误或文件缺失
"""

import sys
import re
import os


def load_blacklist(sourcemap_path):
    """解析 SOURCEMAP.md 的 BLACKLIST 表格，返回禁止的模块模式列表。"""
    patterns = []
    try:
        with open(sourcemap_path, 'r', encoding='utf-8') as f:
            content = f.read()
    except FileNotFoundError:
        print(f"FATAL: SOURCEMAP not found: {sourcemap_path}", file=sys.stderr)
        sys.exit(2)
    except OSError as e:
        print(f"FATAL: Cannot read SOURCEMAP: {e}", file=sys.stderr)
        sys.exit(2)

    # 提取 BLACKLIST 段（到下一个 ## 为止）
    m = re.search(r'^## BLACKLIST:.*?\n(.*?)(?=\n## |\Z)', content, re.DOTALL | re.MULTILINE)
    if not m:
        print("WARN: BLACKLIST section not found in SOURCEMAP", file=sys.stderr)
        return patterns

    for line in m.group(1).splitlines():
        if not line.startswith('|') or ' 标识 ' in line:
            continue
        parts = [p.strip() for p in line.split('|')]
        if len(parts) >= 4:
            path_raw = parts[2].strip('`').strip()
            if path_raw and path_raw != '路径/命令':
                # 将路径转换为模块模式
                # e.g., "manimlib/" -> "manimlib"
                # e.g., "manim/_config/" -> "manim._config"
                # e.g., "node_modules/.cache/" -> skip (not importable)
                module = path_raw.rstrip('/')

                # 跳过明显的文件系统路径（非导入模块）
                if module.startswith('.') or module.startswith('node_modules'):
                    continue

                # 将 / 替换为 . 生成可能的导入前缀
                module_dot = module.replace('/', '.')
                patterns.append((path_raw, module_dot))

    return patterns


def check_scene(filepath, blacklist):
    """检查场景源码是否包含 BLACKLIST 中的违规导入。"""
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            code = f.read()
    except FileNotFoundError:
        print(f"FATAL: Scene file not found: {filepath}", file=sys.stderr)
        sys.exit(2)
    except OSError as e:
        print(f"FATAL: Cannot read scene: {e}", file=sys.stderr)
        sys.exit(2)

    violations = []
    for raw_path, module in blacklist:
        # 匹配 import / from ... import 语句
        escaped = re.escape(module)
        if re.search(rf'\b(?:import\s+{escaped}|from\s+{escaped}\s+import)', code):
            violations.append(
                f"BLACKLIST import: {module} (pattern: {raw_path})"
            )

    return violations


def main():
    if len(sys.argv) < 3:
        print("Usage: api-gate.py <scene_file> <sourcemap_path>", file=sys.stderr)
        sys.exit(2)

    scene_file = sys.argv[1]
    sourcemap_path = sys.argv[2]

    if not os.path.exists(scene_file):
        print(f"FATAL: Scene file not found: {scene_file}", file=sys.stderr)
        sys.exit(2)

    blacklist = load_blacklist(sourcemap_path)
    violations = check_scene(scene_file, blacklist)

    if violations:
        print("API_GATE_VIOLATIONS:")
        for v in violations:
            print(f"  - {v}")
        print(f"\nFix: consult {sourcemap_path} WHITELIST for safe alternatives.",
              file=sys.stderr)
        sys.exit(1)
    else:
        print("API_GATE_OK")
        sys.exit(0)


if __name__ == "__main__":
    main()
