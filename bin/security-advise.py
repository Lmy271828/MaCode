#!/usr/bin/env python3
"""bin/security-advise.py
Convert security checker output into actionable, LLM-friendly advice.

Usage:
    security-advise.py <checker_name> <violation_json>

Design: thin translator. No checking logic — only pattern-to-advice mapping.
"""

import sys

ADVICE_DB = {
    "subprocess": {
        "rule": "Agent must not use subprocess, os.system, or os.popen in scene code",
        "why": "Scene code runs inside MaCode's render pipeline. Arbitrary command execution breaks reproducibility, security sandbox, and cross-platform compatibility.",
        "fix": "Use macode-run for any external command needs, or refactor to pure Python/engine APIs.",
        "docs": "AGENTS.md §5.2 Layer 1 — Runtime Enforcement",
    },
    "os.system()": {
        "rule": "Agent must not use os.system() in scene code",
        "why": "os.system() executes arbitrary shell commands, bypassing MaCode's process lifecycle management (macode-run) and audit trails.",
        "fix": "If you need to run an external tool, use 'macode-run <task_id> -- <command>' from the orchestration layer, not from scene code.",
        "docs": "AGENTS.md §8 反模式 — '使用 subprocess, os.system, socket, requests'",
    },
    "socket": {
        "rule": "Agent must not use socket or network libraries in scene code",
        "why": "Scene code must be deterministic and offline. Network access introduces non-reproducibility and security risks.",
        "fix": "Pre-download all assets to scenes/<name>/assets/ or assets/. Scene code should only read local files.",
        "docs": "AGENTS.md §5.2 Layer 1 — Runtime Enforcement",
    },
    "requests": {
        "rule": "Agent must not use requests or urllib in scene code",
        "why": "Same as socket — scene code must be offline-deterministic.",
        "fix": "Use 'curl' or 'wget' from the setup/bootstrap phase (outside scene code), or pre-download assets.",
        "docs": "AGENTS.md §5.2 Layer 1 — Runtime Enforcement",
    },
    "shutil.rmtree()": {
        "rule": "Agent must not use shutil.rmtree() in scene code",
        "why": "Recursive deletion is dangerous and should be handled by MaCode's cleanup tools (macode cleanup).",
        "fix": "Do not delete files in scene code. Temporary files go to .agent/tmp/. MaCode handles cleanup.",
        "docs": "bin/macode cleanup --help",
    },
    "GLSL": {
        "rule": "Agent must not write GLSL shader code directly",
        "why": "GLSL is a low-level primitive. MaCode manages shader compilation through Effect Registry to ensure cross-engine compatibility (ManimGL OpenGL vs Motion Canvas WebGL2).",
        "fix": "Declare the effect in scene manifest or use the component API: <ShaderFrame src='effects://pulse-wave' color='red' />",
        "docs": "docs/security-architecture.md §Layer 3 — Infrastructure Isolation",
    },
    "raw LaTeX cases": {
        "rule": "Agent must not write raw LaTeX environments (\\begin{cases}, \\begin{bmatrix}, etc.)",
        "why": "Raw LaTeX is error-prone and engine-specific. MaCode provides latex_helper utilities that generate correct LaTeX for both ManimCE and ManimGL.",
        "fix": "Use utils.latex_helper.cases([...]) instead of '\\\\begin{cases}...\\\\end{cases}'",
        "docs": "engines/manim/SOURCEMAP.md WHITELIST — latex_helper",
    },
    "hand-written ffmpeg": {
        "rule": "Agent must not write hand-crafted ffmpeg command strings",
        "why": "ffmpeg filtergraph syntax is fragile and version-sensitive. MaCode's ffmpeg_builder generates correct filtergraphs with proper escaping.",
        "fix": "Use utils.ffmpeg_builder.FFMpegBuilder() to construct filtergraphs programmatically.",
        "docs": "engines/manim/SOURCEMAP.md WHITELIST — ffmpeg_builder",
    },
    "forbidden directory: engines/": {
        "rule": "Agent must not write to engines/, bin/, pipeline/, tests/, or docs/",
        "why": "These directories contain MaCode's infrastructure code. Modifying them breaks the Harness for all scenes.",
        "fix": "All scene-specific code belongs in scenes/<name>/. Shared assets belong in assets/. If you need a new engine feature, request it via an issue rather than modifying engine code.",
        "docs": "AGENTS.md §5.2 Layer 3 — Infrastructure Isolation",
    },
    "forbidden file: project.yaml": {
        "rule": "Agent must not modify project.yaml",
        "why": "project.yaml contains global project configuration (version, defaults, resource limits). Changes affect all scenes.",
        "fix": "Scene-specific configuration goes in scenes/<name>/manifest.json. If you need to change global defaults, request it explicitly.",
        "docs": "AGENTS.md §5.2 Layer 3 — Infrastructure Isolation",
    },
}


def lookup_advice(violation_desc: str) -> dict:
    """Fuzzy match violation description to advice entry."""
    for key, advice in ADVICE_DB.items():
        if key.lower() in violation_desc.lower():
            return advice
    return {
        "rule": "Unknown violation (not in advice database)",
        "why": "Please report this to MaCode maintainers.",
        "fix": "Review the checker output and consult the relevant SOURCEMAP.md or AGENTS.md section.",
        "docs": "AGENTS.md §5 — Security Model",
    }


def format_advice(checker: str, violation: str, location: str = "") -> str:
    advice = lookup_advice(violation)
    lines = [
        f"[{checker.upper()}_VIOLATION]",
        f"  Location: {location or 'unknown'}",
        f"  Found:    {violation}",
        f"  Rule:     {advice['rule']}",
        f"  Why:      {advice['why']}",
        f"  Fix:      {advice['fix']}",
        f"  Docs:     {advice['docs']}",
    ]
    return "\n".join(lines)


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Convert security violations to actionable advice.")
    parser.add_argument("checker", help="Checker name (sandbox, primitive, fs, api-gate)")
    parser.add_argument("--location", default="", help="File location")
    parser.add_argument("violation", nargs="?", help="Violation description")
    args = parser.parse_args()

    if not args.violation and not sys.stdin.isatty():
        args.violation = sys.stdin.read().strip()

    if not args.violation:
        parser.print_help()
        sys.exit(2)

    print(format_advice(args.checker, args.violation, args.location))


if __name__ == "__main__":
    main()
