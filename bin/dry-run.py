#!/usr/bin/env python3
"""bin/dry-run.py
Fast pre-render validation tool for MaCode scenes.

Checks without running full scene renders:
1. Python syntax (py_compile)
2. Imports (importlib.util.find_spec)
3. LaTeX formulas (AST extraction + precompile_formulas)
4. FFmpeg filtergraphs (syntax validation with lavfi test sources)

Usage:
    bin/dry-run.py <scene_file> [engine]

Exit codes:
    0 - PASS
    1 - FAIL
    2 - Argument or file error
"""

from __future__ import annotations

import argparse
import ast
import glob
import importlib.util
import os
import py_compile
import re
import subprocess
import sys
import tempfile
import warnings

# ------------------------------------------------------------------
# Constants
# ------------------------------------------------------------------

LATEX_FUNC_NAMES = {
    "MathTex",
    "ChineseMathTex",
    "Tex",
    "SingleStringMathTex",
    "math",
    "cases",
    "matrix",
    "align_eqns",
    "integral",
    "derivative",
    "precompile_formulas",
}

VIDEO_FILTERS = {
    "fade",
    "scale",
    "crop",
    "fps",
    "format",
    "trim",
    "setpts",
    "hstack",
    "vstack",
    "overlay",
    "concat",
    "colorbalance",
}
AUDIO_FILTERS = {
    "afade",
    "atrim",
    "asetpts",
    "amix",
    "volume",
    "aecho",
    "afreqshift",
    "allpass",
    "amerge",
}


def _classify_filter_type(fstr: str) -> str:
    """Classify a raw filter string as vf, af, or filter_complex."""
    if ";" in fstr or ("[" in fstr and "]" in fstr):
        return "filter_complex"
    # Use whole-filter matching to avoid ``afade`` matching ``fade``.
    audio_rx = re.compile(r"(?:^|,)(" + "|".join(AUDIO_FILTERS) + r")=")
    video_rx = re.compile(r"(?:^|,)(" + "|".join(VIDEO_FILTERS) + r")=")
    has_audio = bool(audio_rx.search(fstr))
    has_video = bool(video_rx.search(fstr))
    if has_audio and not has_video:
        return "af"
    return "vf"


FFMPEG_TESTSRC = "testsrc=duration=1:size=320x240:rate=1"
FFMPEG_ANULLSRC = "anullsrc=duration=1:sample_rate=44100"


# ------------------------------------------------------------------
# Environment bootstrap
# ------------------------------------------------------------------


def _ensure_manim_importable():
    """Ensure the venv site-packages are on sys.path if manim is not already importable."""
    try:
        import manim  # noqa: F401

        return
    except ImportError:
        pass

    venv_site = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".venv", "lib"
    )
    if os.path.isdir(venv_site):
        for entry in os.listdir(venv_site):
            sp = os.path.join(venv_site, entry, "site-packages")
            if os.path.isdir(sp) and sp not in sys.path:
                sys.path.insert(0, sp)


def _add_engine_src(engine: str):
    """Add engines/<engine>/src/ to sys.path so ``utils.*`` and ``templates.*`` resolve."""
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    engine_src = os.path.join(project_root, "engines", engine, "src")
    if os.path.isdir(engine_src) and engine_src not in sys.path:
        sys.path.insert(0, engine_src)


# ------------------------------------------------------------------
# 1. Python syntax check
# ------------------------------------------------------------------


def check_python_syntax(path: str) -> tuple[bool, list[str]]:
    """Run py_compile on *path* and any companion ``.py`` files in the same directory."""
    files = [path]
    companion_dir = os.path.dirname(path)
    files.extend(sorted(glob.glob(os.path.join(companion_dir, "*.py"))))
    files = list(dict.fromkeys(files))  # dedupe, preserve order
    # Skip non-Python files (e.g. .tsx scenes)
    files = [f for f in files if f.endswith(".py")]

    if not files:
        return True, []

    errors = []
    for f in files:
        try:
            py_compile.compile(f, doraise=True)
        except py_compile.PyCompileError as exc:
            errors.append(f"{f}: {exc}")
    return (not errors), errors


# ------------------------------------------------------------------
# 2. Import check
# ------------------------------------------------------------------


def _resolve_module_name(node: ast.Import | ast.ImportFrom) -> list[str]:
    """Return the list of module names to check for an import node."""
    if isinstance(node, ast.Import):
        return [alias.name for alias in node.names]
    if isinstance(node, ast.ImportFrom):
        if node.module is None:
            return []
        if node.level and node.level > 0:
            # Relative imports are skipped in this lightweight check
            return []
        return [node.module]
    return []


def check_imports(path: str, engine: str) -> tuple[bool, list[tuple[str, int, str]]]:
    """Verify that every top-level import in *path* and companion scripts resolves."""
    _add_engine_src(engine)

    files = [path]
    companion_dir = os.path.dirname(path)
    files.extend(sorted(glob.glob(os.path.join(companion_dir, "*.py"))))
    files = list(dict.fromkeys(files))
    # Skip non-Python files
    files = [f for f in files if f.endswith(".py")]

    if not files:
        return True, []

    failures: list[tuple[str, int, str]] = []  # (file, line, module)
    checked = set()

    for f in files:
        try:
            with open(f, encoding="utf-8") as fh:
                source = fh.read()
        except OSError:
            continue
        try:
            tree = ast.parse(source, filename=f)
        except SyntaxError:
            continue

        for node in ast.walk(tree):
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                for mod in _resolve_module_name(node):
                    if mod in checked:
                        continue
                    checked.add(mod)
                    spec = importlib.util.find_spec(mod)
                    if spec is None:
                        # For dotted imports, if the submodule is missing but
                        # the top-level package exists, report the submodule.
                        # If the top-level itself is missing, report that for
                        # clearer diagnostics.
                        if "." in mod:
                            top = mod.split(".")[0]
                            if top not in checked:
                                checked.add(top)
                                top_spec = importlib.util.find_spec(top)
                                if top_spec is None:
                                    failures.append((f, getattr(node, "lineno", 0), top))
                                    continue
                        failures.append((f, getattr(node, "lineno", 0), mod))

    return (not failures), failures


# ------------------------------------------------------------------
# 3. LaTeX dry-run
# ------------------------------------------------------------------


def _safe_ast_eval(node: ast.AST):
    """Safely evaluate an AST node containing literals."""
    if isinstance(node, ast.Constant):
        return node.value
    if isinstance(node, ast.List):
        return [_safe_ast_eval(e) for e in node.elts]
    if isinstance(node, ast.Tuple):
        return tuple(_safe_ast_eval(e) for e in node.elts)
    if isinstance(node, ast.Dict):
        return {
            _safe_ast_eval(k): _safe_ast_eval(v)
            for k, v in zip(node.keys, node.values, strict=False)
        }
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.USub):
        val = _safe_ast_eval(node.operand)
        return -val if val is not None else None
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
        left = _safe_ast_eval(node.left)
        right = _safe_ast_eval(node.right)
        if left is not None and right is not None:
            return left + right
    return None


def _extract_latex_strings(path: str) -> list[tuple[str, int, str]]:
    """Extract (file, line, formula_or_marker) from AST for direct LaTeX calls."""
    results: list[tuple[str, int, str]] = []
    try:
        with open(path, encoding="utf-8") as f:
            source = f.read()
        tree = ast.parse(source, filename=path)
    except (OSError, SyntaxError):
        return results

    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        if not isinstance(node.func, ast.Name):
            continue
        name = node.func.id
        if name not in LATEX_FUNC_NAMES:
            continue

        if name == "precompile_formulas":
            # Extract list elements
            if node.args:
                lst = _safe_ast_eval(node.args[0])
                if isinstance(lst, list):
                    for item in lst:
                        if isinstance(item, str):
                            results.append((path, node.lineno, item))
            continue

        if name in ("cases", "matrix", "align_eqns", "integral", "derivative"):
            # These are helper functions; we will call them directly later.
            # Record a marker so we know to evaluate them.
            results.append((path, node.lineno, f"__helper__:{name}"))
            continue

        if name in ("MathTex", "ChineseMathTex", "Tex", "SingleStringMathTex", "math"):
            if node.args:
                val = _safe_ast_eval(node.args[0])
                if isinstance(val, str):
                    results.append((path, node.lineno, val))
            continue

    return results


def _call_latex_helper(path: str, helper_name: str, node: ast.Call):
    """Import latex_helper and call *helper_name* with evaluated AST args."""
    try:
        import utils.latex_helper as lh  # noqa: PLC0415
    except Exception as exc:
        raise RuntimeError(f"Cannot import latex_helper: {exc}") from exc

    func = getattr(lh, helper_name)
    args = [_safe_ast_eval(a) for a in node.args]
    kwargs = {kw.arg: _safe_ast_eval(kw.value) for kw in node.keywords}
    # None means unsupported AST construct
    if any(a is None for a in args):
        raise ValueError("Unsupported argument expression")
    if any(v is None for v in kwargs.values()):
        raise ValueError("Unsupported keyword argument expression")
    return func(*args, **kwargs)


def check_latex(path: str, engine: str) -> tuple[bool, int, int, list[tuple[str, int, str, str]]]:
    """Precompile LaTeX formulas found in *path*.

    Returns (ok, success_count, total_count, failures)
    where failures is a list of (file, line, formula, error_msg).
    """
    if not path.endswith(".py"):
        return True, 0, 0, []

    _add_engine_src(engine)
    try:
        import utils.latex_helper as lh  # noqa: PLC0415
    except Exception as exc:
        # If we cannot import latex_helper, skip LaTeX dry-run.
        print(f"[dry-run] LaTeX dry-run skipped: cannot import latex_helper ({exc})")
        return True, 0, 0, []

    try:
        with open(path, encoding="utf-8") as f:
            source = f.read()
        tree = ast.parse(source, filename=path)
    except (OSError, SyntaxError):
        return True, 0, 0, []

    formulas: list[tuple[str, int, str]] = []  # (file, line, formula)
    helper_calls: list[tuple[str, int, ast.Call]] = []  # (file, line, node)

    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        if not isinstance(node.func, ast.Name):
            continue
        name = node.func.id
        if name not in LATEX_FUNC_NAMES:
            continue

        if name == "precompile_formulas":
            if node.args:
                lst = _safe_ast_eval(node.args[0])
                if isinstance(lst, list):
                    for item in lst:
                        if isinstance(item, str):
                            formulas.append((path, node.lineno, item))
            continue

        if name in ("cases", "matrix", "align_eqns", "integral", "derivative"):
            helper_calls.append((path, node.lineno, node))
            continue

        if name in ("MathTex", "ChineseMathTex", "Tex", "SingleStringMathTex", "math"):
            if node.args:
                val = _safe_ast_eval(node.args[0])
                if isinstance(val, str):
                    formulas.append((path, node.lineno, val))
            continue

    failures: list[tuple[str, int, str, str]] = []
    successes = 0

    # --- direct formulas ---
    if formulas:
        template = lh.tex_template_chinese()
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            results = lh.precompile_formulas(
                [f[2] for f in formulas], tex_template=template, quiet=True
            )
        for (fpath, line, expr), obj in zip(formulas, results, strict=False):
            if getattr(obj, "tex_string", "") == r"\text{[LaTeX error]}":
                failures.append((fpath, line, expr, "LaTeX compilation error (xelatex)"))
            else:
                successes += 1

    # --- helper function calls ---
    for fpath, line, node in helper_calls:
        helper_name = node.func.id  # type: ignore[union-attr]
        try:
            _call_latex_helper(fpath, helper_name, node)
            successes += 1
        except Exception as exc:
            failures.append((fpath, line, f"<{helper_name}()>", str(exc)))

    total = successes + len(failures)
    return (not failures), successes, total, failures


# ------------------------------------------------------------------
# 4. ffmpeg dry-run
# ------------------------------------------------------------------


def _scan_ffmpeg_strings(path: str) -> list[tuple[str, int, str, str]]:
    """Scan a file for ffmpeg filter strings.

    Returns list of (file, line, filter_string, filter_type)
    where filter_type is one of ``vf``, ``af``, ``filter_complex``.
    """
    results: list[tuple[str, int, str, str]] = []
    try:
        with open(path, encoding="utf-8") as f:
            lines = f.readlines()
    except OSError:
        return results

    # Regex for explicit -vf / -af / -filter_complex in the source
    flag_re = re.compile(r'-(vf|af|filter_complex)\s+(["\'])(.+?)\2')
    # Regex for string literals containing filter-like expressions.
    # Avoid matching assertion strings by requiring the literal not sit
    # inside a typical assert/print/log context.
    filter_expr_re = re.compile(
        r'(["\'])((?:[^"\']*?[=&;\[\]])?\s*(?:'
        + "|".join(VIDEO_FILTERS | AUDIO_FILTERS)
        + r')=[^"\']*?)\1'
    )

    for lineno, line in enumerate(lines, start=1):
        # Explicit flags always take precedence.
        flag_matches = list(flag_re.finditer(line))
        for m in flag_matches:
            ftype = m.group(1)
            fstr = m.group(3)
            results.append((path, lineno, fstr, ftype))

        if flag_matches:
            continue

        # Skip lines that look like assertions or print statements for
        # heuristic matching, to avoid validating test substrings.
        if re.search(r"\bassert\b|\bprint\(|\blogger\.|\blogger\b", line):
            continue

        for m in filter_expr_re.finditer(line):
            fstr = m.group(2)
            ftype = _classify_filter_type(fstr)
            results.append((path, lineno, fstr, ftype))

    return results


def _parse_filter_complex_inputs_outputs(fgraph: str) -> tuple[set[str], set[str]]:
    """Parse a filter_complex string and return (input_labels, output_labels)."""
    inputs: set[str] = set()
    outputs: set[str] = set()
    segment_re = re.compile(r"^((?:\[.*?\])+)(.+?)((?:\[.*?\])+)$")
    for segment in fgraph.split(";"):
        segment = segment.strip()
        if not segment:
            continue
        m = segment_re.match(segment)
        if m:
            inputs.update(re.findall(r"\[(.*?)\]", m.group(1)))
            outputs.update(re.findall(r"\[(.*?)\]", m.group(3)))
        else:
            # No explicit output labels – all labels are inputs.
            inputs.update(re.findall(r"\[(.*?)\]", segment))
    return inputs, outputs


def _make_test_video(path: str) -> bool:
    """Create a 1-second test video with both video and audio streams."""
    cmd = [
        "ffmpeg",
        "-hide_banner",
        "-loglevel",
        "error",
        "-y",
        "-f",
        "lavfi",
        "-i",
        FFMPEG_TESTSRC,
        "-f",
        "lavfi",
        "-i",
        FFMPEG_ANULLSRC,
        "-shortest",
        "-pix_fmt",
        "yuv420p",
        path,
    ]
    try:
        subprocess.run(cmd, capture_output=True, check=True, timeout=30)
        return True
    except Exception:
        return False


def _build_ffmpeg_validate_cmd(
    filter_str: str, ftype: str, test_video: str | None
) -> list[str] | None:
    """Build an ffmpeg command that validates *filter_str* for 1 frame."""
    base = ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y"]

    if ftype == "vf":
        return base + [
            "-f",
            "lavfi",
            "-i",
            FFMPEG_TESTSRC,
            "-vf",
            filter_str,
            "-frames:v",
            "1",
            "-f",
            "null",
            "-",
        ]

    if ftype == "af":
        return base + [
            "-f",
            "lavfi",
            "-i",
            FFMPEG_ANULLSRC,
            "-af",
            filter_str,
            "-frames:a",
            "1",
            "-f",
            "null",
            "-",
        ]

    if ftype == "filter_complex":
        inputs, outputs = _parse_filter_complex_inputs_outputs(filter_str)
        cmd = base[:]
        max_idx = -1
        for lbl in inputs:
            m = re.match(r"(\d+):", lbl)
            if m:
                max_idx = max(max_idx, int(m.group(1)))
            else:
                max_idx = max(max_idx, 0)

        if test_video and os.path.exists(test_video):
            for _ in range(max_idx + 1):
                cmd.extend(["-i", test_video])
        else:
            # Fallback: provide interleaved lavfi inputs.
            for _ in range(max_idx + 1):
                cmd.extend(["-f", "lavfi", "-i", FFMPEG_TESTSRC])
                cmd.extend(["-f", "lavfi", "-i", FFMPEG_ANULLSRC])

        cmd.extend(["-filter_complex", filter_str])
        for out in outputs:
            cmd.extend(["-map", f"[{out}]"])
        cmd.extend(["-frames:v", "1", "-f", "null", "-"])
        return cmd

    return None


def check_ffmpeg(path: str) -> tuple[bool, str, list[tuple[str, int, str, str]]]:
    """Validate ffmpeg filter syntax found in *path* and companion scripts.

    Returns (ok, message, failures)
    where failures is a list of (file, line, filter, stderr).
    """
    files = [path]
    companion_dir = os.path.dirname(path)
    files.extend(sorted(glob.glob(os.path.join(companion_dir, "*.py"))))
    files = list(dict.fromkeys(files))
    # Also include .sh companion scripts which often contain ffmpeg commands
    files.extend(sorted(glob.glob(os.path.join(companion_dir, "*.sh"))))
    files = list(dict.fromkeys(files))

    all_filters: list[tuple[str, int, str, str]] = []
    for f in files:
        all_filters.extend(_scan_ffmpeg_strings(f))

    # Detect ffmpeg_builder usage in companion scripts even when no static
    # filter strings are found.
    has_builder = False
    if not all_filters:
        for f in files:
            if f == path:
                continue
            try:
                with open(f, encoding="utf-8") as fh:
                    content = fh.read()
            except OSError:
                continue
            if "ffmpeg_builder" in content or "FFMpeg" in content:
                has_builder = True
        if has_builder:
            return True, "N/A (ffmpeg_builder companion script found, runtime strings)", []
        return True, "N/A (no ffmpeg references)", []

    seen = set()
    failures: list[tuple[str, int, str, str]] = []

    with tempfile.TemporaryDirectory() as tmpdir:
        test_video = os.path.join(tmpdir, "test.mp4")
        has_test_video = _make_test_video(test_video)

        for fpath, line, fstr, ftype in all_filters:
            key = (fstr, ftype)
            if key in seen:
                continue
            seen.add(key)
            cmd = _build_ffmpeg_validate_cmd(fstr, ftype, test_video if has_test_video else None)
            if cmd is None:
                continue
            try:
                result = subprocess.run(
                    cmd,
                    capture_output=True,
                    text=True,
                    timeout=30,
                )
            except subprocess.TimeoutExpired:
                failures.append((fpath, line, fstr, "ffmpeg validation timed out"))
                continue
            except FileNotFoundError:
                failures.append((fpath, line, fstr, "ffmpeg not found"))
                continue
            if result.returncode != 0:
                err = result.stderr.strip() or "unknown ffmpeg error"
                if len(err) > 300:
                    err = err[:300] + " ..."
                failures.append((fpath, line, fstr, err))

    if failures:
        msg = f"{len(seen) - len(failures)}/{len(seen)} filtergraphs OK"
    else:
        msg = f"{len(seen)}/{len(seen)} filtergraphs OK"
    return (not failures), msg, failures


# ------------------------------------------------------------------
# Main
# ------------------------------------------------------------------


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Fast pre-render validation: syntax, imports, LaTeX and ffmpeg filters.",
        epilog="Exit codes: 0=PASS, 1=FAIL, 2=argument or file error.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("scene_file", help="Path to scene source file")
    parser.add_argument(
        "engine",
        nargs="?",
        default=None,
        help="Engine name (default: inferred from scene file extension)",
    )
    args = parser.parse_args()

    scene_file = args.scene_file
    engine = args.engine
    if engine is None:
        if scene_file.endswith(".tsx"):
            engine = "motion_canvas"
        else:
            engine = "manimgl"

    if not os.path.exists(scene_file):
        print(f"FATAL: Scene file not found: {scene_file}", file=sys.stderr)
        return 2

    _ensure_manim_importable()

    overall_pass = True

    # --- Python syntax ---
    syntax_ok, syntax_errors = check_python_syntax(scene_file)
    if syntax_ok:
        print("[dry-run] Python syntax: OK")
    else:
        overall_pass = False
        print("[dry-run] Python syntax: FAIL")
        for err in syntax_errors:
            print(f"[dry-run]   {err}")

    # --- Imports ---
    imports_ok, import_failures = check_imports(scene_file, engine)
    if imports_ok:
        print("[dry-run] Imports: OK")
    else:
        overall_pass = False
        print("[dry-run] Imports: FAIL")
        for fpath, line, mod in import_failures:
            print(f"[dry-run]   unresolved: {mod} at {fpath}:{line}")

    # --- LaTeX ---
    latex_ok, latex_ok_count, latex_total, latex_failures = check_latex(scene_file, engine)
    if latex_total == 0:
        print("[dry-run] LaTeX formulas: N/A (no formulas found)")
    elif latex_ok:
        print(f"[dry-run] LaTeX formulas: {latex_ok_count}/{latex_total} compiled OK")
    else:
        overall_pass = False
        print(f"[dry-run] LaTeX formulas: {latex_ok_count}/{latex_total} compiled OK")
        for fpath, line, expr, err in latex_failures:
            print(f"[dry-run]   FAIL at {fpath}:{line}")
            display = expr if len(expr) < 200 else expr[:200] + " ..."
            print(f"[dry-run]   Formula: {display}")
            print(f"[dry-run]   Error: {err}")

    # --- ffmpeg ---
    ffmpeg_ok, ffmpeg_msg, ffmpeg_failures = check_ffmpeg(scene_file)
    if ffmpeg_msg.startswith("N/A") or ffmpeg_ok:
        print(f"[dry-run] ffmpeg filtergraph: {ffmpeg_msg}")
    else:
        overall_pass = False
        print(f"[dry-run] ffmpeg filtergraph: {ffmpeg_msg}")
        for fpath, line, fstr, err in ffmpeg_failures:
            print(f"[dry-run]   FAIL at {fpath}:{line}")
            display = fstr if len(fstr) < 200 else fstr[:200] + " ..."
            print(f"[dry-run]   Filter: {display}")
            print(f"[dry-run]   Error: {err}")

    # --- Overall ---
    if overall_pass:
        print("[dry-run] Overall: PASS")
        return 0
    else:
        print("[dry-run] Overall: FAIL")
        return 1


if __name__ == "__main__":
    sys.exit(main())
