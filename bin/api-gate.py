#!/usr/bin/env python3
"""bin/api-gate.py
利用 SOURCEMAP（canonical JSON）BLACKLIST 做导入静态拦截。

用法:
    bin/api-gate.py <scene_file> <engines/.../sourcemap.json> [--engine <name>]

退出码:
    0 - 通过（API_GATE_OK）
    1 - 发现违规导入（API_GATE_VIOLATIONS）
    2 - 参数错误或文件缺失 / JSON 不可用
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys


def infer_engine_from_sourcemap_json_path(abs_path: str) -> str | None:
    """Return engine directory name from .../engines/<engine>/sourcemap.json."""
    norm = os.path.abspath(abs_path).replace("\\", "/")
    marker = "/engines/"
    if marker not in norm:
        return None
    rest = norm.split(marker, 1)[1]
    parts = rest.split("/")
    if len(parts) < 2:
        return None
    if parts[-1] != "sourcemap.json":
        return None
    return parts[0]


def load_blacklist(sourcemap_json_path: str, engine_cli: str | None = None) -> list[tuple[str, str | None]]:
    """Parse sourcemap JSON; fail-closed (exit 2) on missing/malformed data."""
    if not os.path.isfile(sourcemap_json_path):
        print(f"FATAL: SOURCEMAP JSON not found: {sourcemap_json_path}", file=sys.stderr)
        sys.exit(2)

    inferred = infer_engine_from_sourcemap_json_path(sourcemap_json_path)
    if engine_cli:
        if inferred and inferred != engine_cli:
            print(
                f"FATAL: --engine '{engine_cli}' does not match path (expected engine '{inferred}' from file path)",
                file=sys.stderr,
            )
            sys.exit(2)
    elif not inferred:
        print(
            "FATAL: Cannot infer engine from sourcemap path; pass --engine <name>",
            file=sys.stderr,
        )
        sys.exit(2)

    try:
        with open(sourcemap_json_path, encoding="utf-8") as f:
            data = json.load(f)
    except (json.JSONDecodeError, OSError) as e:
        print(f"FATAL: Cannot read SOURCEMAP JSON: {e}", file=sys.stderr)
        sys.exit(2)

    patterns: list[tuple[str, str | None]] = []
    entries = data.get("blacklist", [])
    if not isinstance(entries, list):
        print("FATAL: SOURCEMAP JSON blacklist is not a list", file=sys.stderr)
        sys.exit(2)

    for item in entries:
        if not isinstance(item, dict):
            continue
        path_raw = item.get("path_raw", "")
        path_raw = path_raw.strip() if isinstance(path_raw, str) else ""
        if not path_raw:
            continue
        if path_raw.startswith("@"):
            module = path_raw
        else:
            module = _path_to_module(path_raw)
        patterns.append((path_raw, module))

    return patterns


def _path_to_module(path_raw):
    """将 SOURCEMAP 路径转换为 Python 导入模块名。

    >>> _path_to_module('manimlib/')
    'manimlib'
    >>> _path_to_module('$(python -c "...")/_config/')
    '_config'
    >>> _path_to_module('$(python -c "...")/mobject/types/')
    'mobject.types'
    >>> _path_to_module('.agent/tmp/')
    None
    """
    path = path_raw.strip().rstrip('/')

    # 跳过非代码路径
    if (path.startswith('.') and not path.startswith('./')) or \
       path.startswith('node_modules') or \
       path.startswith('venv'):
        return None

    # 动态路径：$(python -c "...")/foo/bar/ → 取尾部 → foo.bar
    if '$(' in path:
        # 取最后一个 ) 之后的部分
        idx = path.rfind(')')
        if idx >= 0:
            path = path[idx + 1:].lstrip('/')
        else:
            path = path.lstrip('/')

    # 去掉多余的引号和括号
    path = path.strip('"').strip("'")

    # 路径分隔符 → 点号
    module = path.replace('/', '.')

    if not module or module in ('.', '..'):
        return None

    return module


def check_python_imports(code, blacklist):
    """检查场景源码是否包含 BLACKLIST 中的违规导入。"""
    violations = []
    for raw_path, module in blacklist:
        if module is None:
            continue
        # 匹配两种导入模式：
        #   PREFIX: import <module>...  /  from <module>... import ...
        #   SUBMOD: from <parent>.<module>... import ... / import <parent>.<module>
        escaped = re.escape(module)
        prefix_rx = rf'\b(?:import\s+{escaped}\b|from\s+{escaped}(?:\.\S+)?\s+import\b)'
        submod_rx = rf'\b(?:import\s+\S+\.{escaped}\b|from\s+\S+\.{escaped}(?:\.\S+)?\s+import\b)'
        if re.search(prefix_rx, code) or re.search(submod_rx, code):
            violations.append(
                f"BLACKLIST import: {module} (pattern: {raw_path})"
            )

    return violations


def check_js_imports(code: str, blacklist_raw_paths: list[str]) -> list[str]:
    """检查 TS/JS 场景源码是否包含 BLACKLIST 中的违规导入。"""
    violations = []
    imported = set()
    for match in re.finditer(r"\bfrom\s+['\"]([^'\"]+)['\"]", code):
        imported.add(match.group(1))
    for match in re.finditer(r"\brequire\s*\(\s*['\"]([^'\"]+)['\"]\s*\)", code):
        imported.add(match.group(1))

    for pkg in imported:
        for pattern in blacklist_raw_paths:
            # Strip backticks that may surround path_raw in SOURCEMAP markdown
            clean = pattern.strip().strip('`').strip()
            if not clean:
                continue
            if pkg == clean or pkg.startswith(clean + "/"):
                violations.append(
                    f"BLACKLIST JS import: {pkg} (pattern: {pattern})"
                )
                break

    return violations


# ── Sandbox: dangerous Python call patterns ──────────────
# 这些 pattern 在数学动画场景中没有合法用途
SANDBOX_PATTERNS = [
    # 子进程执行
    (r'\bsubprocess\b', 'subprocess — arbitrary command execution'),
    (r'\bos\.system\s*\(', 'os.system() — arbitrary shell command'),
    (r'\bos\.popen\s*\(', 'os.popen() — arbitrary shell command'),
    # 动态导入（绕过 api-gate 静态检查）
    (r'\b__import__\s*\(', '__import__() — dynamic import bypass'),
    # 网络访问
    (r'\bimport\s+socket\b', 'socket — raw network access'),
    (r'\bfrom\s+socket\s+import\b', 'socket — raw network access'),
    (r'\bimport\s+requests\b', 'requests — HTTP client'),
    (r'\bfrom\s+requests\s+import\b', 'requests — HTTP client'),
    (r'\bimport\s+urllib\b', 'urllib — HTTP client'),
    (r'\bfrom\s+urllib', 'urllib — HTTP client'),
    # 文件系统破坏
    (r'\bshutil\.rmtree\s*\(', 'shutil.rmtree() — recursive delete'),
    (r'\bos\.remove\s*\(', 'os.remove() — file deletion (use pipeline scripts)'),
    (r'\bos\.rmdir\s*\(', 'os.rmdir() — directory deletion'),
    # 读取系统敏感路径
    (r'open\s*\(\s*[\'"]/', 'open() reading absolute path (potential data leak)'),
    # 退出/信号
    (r'\bos\.kill\s*\(', 'os.kill() — process termination'),
    (r'\bsys\.exit\s*\(', 'sys.exit() — premature process termination'),
]


# ── Syntax Gate: hand-written raw nested syntax ──────────────
# Agents should not write these raw patterns; use utils helpers instead
SYNTAX_REDIRECTS = [
    # ffmpeg filtergraph strings
    (r'-vf\s*"', "hand-written ffmpeg video filtergraph", "use utils.ffmpeg_builder"),
    (r'-af\s*"', "hand-written ffmpeg audio filter", "use utils.ffmpeg_builder"),
    (r'-filter_complex\s*"', "hand-written ffmpeg complex filtergraph", "use utils.ffmpeg_builder"),

    # LaTeX raw environments
    (r'\\begin\{cases\}', "hand-written LaTeX cases environment", "use utils.latex_helper.cases()"),
    (r'\\begin\{bmatrix\}|\\begin\{pmatrix\}|\\begin\{Bmatrix\}', "hand-written LaTeX matrix", "use utils.latex_helper.matrix()"),
    (r'\\begin\{align\*?\}', "hand-written LaTeX align environment", "use utils.latex_helper.align_eqns()"),
    (r'\\begin\{equation\*?\}', "hand-written LaTeX equation environment", "use utils.latex_helper.math() or ChineseMathTex()"),

    # GLSL shader
    (r'gl_Position|uniform\s+\w+|varying\s+\w+|attribute\s+\w+', "hand-written GLSL shader code", "use utils.shader_builder"),
    (r'#version\s+\d+', "hand-written GLSL version directive", "use utils.shader_builder"),

    # Complex regex
    (r're\.compile\s*\(\s*["\'][^"\']{60,}["\']', "hand-written complex regex", "use utils.pattern_helper"),
    (r're\.match\s*\(\s*["\'][^"\']{60,}["\']', "hand-written complex regex", "use utils.pattern_helper"),
    (r're\.search\s*\(\s*["\'][^"\']{60,}["\']', "hand-written complex regex", "use utils.pattern_helper"),

    # Bash dangerous patterns in Python strings
    (r'ffmpeg.*?-i.*?-vf', "hand-written ffmpeg command string in Python", "use utils.ffmpeg_builder"),
]


def check_sandbox(code):
    """扫描场景源码中的危险 Python 调用。"""
    violations = []
    for pattern, description in SANDBOX_PATTERNS:
        if re.search(pattern, code):
            violations.append(f"SANDBOX violation: {description}")
    return violations


def check_syntax_gate(code, scene_file):
    """扫描场景源码中的手写原始语法模式。返回 (description, line_number, recommendation) 列表。"""
    violations = []
    seen_lines = set()
    for line_no, line in enumerate(code.splitlines(), start=1):
        for pattern, description, recommendation in SYNTAX_REDIRECTS:
            if re.search(pattern, line):
                if line_no in seen_lines:
                    break  # 不重复报告同一行
                seen_lines.add(line_no)
                violations.append((description, line_no, recommendation))
                break  # 一行只报第一个匹配的 pattern
    return violations


def main():
    parser = argparse.ArgumentParser(
        description='Static API gate using SOURCEMAP BLACKLIST. '
                    'Blocks forbidden imports, sandbox violations and raw syntax patterns.',
        epilog='Exit codes: 0=OK, 1=violations found, 2=argument or file error.',
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument('scene_file', help='Path to scene source file (.py or .tsx)')
    parser.add_argument('sourcemap_json', help='Path to engines/{engine}/sourcemap.json')
    parser.add_argument(
        '--engine',
        default=None,
        help='Explicit engine id (must match path engines/<engine>/sourcemap.json when inferable)',
    )
    args = parser.parse_args()

    scene_file = args.scene_file
    sourcemap_path = args.sourcemap_json

    if not os.path.exists(scene_file):
        print(f"FATAL: Scene file not found: {scene_file}", file=sys.stderr)
        sys.exit(2)

    # 读取场景源码
    try:
        with open(scene_file, encoding='utf-8') as f:
            code = f.read()
    except OSError as e:
        print(f"FATAL: Cannot read scene: {e}", file=sys.stderr)
        sys.exit(2)

    blacklist = load_blacklist(sourcemap_path, args.engine)
    all_violations = []

    is_js = scene_file.endswith(('.ts', '.tsx', '.js', '.mjs'))

    # 1. BLACKLIST 导入检查
    if is_js:
        js_blacklist = [raw for raw, _ in blacklist]
        all_violations.extend(check_js_imports(code, js_blacklist))
    else:
        all_violations.extend(check_python_imports(code, blacklist))

    # 2. Sandbox 危险调用检查
    all_violations.extend(check_sandbox(code))

    # 3. Syntax Gate 手写原始语法检查
    syntax_violations = check_syntax_gate(code, scene_file)

    if syntax_violations:
        for description, line_no, recommendation in syntax_violations:
            print(f"SYNTAX_GATE_REDIRECT: {description}")
            print(f"Location: {scene_file}:{line_no}")
            print(f"Recommendation: {recommendation}")

    if all_violations or syntax_violations:
        if all_violations:
            print("API_GATE_VIOLATIONS:")
            for v in all_violations:
                print(f"  - {v}")
            print(f"\nFix: consult {sourcemap_path} (whitelist in engines/*/sourcemap.json + REDIRECT).",
                  file=sys.stderr)
        sys.exit(1)
    else:
        print("API_GATE_OK")
        sys.exit(0)


if __name__ == "__main__":
    main()
