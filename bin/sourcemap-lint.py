#!/usr/bin/env python3
"""bin/sourcemap-lint.py
SOURCEMAP Markdown schema 校验器。
确保 SOURCEMAP.md 符合规范后再被机器消费。

用法:
    bin/sourcemap-lint.py <sourcemap.md>

退出码:
    0 - 通过
    1 - 失败（输出具体错误）
"""

import argparse
import re
import sys
from pathlib import Path


class LintError(Exception):
    pass


def lint(sourcemap_path):
    errors = []
    path = Path(sourcemap_path)
    if not path.exists():
        raise LintError(f"File not found: {sourcemap_path}")

    content = path.read_text(encoding="utf-8")
    lines = content.splitlines()

    # ── 1. 元数据校验 ──────────────────────────────────────
    if not re.search(r"^# MaCode Engine Source Map:\s*", content, re.MULTILINE):
        errors.append("Missing or malformed header: '# MaCode Engine Source Map: <引擎名>'")

    if not re.search(r">\s*引擎版本:\s*\S+", content, re.MULTILINE):
        errors.append("Missing metadata: 引擎版本")

    if not re.search(r">\s*适配层版本:\s*\S+", content, re.MULTILINE):
        errors.append("Missing metadata: 适配层版本")

    if not re.search(r">\s*生成日期:\s*\d{4}-\d{2}-\d{2}", content, re.MULTILINE):
        errors.append("Missing or malformed metadata: 生成日期 (expected YYYY-MM-DD)")

    # ── 2. 段式标题校验 ──────────────────────────────────
    required_sections = ["WHITELIST", "BLACKLIST", "EXTENSION"]
    for sec in required_sections:
        pattern = rf"^## {sec}:"
        if not re.search(pattern, content, re.MULTILINE):
            errors.append(f"Missing required section: '## {sec}:'")

    optional_sections = ["REDIRECT"]
    for sec in optional_sections:
        pattern = rf"^## {sec}:"
        if re.search(pattern, content, re.MULTILINE):
            pass  # optional, present is OK

    # 检测大小写错误（如 ## Whitelist）
    for sec in required_sections:
        bad_pattern = rf"^## {sec.lower()}\b|^## {sec.capitalize()}\b"
        if re.search(bad_pattern, content, re.MULTILINE | re.IGNORECASE):
            # 如果上面严格匹配已经通过，这里不会触发；如果没通过，给更精确提示
            pass

    # ── 3. 按段校验表格 ────────────────────────────────────
    def extract_section_lines(sec_name):
        in_section = False
        for line in lines:
            if re.match(rf"^## {sec_name}:", line):
                in_section = True
                continue
            if in_section and re.match(r"^## ", line):
                break
            if in_section:
                yield line
        return

    # WHITELIST: | 标识 | 路径/命令 | 用途 | 优先级 |
    whitelist_rows = 0
    for line in extract_section_lines("WHITELIST"):
        stripped = line.strip()
        if not stripped or stripped.replace("|", "").replace("-", "").replace(" ", "") == "":
            continue  # 空行或表格分隔线
        if not stripped.startswith("|"):
            continue
        parts = [p.strip() for p in stripped.split("|")]
        parts = [p for p in parts if p]
        if len(parts) == 4 and parts[0] == "标识":
            continue  # 表头
        if len(parts) != 4:
            errors.append(f"WHITELIST table row has {len(parts)} columns (expected 4): {stripped[:80]}")
            continue
        _id, path_raw, purpose, priority = parts
        if not path_raw.startswith("`") or not path_raw.endswith("`"):
            errors.append(f"WHITELIST row '{_id}': path must be wrapped in backticks: {path_raw[:60]}")
        if priority not in ("P0", "P1", "P2"):
            errors.append(f"WHITELIST row '{_id}': invalid priority '{priority}' (must be P0/P1/P2)")
        whitelist_rows += 1

    if whitelist_rows > 20:
        errors.append(f"WHITELIST has {whitelist_rows} rows (max 20)")

    # BLACKLIST: | 标识 | 路径/命令 | 原因 |
    for line in extract_section_lines("BLACKLIST"):
        stripped = line.strip()
        if not stripped or stripped.replace("|", "").replace("-", "").replace(" ", "") == "":
            continue
        if not stripped.startswith("|"):
            continue
        parts = [p.strip() for p in stripped.split("|")]
        parts = [p for p in parts if p]
        if len(parts) == 3 and parts[0] == "标识":
            continue
        if len(parts) != 3:
            errors.append(f"BLACKLIST table row has {len(parts)} columns (expected 3): {stripped[:80]}")
            continue
        _id, path_raw, reason = parts
        if path_raw and not (path_raw.startswith("`") and path_raw.endswith("`")):
            errors.append(f"BLACKLIST row '{_id}': path must be wrapped in backticks if present: {path_raw[:60]}")

    # EXTENSION: | 标识 | 描述 | 状态 |
    for line in extract_section_lines("EXTENSION"):
        stripped = line.strip()
        if not stripped or stripped.replace("|", "").replace("-", "").replace(" ", "") == "":
            continue
        if not stripped.startswith("|"):
            continue
        parts = [p.strip() for p in stripped.split("|")]
        parts = [p for p in parts if p]
        if len(parts) == 3 and parts[0] == "标识":
            continue
        if len(parts) != 3:
            errors.append(f"EXTENSION table row has {len(parts)} columns (expected 3): {stripped[:80]}")
            continue
        _id, desc, status = parts
        if status not in ("TODO", "DOING", "DONE", "WONTFIX"):
            errors.append(f"EXTENSION row '{_id}': invalid status '{status}' (must be TODO/DOING/DONE/WONTFIX)")

    # REDIRECT: | Pitfall | Correct Approach | Reason |
    redirect_present = bool(re.search(r"^## REDIRECT:", content, re.MULTILINE))
    if redirect_present:
        for line in extract_section_lines("REDIRECT"):
            stripped = line.strip()
            if not stripped or stripped.replace("|", "").replace("-", "").replace(" ", "") == "":
                continue
            if not stripped.startswith("|"):
                continue
            parts = [p.strip() for p in stripped.split("|")]
            parts = [p for p in parts if p]
            if len(parts) == 3 and parts[0] == "Pitfall":
                continue
            if len(parts) != 3:
                errors.append(f"REDIRECT table row has {len(parts)} columns (expected 3): {stripped[:80]}")
                continue
            _pitfall, _correct, _reason = parts

    # ── 4. 危险 eval 模式检测 ───────────────────────────────
    dangerous_commands = ["rm", "curl", "wget", "eval", "exec", "bash", "sh ", "dd ", "mv ", "cp "]
    for line in lines:
        if "$(" in line:
            backtick_content = re.findall(r"`([^`]+)`", line)
            for content in backtick_content:
                if "$(" in content:
                    inner = content[content.find("$(") + 2:]
                    inner = inner[:inner.find(")")] if ")" in inner else inner
                    for cmd in dangerous_commands:
                        if cmd in inner.lower():
                            errors.append(f"Dangerous shell command detected in path expression: {content[:80]}")
                            break

    return errors


def main():
    parser = argparse.ArgumentParser(
        description='SOURCEMAP Markdown schema validator. '
                    'Ensures SOURCEMAP.md is machine-consumable.',
        epilog='Exit codes: 0=pass, 1=fail, 2=argument or file error.',
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument('sourcemap', help='Path to SOURCEMAP.md file')
    args = parser.parse_args()

    sourcemap_path = args.sourcemap
    try:
        errors = lint(sourcemap_path)
    except LintError as e:
        print(f"[sourcemap-lint] FATAL: {e}", file=sys.stderr)
        sys.exit(1)

    if errors:
        print(f"[sourcemap-lint] FAILED: {len(errors)} error(s) in {sourcemap_path}", file=sys.stderr)
        for err in errors:
            print(f"  - {err}", file=sys.stderr)
        sys.exit(1)
    else:
        print(f"[sourcemap-lint] OK: {sourcemap_path}")
        sys.exit(0)


if __name__ == "__main__":
    main()
