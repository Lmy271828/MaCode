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


def load_blacklist(sourcemap_json_path: str, engine_cli: str | None = None) -> list[tuple[str, str | None, str, str]]:
    """Parse sourcemap JSON; fail-closed (exit 2) on missing/malformed data.

    Returns list of (path_raw, module, reason, entry_id).
    """
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

    patterns: list[tuple[str, str | None, str, str]] = []
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
        reason = item.get("reason", "")
        entry_id = item.get("id", "")
        if path_raw.startswith("@"):
            module = path_raw
        else:
            module = _path_to_module(path_raw)
        patterns.append((path_raw, module, reason, entry_id))

    return patterns


def load_redirects(sourcemap_json_path: str) -> list[dict]:
    """Load redirect entries from sourcemap JSON."""
    try:
        with open(sourcemap_json_path, encoding="utf-8") as f:
            data = json.load(f)
    except (json.JSONDecodeError, OSError):
        return []
    entries = data.get("redirect", [])
    if not isinstance(entries, list):
        return []
    return [e for e in entries if isinstance(e, dict)]


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


def _get_replacement_hint(entry_id: str, module: str) -> str | None:
    """Return a concrete replacement hint for known blacklisted modules."""
    if entry_id == "DEPRECATED_GL":
        return "Use 'from manim import *' instead of 'from manimlib import *'"
    if entry_id == "MANIMCE_API":
        return "Use 'from manimlib import *' instead of 'from manim import *'"
    if entry_id == "MANIMCE_SCENE":
        return "Use 'from manimlib import *' and inherit from manimlib's Scene"
    if "manimlib" in module and "manim" not in module.replace("manimlib", ""):
        return "Use 'from manim import *' instead"
    if module == "manim" or module.startswith("manim."):
        return "Use 'from manimlib import *' instead"
    return None


def _extract_pitfall_keywords(pitfall: str) -> list[str]:
    """Extract backtick-quoted snippets from a pitfall string."""
    # Match content inside `...`
    return re.findall(r'`([^`]+)`', pitfall)


def _find_handwritten_pitfalls(code: str, redirects: list[dict]) -> list[dict]:
    """Scan code for raw syntax patterns that have redirect wrappers."""
    matches = []
    for entry in redirects:
        pitfall = entry.get("pitfall", "")
        if not pitfall:
            continue
        keywords = _extract_pitfall_keywords(pitfall)
        if not keywords:
            continue
        # Require at least one keyword to appear in the code
        for kw in keywords:
            # Skip very short keywords to reduce false positives
            if len(kw) < 4:
                continue
            if kw in code:
                matches.append(entry)
                break
    return matches


def check_python_imports(code, blacklist):
    """检查场景源码是否包含 BLACKLIST 中的违规导入。

    Returns list of violation dicts.
    """
    violations = []
    for raw_path, module, reason, entry_id in blacklist:
        if module is None:
            continue
        # 匹配两种导入模式：
        #   PREFIX: import <module>...  /  from <module>... import ...
        #   SUBMOD: from <parent>.<module>... import ... / import <parent>.<module>
        escaped = re.escape(module)
        prefix_rx = rf'\b(?:import\s+{escaped}\b|from\s+{escaped}(?:\.\S+)?\s+import\b)'
        submod_rx = rf'\b(?:import\s+\S+\.{escaped}\b|from\s+\S+\.{escaped}(?:\.\S+)?\s+import\b)'
        if re.search(prefix_rx, code) or re.search(submod_rx, code):
            violations.append({
                "module": module,
                "raw_path": raw_path,
                "reason": reason,
                "id": entry_id,
            })

    return violations


def check_js_imports(code: str, blacklist_entries: list[tuple[str, str | None, str, str]]) -> list[dict]:
    """检查 TS/JS 场景源码是否包含 BLACKLIST 中的违规导入。"""
    violations = []
    imported = set()
    for match in re.finditer(r"\bfrom\s+['\"]([^'\"]+)['\"]", code):
        imported.add(match.group(1))
    for match in re.finditer(r"\brequire\s*\(\s*['\"]([^'\"]+)['\"]\s*\)", code):
        imported.add(match.group(1))

    for pkg in imported:
        for raw_path, _module, reason, entry_id in blacklist_entries:
            # Strip backticks that may surround path_raw in SOURCEMAP markdown
            clean = raw_path.strip().strip('`').strip()
            if not clean:
                continue
            if pkg == clean or pkg.startswith(clean + "/"):
                violations.append({
                    "module": pkg,
                    "raw_path": raw_path,
                    "reason": reason,
                    "id": entry_id,
                })
                break

    return violations


def main():
    parser = argparse.ArgumentParser(
        description='Static API gate using SOURCEMAP BLACKLIST. Blocks forbidden imports.',
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
    redirects = load_redirects(sourcemap_path)
    all_violations = []

    is_js = scene_file.endswith(('.ts', '.tsx', '.js', '.mjs'))

    # 1. BLACKLIST 导入检查
    if is_js:
        all_violations.extend(check_js_imports(code, blacklist))
    else:
        all_violations.extend(check_python_imports(code, blacklist))

    # 2. Redirect pitfall scanning (advisory, not blocking on its own)
    pitfall_matches = _find_handwritten_pitfalls(code, redirects)

    if all_violations:
        print("API_GATE_VIOLATIONS:")
        for v in all_violations:
            print(f"  - {v['module']} (pattern: {v['raw_path']})")
            if v.get('reason'):
                print(f"    reason: {v['reason']}")
            hint = _get_replacement_hint(v.get('id', ''), v['module'])
            if hint:
                print(f"    REPLACEMENT: {hint}")

        if pitfall_matches:
            print("\n  REDIRECT hints (code patterns that should use wrappers):")
            for p in pitfall_matches:
                print(f"    - {p.get('pitfall')} -> {p.get('correct')}")

        print(f"\nFix: consult {sourcemap_path} (BLACKLIST + REDIRECT in engines/*/sourcemap.json).",
              file=sys.stderr)
        sys.exit(1)
    else:
        if pitfall_matches:
            print("API_GATE_OK (with advisory redirects):")
            for p in pitfall_matches:
                print(f"  - {p.get('pitfall')} -> {p.get('correct')}")
        else:
            print("API_GATE_OK")
        sys.exit(0)


if __name__ == "__main__":
    main()
