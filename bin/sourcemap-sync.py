#!/usr/bin/env python3
"""bin/sourcemap-sync.py
将 engines/{name}/SOURCEMAP.md 解析为结构化的 JSON，供机器消费。

用法:
    sourcemap-sync.py [engine_name]       # 同步指定引擎（默认 project.yaml 中的 default engine）
    sourcemap-sync.py --all               # 同步所有引擎
    sourcemap-sync.py --check [engine]    # 检查 Markdown 与 JSON 是否同步（不写入）

输出:
    .agent/context/{engine}_sourcemap.json
"""

import hashlib
import json
import os
import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path


def parse_markdown_table(lines, expected_cols):
    """解析 Markdown 表格，返回字典列表。"""
    rows = []
    for line in lines:
        line = line.strip()
        if not line.startswith("|") or " 标识 " in line or " Pitfall " in line or "---" in line.replace("|", ""):
            continue
        parts = [p.strip() for p in line.split("|")]
        # 过滤空字符串（首尾 | 产生的）
        parts = [p for p in parts if p]
        if len(parts) < expected_cols:
            continue
        rows.append(parts)
    return rows


def extract_section(content, section_name):
    """从 Markdown 内容中提取指定 ## section 的表格行。"""
    pattern = rf'^## {re.escape(section_name)}:.*?\n(.*?)(?=\n## |\Z)'
    m = re.search(pattern, content, re.DOTALL | re.MULTILINE)
    return m.group(1).splitlines() if m else []


def lint_sourcemap(md_path):
    """调用 sourcemap-lint.py 校验 Markdown schema。"""
    lint_script = Path(__file__).parent / "sourcemap-lint.py"
    result = subprocess.run(
        [sys.executable, str(lint_script), str(md_path)],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        print(result.stderr, file=sys.stderr)
        return False
    return True


def parse_sourcemap(md_path):
    """解析 SOURCEMAP.md，返回结构化字典。"""
    # 必须先通过 lint
    if not lint_sourcemap(md_path):
        raise RuntimeError(f"SOURCEMAP lint failed: {md_path}")

    with open(md_path, "r", encoding="utf-8") as f:
        content = f.read()

    # 提取元数据
    engine_match = re.search(r'^# MaCode Engine Source Map:\s*(.+)$', content, re.MULTILINE)
    engine_name = engine_match.group(1).strip() if engine_match else "unknown"

    version_match = re.search(r'>\s*引擎版本:\s*(.+)$', content, re.MULTILINE)
    version = version_match.group(1).strip() if version_match else "unknown"

    adapter_match = re.search(r'>\s*适配层版本:\s*(.+)$', content, re.MULTILINE)
    adapter_version = adapter_match.group(1).strip() if adapter_match else "unknown"

    generated_at = datetime.now().isoformat()

    # WHITELIST
    whitelist = []
    for parts in parse_markdown_table(extract_section(content, "WHITELIST"), 4):
        # 格式: | 标识 | 路径/命令 | 用途 | 优先级 |
        whitelist.append({
            "id": parts[0],
            "path_raw": parts[1].strip("`"),
            "purpose": parts[2],
            "priority": parts[3]
        })

    # BLACKLIST
    blacklist = []
    for parts in parse_markdown_table(extract_section(content, "BLACKLIST"), 3):
        # 格式: | 标识 | 路径/命令 | 原因 |
        blacklist.append({
            "id": parts[0],
            "path_raw": parts[1].strip("`"),
            "reason": parts[2]
        })

    # EXTENSION
    extension = []
    for parts in parse_markdown_table(extract_section(content, "EXTENSION"), 3):
        # 格式: | 标识 | 描述 | 状态 |
        extension.append({
            "id": parts[0],
            "desc": parts[1],
            "status": parts[2]
        })

    # REDIRECT
    redirect = []
    for parts in parse_markdown_table(extract_section(content, "REDIRECT"), 3):
        # 格式: | Pitfall | Correct Approach | Reason |
        redirect.append({
            "pitfall": parts[0],
            "correct": parts[1],
            "reason": parts[2]
        })

    # 计算内容哈希
    content_hash = hashlib.sha256(content.encode("utf-8")).hexdigest()

    return {
        "engine": engine_name,
        "version": version,
        "adapter_version": adapter_version,
        "generated_at": generated_at,
        "source_md": str(md_path),
        "content_hash": content_hash,
        "whitelist": whitelist,
        "blacklist": blacklist,
        "extension": extension,
        "redirect": redirect,
    }


def write_json(data, out_path):
    """写入格式化 JSON。"""
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"[sourcemap-sync] {out_path}")


def sync_engine(engine_name, project_root):
    """同步单个引擎的 SOURCEMAP。"""
    md_path = Path(project_root) / "engines" / engine_name / "SOURCEMAP.md"
    if not md_path.exists():
        print(f"[sourcemap-sync] SKIP: {md_path} not found", file=sys.stderr)
        return False

    data = parse_sourcemap(md_path)
    out_path = Path(project_root) / ".agent" / "context" / f"{engine_name}_sourcemap.json"
    write_json(data, out_path)
    return True


def check_sync(engine_name, project_root):
    """检查 JSON 是否与 Markdown 同步（比较内容哈希）。"""
    md_path = Path(project_root) / "engines" / engine_name / "SOURCEMAP.md"
    json_path = Path(project_root) / ".agent" / "context" / f"{engine_name}_sourcemap.json"

    if not md_path.exists():
        return False, f"{md_path} not found"
    if not json_path.exists():
        return False, f"{json_path} not found (run sync first)"

    # 读取当前 Markdown 的内容哈希
    md_content = md_path.read_bytes()
    current_hash = hashlib.sha256(md_content).hexdigest()

    with open(json_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    recorded_hash = data.get("content_hash", "")
    if not recorded_hash:
        return False, "JSON missing content_hash (legacy, please re-sync)"

    if current_hash != recorded_hash:
        return False, f"SOURCEMAP.md content changed (hash mismatch)"

    return True, "sync OK"


def main():
    project_root = Path(__file__).parent.parent.resolve()
    args = sys.argv[1:]

    if "--all" in args:
        engines_dir = project_root / "engines"
        ok = 0
        for engine_dir in sorted(engines_dir.iterdir()):
            if engine_dir.is_dir():
                if sync_engine(engine_dir.name, project_root):
                    ok += 1
        print(f"[sourcemap-sync] {ok} engine(s) synced")
        return

    if "--check" in args:
        engine = next((a for a in args if not a.startswith("-")), None)
        if not engine:
            # 从 project.yaml 读取默认引擎
            py = project_root / ".venv" / "bin" / "python"
            if not py.exists():
                py = "python3"
            engine = os.popen(f'{py} -c "import yaml; print(yaml.safe_load(open(\'{project_root}/project.yaml\')).get(\'defaults\',{{}}).get(\'engine\',\'manim\'))" 2>/dev/null || echo manim"').read().strip()

        is_sync, msg = check_sync(engine, project_root)
        status = "✓" if is_sync else "✗"
        print(f"[sourcemap-sync] {status} {engine}: {msg}")
        sys.exit(0 if is_sync else 1)

    # 默认：同步指定引擎（或默认引擎）
    engine = args[0] if args else None
    if not engine:
        py = project_root / ".venv" / "bin" / "python"
        if not py.exists():
            py = "python3"
        engine = os.popen(f'{py} -c "import yaml; print(yaml.safe_load(open(\'{project_root}/project.yaml\')).get(\'defaults\',{{}}).get(\'engine\',\'manim\'))" 2>/dev/null || echo manim"').read().strip()

    if sync_engine(engine, project_root):
        print("[sourcemap-sync] Done")
    else:
        sys.exit(1)


if __name__ == "__main__":
    main()
