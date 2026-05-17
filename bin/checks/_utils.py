"""bin/checks/_utils.py
Shared utilities for check scripts.
"""

import ast
import json
import os
import re
import sys

_BIN = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _BIN not in sys.path:
    sys.path.insert(0, _BIN)

from macode_concurrency import file_lock, write_json_atomic  # noqa: E402


def find_function_blocks(source_path: str):
    """Parse source and return {def_lineno: (start, end, name)}."""
    with open(source_path, encoding="utf-8") as f:
        source = f.read()
    tree = ast.parse(source)
    blocks = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef):
            blocks[node.lineno] = (node.lineno, node.end_lineno, node.name)
    return blocks


def extract_segments_from_source(source_path: str):
    """Extract @segment annotations from scene.py or scene.tsx."""
    SEGMENT_RE = re.compile(r"^\s*(?:#|//)\s*@segment:(\w+)\s*$")
    TIME_RE = re.compile(r"^\s*(?:#|//)\s*@time:([\d.]+)-([\d.]+)s\s*$")
    KEYFRAMES_RE = re.compile(r"^\s*(?:#|//)\s*@keyframes:\[(.*?)\]\s*$")
    DESC_RE = re.compile(r"^\s*(?:#|//)\s*@description:(.*)$")
    CHECKS_RE = re.compile(r"^\s*(?:#|//)\s*@checks:\[(.*?)\]\s*$")

    segments = []
    current = None

    with open(source_path, encoding="utf-8") as f:
        for lineno, line in enumerate(f, 1):
            m = SEGMENT_RE.match(line)
            if m:
                if current:
                    current["line_end"] = lineno - 1
                current = {
                    "id": m.group(1),
                    "file": os.path.basename(source_path),
                    "line_start": lineno,
                }
                segments.append(current)
                continue

            if not current:
                continue

            m = TIME_RE.match(line)
            if m:
                current["time_range"] = [float(m.group(1)), float(m.group(2))]
                continue

            m = KEYFRAMES_RE.match(line)
            if m:
                current["keyframes"] = [
                    float(x.strip()) for x in m.group(1).split(",") if x.strip()
                ]
                continue

            m = DESC_RE.match(line)
            if m:
                desc = m.group(1).strip()
                existing = current.get("description", "")
                if existing:
                    current["description"] = existing + "\n" + desc
                else:
                    current["description"] = desc
                continue

            m = CHECKS_RE.match(line)
            if m:
                current["checks"] = [
                    x.strip().strip("\"'") for x in m.group(1).split(",") if x.strip()
                ]
                continue

            if (
                line.strip()
                and not line.strip().startswith("#")
                and not line.strip().startswith("//")
            ):
                current["line_end"] = lineno - 1
                current = None

    if current and "line_end" not in current:
        with open(source_path, encoding="utf-8") as f:
            lines = f.readlines()
            current["line_end"] = len(lines)

    return segments


def get_code_block(source_path: str, line_start: int, line_end: int) -> str:
    with open(source_path, encoding="utf-8") as f:
        lines = f.readlines()
    return "".join(lines[line_start - 1 : line_end])


def calc_animation_time(code_block: str) -> float:
    """Accumulate self.wait() and run_time params to get total animation time."""
    total = 0.0
    for m in re.finditer(r"self\.wait\(([^)]+)\)", code_block):
        expr = m.group(1).strip()
        try:
            total += float(ast.literal_eval(expr))
        except Exception:
            pass
    for _ in re.finditer(r"self\.wait\(\s*\)", code_block):
        total += 1.0
    for m in re.finditer(r"run_time\s*=\s*([^,\)\n]+)", code_block):
        expr = m.group(1).strip()
        try:
            total += float(ast.literal_eval(expr))
        except Exception:
            pass
    return total


def _strip_js_comments(code: str) -> str:
    """Remove both // and /* */ style comments from JS/TS code."""
    code = re.sub(r"//.*$", "", code, flags=re.MULTILINE)
    code = re.sub(r"/\*.*?\*/", "", code, flags=re.DOTALL)
    return code


def _extract_yield_exprs(code: str) -> list[str]:
    """Extract full yield* expression strings (best-effort, newline-tolerant)."""
    # Collapse yield* statements that may span multiple lines
    exprs = []
    # Match yield* followed by balanced parentheses content
    for m in re.finditer(r"yield\*\s*(.+?)(?:;|$)", code, re.DOTALL):
        expr = m.group(1).strip().replace("\n", " ")
        exprs.append(expr)
    return exprs


def _parse_mc_expr_duration(expr: str) -> float | None:
    """Parse duration from a single MC yield* expression."""
    expr = expr.strip()
    # waitFor(duration)
    m = re.match(r"waitFor\s*\(\s*([\d.]+)\s*\)", expr)
    if m:
        return float(m.group(1))
    # delay(duration, callback?) — first arg is duration
    m = re.match(r"delay\s*\(\s*([\d.]+)", expr)
    if m:
        return float(m.group(1))
    # all(...) or sequence(...) — container; we can't know exact duration
    # without evaluating children, so we return 0 and let caller decide
    if re.match(r"(?:all|sequence)\s*\(", expr):
        return None  # container: handled separately
    # Generic: someNode().method(..., duration) or method(duration)
    # Last numeric argument is likely duration in MC
    numbers = re.findall(r"([\d.]+)", expr)
    if numbers:
        return float(numbers[-1])
    return 0.0


def calc_animation_time_mc(code_block: str) -> float:
    """Accumulate Motion Canvas yield* durations (best-effort)."""
    total = 0.0
    code = _strip_js_comments(code_block)
    exprs = _extract_yield_exprs(code)
    for expr in exprs:
        dur = _parse_mc_expr_duration(expr)
        if dur is None:
            # Container (all/sequence) — heuristic: count child animations
            # Extract top-level comma-separated arguments
            inner = re.search(r"\((.*)\)", expr)
            if inner:
                children = inner.group(1).split(",")
                child_durs = []
                for child in children:
                    child = child.strip()
                    if not child:
                        continue
                    cd = _parse_mc_expr_duration(child)
                    if cd is not None:
                        child_durs.append(cd)
                if "sequence" in expr:
                    total += sum(child_durs)
                else:
                    # all() takes max
                    total += max(child_durs) if child_durs else 0.0
        else:
            total += dur
    return total


def extract_animation_calls(code_block: str, is_mc: bool = False) -> list[dict]:
    """Extract individual animation calls with line offsets and durations.

    Returns list of dicts:
        {
            'line': int,       # 1-based, relative to code_block start
            'expr': str,       # matched expression text
            'duration': float,
        }
    """
    calls = []
    lines = code_block.splitlines()
    for i, raw_line in enumerate(lines, start=1):
        line = raw_line.strip()
        if not line or line.startswith("#") or line.startswith("//"):
            continue
        if is_mc:
            # yield* waitFor(duration)
            m = re.search(r"yield\*\s*waitFor\(\s*([\d.]+)\s*\)", line)
            if m:
                calls.append({"line": i, "expr": m.group(0), "duration": float(m.group(1))})
                continue
            # yield* delay(duration, ...)
            m = re.search(r"yield\*\s*delay\(\s*([\d.]+)", line)
            if m:
                calls.append({"line": i, "expr": m.group(0), "duration": float(m.group(1))})
                continue
            # yield* all(...) or sequence(...) — skip containers, handled by total calc
            if re.search(r"yield\*\s*(?:all|sequence)\s*\(", line):
                continue
            # Generic yield* something(..., duration) — last number is duration
            m = re.search(r"yield\*\s+(.+?\(\s*[^)]*?([\d.]+)\s*\))", line)
            if m:
                calls.append({"line": i, "expr": m.group(0), "duration": float(m.group(2))})
        else:
            # self.wait(N)
            m = re.search(r"self\.wait\(\s*([\d.]+)\s*\)", line)
            if m:
                calls.append({"line": i, "expr": m.group(0), "duration": float(m.group(1))})
                continue
            # self.wait() → default 1.0s
            if re.search(r"self\.wait\(\s*\)", line):
                calls.append({"line": i, "expr": "self.wait()", "duration": 1.0})
                continue
            # run_time=N
            m = re.search(r"run_time\s*=\s*([\d.]+)", line)
            if m:
                calls.append({"line": i, "expr": m.group(0), "duration": float(m.group(1))})
    return calls


def find_source_file(scene_dir: str) -> str:
    """Find scene source file (.py or .tsx) in scene directory."""
    for ext in [".py", ".tsx"]:
        candidate = os.path.join(scene_dir, f"scene{ext}")
        if os.path.exists(candidate):
            return candidate
    return ""


def count_formulas(code_block: str, is_mc: bool = False) -> int:
    if is_mc:
        # Motion Canvas uses <Latex> JSX component or MathJax via custom nodes
        return len(re.findall(r"<(Latex|MathJax|Tex)\b", code_block))
    return len(re.findall(r"\b(MathTex|Tex|ChineseMathTex)\b", code_block))


def segments_equal(a: dict, b: dict) -> bool:
    # Structural fields must match exactly
    for k in ("id", "time_range", "keyframes", "checks"):
        if a.get(k) != b.get(k):
            return False
    # Description is human-readable; only flag mismatch if one side is empty
    # and the other isn't, or if they share zero words (completely unrelated).
    a_desc = " ".join(str(a.get("description", "")).split())
    b_desc = " ".join(str(b.get("description", "")).split())
    if not a_desc and not b_desc:
        return True
    if not a_desc or not b_desc:
        return False
    # Check for word overlap — if at least one word matches, consider them related
    a_words = set(a_desc.lower().split())
    b_words = set(b_desc.lower().split())
    return bool(a_words & b_words)


def get_project_root() -> str:
    # _utils.py lives at bin/checks/_utils.py → project root is two levels up
    return os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def load_manifest(scene_dir: str) -> dict:
    manifest_path = os.path.join(scene_dir, "manifest.json")
    with open(manifest_path, encoding="utf-8") as f:
        return json.load(f)


# ── Check report locking ──────────────────────────────


def write_check_report(report_path: str, data: dict, timeout: float = 10.0):
    """Write a check report with advisory file locking to prevent clobbering."""
    lock_path = report_path + ".lock"
    with file_lock(lock_path, timeout=timeout):
        write_json_atomic(report_path, data)


def read_check_report(report_path: str) -> dict:
    """Read a check report (no locking needed for reads)."""
    if not os.path.isfile(report_path):
        return {}
    with open(report_path, encoding="utf-8") as f:
        return json.load(f)
