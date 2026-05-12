"""engines/manimgl/src/utils/lygia_resolver.py
Resolve LYGIA ``#include`` directives into self-contained GLSL.

LYGIA (https://lygia.xyz) is a granular shader function library by
Patricio Gonzalez Vivo. It uses ``#include`` with relative paths.
This module recursively expands those includes so the output can be
fed directly into moderngl or glslViewer without an external resolver.

Usage::

    from utils.lygia_resolver import resolve_lygia
    from pathlib import Path

    frag = '''
    #include "lygia/draw/circle.glsl"
    void main() { gl_FragColor = vec4(circle(uv, 0.5), 0.0, 0.0, 1.0); }
    '''
    resolved, deps = resolve_lygia(frag)
"""

from __future__ import annotations

import re
from pathlib import Path

# Default LYGIA root relative to MaCode project root.
# Consumers can override via environment variable MACODE_LYGIA_ROOT.
_DEFAULT_LYGIA_ROOT = Path(__file__).parent.parent.parent.parent.parent / "assets" / "shaders" / "lygia"


def _get_lygia_root() -> Path:
    import os
    env = os.environ.get("MACODE_LYGIA_ROOT")
    if env:
        return Path(env).resolve()
    return _DEFAULT_LYGIA_ROOT.resolve()


_INCLUDE_RE = re.compile(
    r'^\s*#include\s+"([^"]+)"\s*$',
    re.MULTILINE,
)


def _resolve_include_path(include_str: str, current_file: Path | None) -> Path | None:
    """Map an include string to an absolute file path."""
    lygia_root = _get_lygia_root()

    # Case 1: absolute-ish LYGIA path, e.g. "lygia/space/ratio.glsl"
    if include_str.startswith("lygia/"):
        target = lygia_root / include_str.removeprefix("lygia/")
        if target.exists():
            return target.resolve()
        return None

    # Case 2: relative to current file, e.g. "../sdf/circleSDF.glsl"
    if current_file is not None:
        target = current_file.parent / include_str
        if target.exists():
            return target.resolve()

    # Case 3: bare name relative to LYGIA root, e.g. "math/const.glsl"
    target = lygia_root / include_str
    if target.exists():
        return target.resolve()

    return None


def resolve_lygia(
    source: str,
    current_file: Path | None = None,
    visited: set[str] | None = None,
) -> tuple[str, list[str]]:
    """Recursively expand LYGIA ``#include`` directives.

    Args:
        source: GLSL source that may contain ``#include"..."`` lines.
        current_file: path to the file *source* came from (for resolving
            relative includes).  ``None`` when resolving a raw string.
        visited: set of already-included absolute paths (cycle detection).

    Returns:
        (expanded_source, list_of_included_relative_paths)
    """
    if visited is None:
        visited = set()

    deps: list[str] = []

    def replacer(match: re.Match) -> str:
        include_str = match.group(1)
        target = _resolve_include_path(include_str, current_file)

        if target is None:
            return f"// MISSING LYGIA INCLUDE: {include_str}\n"

        abs_path = str(target)
        if abs_path in visited:
            # LYGIA functions are guarded by #ifndef FNC_XXX,
            # so re-including is harmless. We skip the content to avoid bloat.
            return f"// ALREADY INCLUDED: {include_str}\n"

        visited.add(abs_path)
        deps.append(include_str)

        with open(target, encoding="utf-8") as f:
            content = f.read()

        expanded, nested_deps = resolve_lygia(content, current_file=target, visited=visited)
        deps.extend(nested_deps)
        return expanded

    expanded = _INCLUDE_RE.sub(replacer, source)
    return expanded, deps


def build_shader_from_lygia(
    frag_includes: list[str],
    vert_includes: list[str] | None = None,
    frag_body: str = "",
    vert_body: str = "",
    uniforms: str = "",
) -> tuple[str, str]:
    """Convenience: build a self-contained vert/frag pair from LYGIA includes.

    Args:
        frag_includes: list of LYGIA paths for fragment shader, e.g.
            ["lygia/draw/circle.glsl", "lygia/color/palette/heatmap.glsl"]
        vert_includes: same for vertex shader (usually empty for fullscreen)
        frag_body: code inside ``void main() { ... }``
        vert_body: same for vertex shader
        uniforms: extra uniform declarations

    Returns:
        (vertex_shader, fragment_shader)
    """
    # Default fullscreen vertex shader
    if vert_body:
        vert = f"""#version 330
in vec2 in_pos;
void main() {{
    gl_Position = vec4(in_pos, 0.0, 1.0);
    {vert_body}
}}
"""
    else:
        vert = """#version 330
in vec2 in_pos;
void main() {
    gl_Position = vec4(in_pos, 0.0, 1.0);
}
"""

    frag_preamble = "#version 330\n\n"
    if uniforms:
        frag_preamble += uniforms + "\n\n"
    frag_preamble += "out vec4 fragColor;\n\n"

    # Resolve all fragment includes
    resolved_frag = ""
    for inc in frag_includes:
        src = f'#include "{inc}"\n'
        expanded, _ = resolve_lygia(src)
        resolved_frag += expanded + "\n"

    frag = frag_preamble + resolved_frag + f"""
void main() {{
    {frag_body}
}}
"""
    return vert, frag


def _test():
    """Quick sanity tests."""
    root = _get_lygia_root()
    print(f"LYGIA root: {root}")
    assert root.exists(), f"LYGIA not found at {root}"

    # Test 1: simple self-contained function
    src = '#include "lygia/color/palette/heatmap.glsl"\n'
    out, deps = resolve_lygia(src)
    assert "FNC_HEATMAP" in out
    assert "#include" not in out
    print("Test 1 (heatmap): PASSED")

    # Test 2: nested includes (circle → circleSDF → fill/stroke)
    src2 = '#include "lygia/draw/circle.glsl"\n'
    out2, deps2 = resolve_lygia(src2)
    assert "FNC_CIRCLE" in out2
    assert "FNC_CIRCLESDF" in out2
    assert "#include" not in out2
    print("Test 2 (circle nested): PASSED")
    print(f"  deps: {deps2}")

    # Test 3: build_shader_from_lygia
    v, f = build_shader_from_lygia(
        frag_includes=["lygia/draw/circle.glsl", "lygia/color/palette/heatmap.glsl"],
        frag_body="vec2 uv = gl_FragCoord.xy / resolution.xy;\nfragColor = vec4(heatmap(circle(uv, 0.5)), 1.0);",
        uniforms="uniform vec2 resolution;",
    )
    assert "void main()" in f
    assert "#include" not in f
    print("Test 3 (build_shader): PASSED")


if __name__ == "__main__":
    _test()
