#!/usr/bin/env python3
"""bin/sourcemap-scan-api.py
Scan engine source for public APIs not yet covered by SOURCEMAP WHITELIST.

This is a **suggestion-only** tool: it does NOT modify SOURCEMAP.md.
It surfaces candidates for developer review, reducing the chance that
new engine capabilities remain invisible to Host Agents.

Usage:
    sourcemap-scan-api.py [engine_name]
    sourcemap-scan-api.py --all

Checks:
  1. Adapter layer files (engines/{name}/src/) missing from WHITELIST
  2. Python engine: top-level public classes/functions in key modules
  3. JS engine: exported symbols from package index files
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path


def get_project_root() -> Path:
    return Path(__file__).parent.parent.resolve()


def load_whitelist_ids(md_path: Path) -> set:
    """Extract identifier column from WHITELIST table."""
    ids = set()
    with open(md_path, encoding="utf-8") as f:
        content = f.read()
    section = re.search(r"^## WHITELIST:.*?(?=\n## |\Z)", content, re.DOTALL | re.MULTILINE)
    if not section:
        return ids
    for line in section.group(0).splitlines():
        if not line.startswith("|") or " 标识 " in line or "---" in line.replace("|", ""):
            continue
        parts = [p.strip() for p in line.split("|")]
        parts = [p for p in parts if p]
        if len(parts) >= 4:
            ids.add(parts[0])
    return ids


def scan_adapter_layer(engine: str, project_root: Path, whitelist_ids: set) -> list:
    """Find files in engines/{engine}/src/ not referenced by WHITELIST."""
    src_dir = project_root / "engines" / engine / "src"
    if not src_dir.exists():
        return []

    candidates = []
    for root, _dirs, files in os.walk(src_dir):
        for fname in files:
            if fname.startswith("_") or fname.endswith(".pyc"):
                continue
            fpath = Path(root) / fname
            rel = fpath.relative_to(src_dir).as_posix()
            # Check if any whitelist id references this path
            referenced = any(rel in lid.lower() or lid.lower() in rel for lid in whitelist_ids)
            if not referenced:
                candidates.append({
                    "type": "adapter_file",
                    "path": f"engines/{engine}/src/{rel}",
                    "suggested_id": f"ADAPTER_{rel.replace('/', '_').replace('.', '_').upper()}",
                })
    return candidates


def scan_python_public_api(engine: str, project_root: Path, whitelist_ids: set) -> list:
    """Scan key Python modules for public classes/functions not in WHITELIST."""
    candidates = []

    if engine == "manim":
        py = project_root / ".venv" / "bin" / "python"
    elif engine == "manimgl":
        py = project_root / ".venv-manimgl" / "bin" / "python"
    else:
        return candidates

    if not py.exists():
        return candidates

    # Ask Python for the package path and key submodules
    script = """
import sys, json, ast, inspect, importlib
engine = sys.argv[1]
try:
    if engine == "manim":
        import manim
        pkg = manim
    elif engine == "manimgl":
        import manimlib
        pkg = manimlib
    else:
        sys.exit(0)
    pkg_dir = pkg.__path__[0]
    results = []
    # Scan key submodules known to contain public API
    targets = ["scene", "mobject", "animation", "camera", "utils"]
    for target in targets:
        mod_path = os.path.join(pkg_dir, target)
        if not os.path.isdir(mod_path):
            continue
        for root, dirs, files in os.walk(mod_path):
            # Skip test dirs and internal
            dirs[:] = [d for d in dirs if not d.startswith("_") and d not in ("test", "tests", "__pycache__")]
            for f in files:
                if not f.endswith(".py") or f.startswith("_"):
                    continue
                fp = os.path.join(root, f)
                try:
                    with open(fp, "r", encoding="utf-8") as src:
                        tree = ast.parse(src.read(), filename=fp)
                except Exception:
                    continue
                for node in ast.iter_child_nodes(tree):
                    if isinstance(node, ast.ClassDef):
                        # Heuristic: public class, not internal
                        if not node.name.startswith("_"):
                            results.append({"kind": "class", "name": node.name, "module": target, "file": os.path.relpath(fp, pkg_dir)})
                    elif isinstance(node, ast.FunctionDef):
                        if not node.name.startswith("_") and node.name[0].islower():
                            results.append({"kind": "function", "name": node.name, "module": target, "file": os.path.relpath(fp, pkg_dir)})
    print(json.dumps(results))
except Exception as e:
    print(json.dumps({"error": str(e)}))
"""
    import subprocess
    try:
        result = subprocess.run(
            [str(py), "-c", script, engine],
            capture_output=True, text=True, timeout=30, cwd=str(project_root),
        )
        if result.returncode == 0:
            data = json.loads(result.stdout)
            if isinstance(data, list):
                seen_names = set()
                for item in data:
                    name = item["name"]
                    if name in seen_names:
                        continue
                    seen_names.add(name)
                    # Check if name or a close variant is in whitelist
                    covered = any(name.lower() in lid.lower() or lid.lower() in name.lower() for lid in whitelist_ids)
                    if not covered:
                        candidates.append({
                            "type": "public_api",
                            "kind": item["kind"],
                            "name": name,
                            "module": item["module"],
                            "file": item["file"],
                        })
    except Exception:
        pass

    return candidates


def scan_js_exports(engine: str, project_root: Path, whitelist_ids: set) -> list:
    """Scan Motion Canvas package exports for symbols not in WHITELIST."""
    candidates = []
    if engine != "motion_canvas":
        return candidates

    # Read package index files for exported symbols
    packages = [
        "@motion-canvas/core",
        "@motion-canvas/2d",
    ]
    for pkg in packages:
        idx = project_root / "node_modules" / pkg / "lib" / "index.js"
        if not idx.exists():
            continue
        try:
            content = idx.read_text(encoding="utf-8")
            # Extract export { ... } lines
            for m in re.finditer(r"export\s*\{([^}]+)\}", content):
                for sym in m.group(1).split(","):
                    sym = sym.strip().split(" as ")[-1].strip()
                    if not sym:
                        continue
                    covered = any(sym.lower() in lid.lower() or lid.lower() in sym.lower() for lid in whitelist_ids)
                    if not covered and len(sym) > 2:
                        candidates.append({
                            "type": "js_export",
                            "package": pkg,
                            "name": sym,
                        })
        except Exception:
            pass
    return candidates


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Scan engine source for APIs not yet in SOURCEMAP WHITELIST.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("engine", nargs="?", help="Engine name")
    parser.add_argument("--all", action="store_true", help="Scan all engines")
    parser.add_argument("--json", action="store_true", help="Output JSON")
    args = parser.parse_args()

    project_root = get_project_root()

    engines = []
    if args.all:
        engines_dir = project_root / "engines"
        if engines_dir.exists():
            engines = sorted([d.name for d in engines_dir.iterdir() if d.is_dir() and (d / "SOURCEMAP.md").exists()])
    elif args.engine:
        engines = [args.engine]
    else:
        engines_dir = project_root / "engines"
        if engines_dir.exists():
            engines = sorted([d.name for d in engines_dir.iterdir() if d.is_dir() and (d / "SOURCEMAP.md").exists()])

    all_results = []
    total_candidates = 0

    for engine in engines:
        md_path = project_root / "engines" / engine / "SOURCEMAP.md"
        whitelist_ids = load_whitelist_ids(md_path)
        candidates = []
        candidates.extend(scan_adapter_layer(engine, project_root, whitelist_ids))
        candidates.extend(scan_python_public_api(engine, project_root, whitelist_ids))
        candidates.extend(scan_js_exports(engine, project_root, whitelist_ids))

        # Deduplicate by path+name
        seen = set()
        unique = []
        for c in candidates:
            key = c.get("path", "") + ":" + c.get("name", "")
            if key not in seen:
                seen.add(key)
                unique.append(c)

        all_results.append({
            "engine": engine,
            "whitelist_count": len(whitelist_ids),
            "candidates": unique,
        })
        total_candidates += len(unique)

    if args.json:
        print(json.dumps({
            "total_candidates": total_candidates,
            "engines": all_results,
        }, indent=2, ensure_ascii=False))
    else:
        print("=== SOURCEMAP API Scan ===")
        for r in all_results:
            print(f"\n{r['engine']} (WHITELIST: {r['whitelist_count']} items)")
            if not r["candidates"]:
                print("  ✓ No obvious gaps detected")
                continue
            for c in r["candidates"][:15]:  # Limit output
                if c["type"] == "adapter_file":
                    print(f"  ~ Adapter file not in WHITELIST: {c['path']} (suggest: {c['suggested_id']})")
                elif c["type"] == "public_api":
                    print(f"  ~ Public {c['kind']}: {c['name']} in {c['module']} (file: {c['file']})")
                elif c["type"] == "js_export":
                    print(f"  ~ JS export: {c['name']} from {c['package']}")
            if len(r["candidates"]) > 15:
                print(f"  ... and {len(r['candidates']) - 15} more")
        print("")
        if total_candidates:
            print(f"Found {total_candidates} candidate(s) not covered by WHITELIST.")
            print("Review and add relevant items to engines/{{engine}}/SOURCEMAP.md")
        else:
            print("All scanned APIs appear covered by WHITELIST.")

    return 0


if __name__ == "__main__":
    sys.exit(main())
