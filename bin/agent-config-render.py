#!/usr/bin/env python3
"""bin/agent-config-render.py
Render IDE-specific agent configs from docs/agent-config-source.md.

Usage:
    agent-config-render.py [--check]

Without --check: regenerates .cursorrules, .windsurf/rules.md, .aider.conf.yml
With --check:    exits 1 if any generated file is out of sync
"""
from __future__ import annotations

import argparse
import json
import os
import sys

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SOURCE_PATH = os.path.join(PROJECT_ROOT, "docs", "agent-config-source.md")


def _read_source() -> str:
    with open(SOURCE_PATH, encoding="utf-8") as f:
        return f.read()


def _extract_body(text: str) -> str:
    # Drop YAML frontmatter
    if text.startswith("---"):
        parts = text.split("---", 2)
        if len(parts) >= 3:
            return parts[2].strip()
    return text.strip()


def _render_cursorrules(body: str) -> str:
    return body + "\n"


def _render_windsurf(body: str) -> str:
    # Same as cursorrules for now
    return body + "\n"


def _render_aider(body: str) -> str:
    lines = body.splitlines()
    out = ["# MaCode — Math Animation Harness", "# Aider project configuration", ""]
    out.append("# MaCode manages Git explicitly; disable auto-commits")
    out.append("auto-commits: false")
    out.append("")
    out.append("# ---------------------------------------------------------------------------")
    out.append("# SECURITY RULES for Host Agent working in MaCode")
    out.append("# ---------------------------------------------------------------------------")
    out.append("")

    current_section = None
    for line in lines:
        if line.startswith("## "):
            current_section = line[3:].strip().lower()
            out.append(f"# {line[3:].strip()}")
            continue
        if line.startswith("- "):
            item = line[2:].strip()
            if current_section and "allowed" in current_section:
                out.append(f"#   {item}")
            elif current_section and "require" in current_section:
                out.append(f"#   {item}")
            elif current_section and "never" in current_section:
                out.append(f"#   {item}")
            else:
                out.append(f"# {item}")
        elif line.strip() == "":
            out.append("")
        else:
            out.append(f"# {line}")
    return "\n".join(out) + "\n"


def _render_claude(body: str) -> str:
    # Minimal JSON wrapper — full permissions array is kept static
    # because Claude Code uses a structured JSON schema.
    permissions = {
        "allow": [
            "Bash(macode status)", "Bash(macode status *)", "Bash(macode inspect *)",
            "Bash(macode engine)", "Bash(macode engine *)", "Bash(ls *)",
            "Bash(cat *)", "Bash(jq *)", "Bash(tail -n *)", "Bash(head -n *)",
            "Bash(find *)", "Bash(grep *)", "Bash(du -sh *)", "Bash(ps *)",
            "Bash(ffprobe *)", "Bash(manim --version)", "Bash(ffmpeg -version)",
            "Bash(node --version)", "Bash(python3 bin/discover)",
            "Bash(macode check *)", "Bash(macode dry-run *)", "Bash(macode render *)",
            "Bash(macode render-all)", "Bash(pipeline/render.sh *)",
            "Bash(git status)", "Bash(git diff)", "Bash(git log)",
            "Bash(git add scenes/*)", "Bash(git commit -m *)",
        ],
        "require_confirmation": [
            "Bash(rm -rf *)", "Bash(sudo *)", "Bash(pip install *)",
            "Bash(npm install *)", "Bash(git push *)", "Bash(git reset --hard *)",
            "Bash(git clean -fd *)", "Bash(curl *)", "Bash(wget *)",
            "EditFile(engines/*)", "EditFile(bin/*)", "EditFile(pipeline/*)",
        ],
        "never": [
            "Bash(access .git/config)", "Bash(access .macode/*)",
            "Bash(access .claude/*)", "EditFile(engines/*/src/*)",
            "Bash(pip install *)", "Bash(npm install -g *)",
            "Bash(git push --force)", "Bash(git reset --hard)",
            "Bash(python3 scene.py)",
        ],
    }
    return json.dumps({"permissions": permissions}, indent=2, ensure_ascii=False) + "\n"


TARGETS = {
    ".cursorrules": _render_cursorrules,
    ".windsurf/rules.md": _render_windsurf,
    ".aider.conf.yml": _render_aider,
    ".claude/settings.local.json": _render_claude,
}


def main() -> int:
    parser = argparse.ArgumentParser(description="Render IDE agent configs from unified source")
    parser.add_argument("--check", action="store_true", help="Exit 1 if any target is out of sync")
    args = parser.parse_args()

    if not os.path.isfile(SOURCE_PATH):
        print(f"Error: source not found: {SOURCE_PATH}", file=sys.stderr)
        return 1

    body = _read_source()
    body = _extract_body(body)

    mismatched = []
    for rel_path, renderer in TARGETS.items():
        target_path = os.path.join(PROJECT_ROOT, rel_path)
        expected = renderer(body)
        if args.check:
            if not os.path.isfile(target_path):
                print(f"[CHECK] Missing: {rel_path}")
                mismatched.append(rel_path)
                continue
            with open(target_path, encoding="utf-8") as f:
                actual = f.read()
            if actual.strip() != expected.strip():
                print(f"[CHECK] Mismatch: {rel_path}")
                mismatched.append(rel_path)
        else:
            os.makedirs(os.path.dirname(target_path) or PROJECT_ROOT, exist_ok=True)
            with open(target_path, "w", encoding="utf-8") as f:
                f.write(expected)
            print(f"[RENDER] {rel_path}")

    if args.check:
        if mismatched:
            print(f"[CHECK] {len(mismatched)} file(s) out of sync", file=sys.stderr)
            return 1
        print("[CHECK] All files in sync")
        return 0
    return 0


if __name__ == "__main__":
    sys.exit(main())
