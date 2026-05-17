#!/usr/bin/env python3
"""bin/sourcemap-sync.py
JSON 为唯一事实源：engines/{engine}/sourcemap.json → SOURCEMAP.md（生成）+
.agent/context/*（派生）。

用法:
    sourcemap-sync.py [engine_name]     # 校验 JSON、写回 SOURCEMAP.md + .agent/context
    sourcemap-sync.py --all               # 同上，所有带 sourcemap.json 的引擎目录
    sourcemap-sync.py --check [engine]    # SOURCEMAP.md 是否与 JSON 生成一致（不落盘）
    sourcemap-sync.py --write-md-only [e] # 仅写 Markdown（调试用）
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import datetime
from pathlib import Path

try:
    from jsonschema import Draft202012Validator
except ImportError:
    Draft202012Validator = None  # type: ignore


def get_project_root() -> Path:
    return Path(__file__).parent.parent.resolve()


def schema_path(root: Path) -> Path:
    return root / "engines" / "sourcemap.schema.json"


def load_schema_validator(root: Path):
    if Draft202012Validator is None:
        print("FATAL: jsonschema is required. pip install jsonschema", file=sys.stderr)
        sys.exit(2)
    sp = schema_path(root)
    if not sp.is_file():
        print(f"FATAL: schema not found: {sp}", file=sys.stderr)
        sys.exit(2)
    schema = json.loads(sp.read_text(encoding="utf-8"))
    return Draft202012Validator(schema)


def validate_data(validator, data: dict, label: str) -> None:
    errors = sorted(validator.iter_errors(data), key=lambda e: list(e.path))
    if errors:
        print(f"FATAL: sourcemap JSON schema errors ({label}):", file=sys.stderr)
        for e in errors[:20]:
            print(f"  {'/'.join(str(p) for p in e.path)}: {e.message}", file=sys.stderr)
        if len(errors) > 20:
            print(f"  ... +{len(errors) - 20} more", file=sys.stderr)
        sys.exit(2)


def _esc_cell(s: str) -> str:
    return (s or "").replace("|", "\\|").replace("\n", " ")


def markdown_from_json(data: dict) -> str:
    """Deterministic Markdown view from canonical JSON."""
    lines: list[str] = []
    title = data.get("engine", "unknown")
    lines.append(f"# MaCode Engine Source Map: {_esc_cell(title)}")
    lines.append("")
    gen = data.get("generated_at", "")
    date_s = gen[:10] if gen else ""
    if date_s:
        lines.append(f"> 生成日期: {date_s}")
    lines.append(f"> 引擎版本: {_esc_cell(data.get('version', 'unknown'))}")
    lines.append(f"> 适配层版本: {_esc_cell(data.get('adapter_version', 'unknown'))}")
    sr = data.get("source_root")
    if sr:
        lines.append(f"> 源码根目录: `{_esc_cell(sr)}`")

    lines.append("")
    lines.append("## WHITELIST: 推荐探索路径")
    lines.append("")
    lines.append("| 标识 | 路径/命令 | 用途 | 优先级 |")
    lines.append("|------|-----------|------|--------|")
    for it in data.get("whitelist") or []:
        pid = _esc_cell(str(it.get("id", "")))
        raw = _esc_cell(str(it.get("path_raw", "")))
        purpose = _esc_cell(str(it.get("purpose", "")))
        pri = _esc_cell(str(it.get("priority", "")))
        lines.append(f"| {pid} | `{raw}` | {purpose} | {pri} |")

    lines.append("")
    lines.append("## BLACKLIST: 禁止/不建议探索")
    lines.append("")
    lines.append("| 标识 | 路径/命令 | 原因 |")
    lines.append("|------|-----------|------|")
    for it in data.get("blacklist") or []:
        pid = _esc_cell(str(it.get("id", "")))
        raw = _esc_cell(str(it.get("path_raw", "")))
        reason = _esc_cell(str(it.get("reason", "")))
        lines.append(f"| {pid} | `{raw}` | {reason} |")

    lines.append("")
    lines.append("## EXTENSION: 待补充/可添加")
    lines.append("")
    lines.append("| 标识 | 描述 | 状态 |")
    lines.append("|------|------|------|")
    for it in data.get("extension") or []:
        pid = _esc_cell(str(it.get("id", "")))
        desc = _esc_cell(str(it.get("desc", "")))
        st = _esc_cell(str(it.get("status", "")))
        lines.append(f"| {pid} | {desc} | {st} |")

    lines.append("")
    lines.append("## REDIRECT: Common Pitfall Corrections")
    lines.append("")
    lines.append("When you find yourself writing the left column, use the right column instead.")
    lines.append("")
    lines.append("| Pitfall | Correct Approach | Reason |")
    lines.append("|---------|-----------------|--------|")
    for it in data.get("redirect") or []:
        pit = _esc_cell(str(it.get("pitfall", "")))
        cor = _esc_cell(str(it.get("correct", "")))
        rea = _esc_cell(str(it.get("reason", "")))
        lines.append(f"| {pit} | {cor} | {rea} |")

    lines.append("")
    return "\n".join(lines)


def normalize_md(text: str) -> str:
    t = text.replace("\r\n", "\n").strip()
    return t + "\n"


def write_json(data: dict, out_path: Path) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"[sourcemap-sync] {out_path}")


def _write_api_txt(data: dict, out_path: Path) -> None:
    lines = [
        f"# Engine: {data['engine']}",
        f"# Version: {data['version']}  (Adapter: {data['adapter_version']})",
        f"# Generated: {data.get('generated_at', '')}",
        "",
        "## WHITELIST (P0 = core, P1 = common, P2 = advanced)",
        "",
    ]
    for item in data.get("whitelist", []):
        lines.append(f"[{item['priority']}] {item['id']}: {item['path_raw']}")
        lines.append(f"    Purpose: {item['purpose']}")
        lines.append("")

    if data.get("redirect"):
        lines.append("## REDIRECT (pitfall → correct approach)")
        lines.append("")
        for item in data["redirect"]:
            lines.append(f"AVOID: {item['pitfall']}")
            lines.append(f"  USE:  {item['correct']}")
            lines.append(f"  WHY:  {item['reason']}")
            lines.append("")

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text("\n".join(lines), encoding="utf-8")
    print(f"[sourcemap-sync] {out_path}")


def _write_blacklist_txt(data: dict, out_path: Path) -> None:
    lines = [
        f"# Engine: {data['engine']}",
        f"# Version: {data['version']}",
        "",
        "## BLACKLIST",
        "",
    ]
    for item in data.get("blacklist", []):
        lines.append(f"{item['id']}: {item['path_raw']}")
        lines.append(f"    Reason: {item['reason']}")
        lines.append("")

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text("\n".join(lines), encoding="utf-8")
    print(f"[sourcemap-sync] {out_path}")


def write_derived(engine: str, data: dict, root: Path) -> None:
    """Write SOURCEMAP.md + .agent/context copies."""
    md_path = root / "engines" / engine / "SOURCEMAP.md"
    md = markdown_from_json(data)
    md_path.parent.mkdir(parents=True, exist_ok=True)
    md_path.write_text(md, encoding="utf-8")
    print(f"[sourcemap-sync] {md_path}")

    content_hash = hashlib.sha256(md.encode("utf-8")).hexdigest()

    enriched = dict(data)
    enriched["generated_at"] = data.get("generated_at") or datetime.now().isoformat()
    enriched["source_md"] = f"engines/{engine}/SOURCEMAP.md"
    enriched["content_hash"] = content_hash

    out_path = root / ".agent" / "context" / f"{engine}_sourcemap.json"
    write_json(enriched, out_path)

    _write_api_txt(enriched, root / ".agent" / "context" / f"{engine}_api.txt")
    _write_blacklist_txt(enriched, root / ".agent" / "context" / f"{engine}_blacklist.txt")


def check_engine(engine: str, root: Path, validator) -> tuple[bool, str]:
    jp = root / "engines" / engine / "sourcemap.json"
    mp = root / "engines" / engine / "SOURCEMAP.md"
    if not jp.is_file():
        return False, f"{jp} not found"
    data = json.loads(jp.read_text(encoding="utf-8"))
    validate_data(validator, data, str(jp))
    if not mp.is_file():
        return False, f"{mp} not found"
    expected = normalize_md(markdown_from_json(data))
    actual = normalize_md(mp.read_text(encoding="utf-8"))
    if actual != expected:
        return (
            False,
            f"SOURCEMAP.md drift from engines/{engine}/sourcemap.json "
            f"(run: python3 bin/sourcemap-sync.py {engine})",
        )
    return True, "sync OK"


def sync_engine(engine: str, root: Path, validator, write_agent: bool = True) -> bool:
    ed = root / "engines" / engine
    if not ed.is_dir():
        print(f"[sourcemap-sync] SKIP: {ed} not a directory", file=sys.stderr)
        return False
    jp = ed / "sourcemap.json"
    if not jp.is_file():
        print(f"[sourcemap-sync] SKIP: {jp} not found", file=sys.stderr)
        return False
    data = json.loads(jp.read_text(encoding="utf-8"))
    validate_data(validator, data, str(jp))
    if write_agent:
        write_derived(engine, data, root)
    else:
        md_path = ed / "SOURCEMAP.md"
        md_path.write_text(markdown_from_json(data), encoding="utf-8")
        print(f"[sourcemap-sync] {md_path} (write-md-only)")
    return True


def default_engine_from_project(root: Path) -> str:
    try:
        import yaml  # type: ignore
    except ImportError:
        return "manimgl"
    try:
        raw = (root / "project.yaml").read_text(encoding="utf-8")
        d = yaml.safe_load(raw) or {}
        de = d.get("defaults") or {}
        if isinstance(de, dict) and de.get("engine"):
            return str(de["engine"])
    except (OSError, TypeError, ValueError):
        pass
    return "manimgl"


def main() -> None:
    parser = argparse.ArgumentParser(
        description="MaCode sourcemap: engines/{engine}/sourcemap.json is canonical.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "engine", nargs="?", help="Engine name (default: project.yaml defaults.engine)"
    )
    parser.add_argument("--all", action="store_true", help="Sync all engines with sourcemap.json")
    parser.add_argument(
        "--check", action="store_true", help="Verify SOURCEMAP.md matches JSON (no write)"
    )
    parser.add_argument(
        "--write-md-only",
        action="store_true",
        help="Only regenerate SOURCEMAP.md (no .agent/context)",
    )
    args = parser.parse_args()

    root = get_project_root()
    validator = load_schema_validator(root)

    if args.all:
        ok_count = 0
        engines_dir = root / "engines"
        for d in sorted(engines_dir.iterdir()):
            if d.is_dir() and (d / "sourcemap.json").is_file():
                if sync_engine(d.name, root, validator, write_agent=not args.write_md_only):
                    ok_count += 1
        print(f"[sourcemap-sync] {ok_count} engine(s) synced")
        return

    if args.check:
        engine = args.engine or default_engine_from_project(root)
        is_ok, msg = check_engine(engine, root, validator)
        status = "\u2713" if is_ok else "\u2717"
        print(f"[sourcemap-sync] {status} {engine}: {msg}")
        sys.exit(0 if is_ok else 1)

    engine = args.engine or default_engine_from_project(root)
    if sync_engine(engine, root, validator, write_agent=not args.write_md_only):
        print("[sourcemap-sync] Done")
    else:
        sys.exit(1)


if __name__ == "__main__":
    main()
