"""bin/checks/_utils.py
Shared utilities for check scripts.
"""

import ast
import fcntl
import json
import os
import re
import time
from contextlib import contextmanager
from datetime import UTC, datetime


def find_function_blocks(source_path: str):
    """Parse source and return {def_lineno: (start, end, name)}."""
    with open(source_path, encoding='utf-8') as f:
        source = f.read()
    tree = ast.parse(source)
    blocks = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef):
            blocks[node.lineno] = (node.lineno, node.end_lineno, node.name)
    return blocks


def extract_segments_from_source(source_path: str):
    """Extract @segment annotations from scene.py or scene.tsx."""
    SEGMENT_RE = re.compile(r'^\s*(?:#|//)\s*@segment:(\w+)\s*$')
    TIME_RE = re.compile(r'^\s*(?:#|//)\s*@time:([\d.]+)-([\d.]+)s\s*$')
    KEYFRAMES_RE = re.compile(r'^\s*(?:#|//)\s*@keyframes:\[(.*?)\]\s*$')
    DESC_RE = re.compile(r'^\s*(?:#|//)\s*@description:(.*)$')
    CHECKS_RE = re.compile(r'^\s*(?:#|//)\s*@checks:\[(.*?)\]\s*$')

    segments = []
    current = None

    with open(source_path, encoding='utf-8') as f:
        for lineno, line in enumerate(f, 1):
            m = SEGMENT_RE.match(line)
            if m:
                if current:
                    current['line_end'] = lineno - 1
                current = {
                    'id': m.group(1),
                    'file': os.path.basename(source_path),
                    'line_start': lineno,
                }
                segments.append(current)
                continue

            if not current:
                continue

            m = TIME_RE.match(line)
            if m:
                current['time_range'] = [float(m.group(1)), float(m.group(2))]
                continue

            m = KEYFRAMES_RE.match(line)
            if m:
                current['keyframes'] = [
                    float(x.strip()) for x in m.group(1).split(',') if x.strip()
                ]
                continue

            m = DESC_RE.match(line)
            if m:
                current['description'] = m.group(1).strip()
                continue

            m = CHECKS_RE.match(line)
            if m:
                current['checks'] = [
                    x.strip().strip('"\'') for x in m.group(1).split(',') if x.strip()
                ]
                continue

            if line.strip() and not line.strip().startswith('#') and not line.strip().startswith('//'):
                current['line_end'] = lineno - 1
                current = None

    if current and 'line_end' not in current:
        with open(source_path, encoding='utf-8') as f:
            lines = f.readlines()
            current['line_end'] = len(lines)

    return segments


def get_code_block(source_path: str, line_start: int, line_end: int) -> str:
    with open(source_path, encoding='utf-8') as f:
        lines = f.readlines()
    return ''.join(lines[line_start - 1:line_end])


def calc_animation_time(code_block: str) -> float:
    """Accumulate self.wait() and run_time params to get total animation time."""
    total = 0.0
    for m in re.finditer(r'self\.wait\(([^)]+)\)', code_block):
        expr = m.group(1).strip()
        try:
            total += float(ast.literal_eval(expr))
        except Exception:
            pass
    for _ in re.finditer(r'self\.wait\(\s*\)', code_block):
        total += 1.0
    for m in re.finditer(r'run_time\s*=\s*([^,\)\n]+)', code_block):
        expr = m.group(1).strip()
        try:
            total += float(ast.literal_eval(expr))
        except Exception:
            pass
    return total


def calc_animation_time_mc(code_block: str) -> float:
    """Accumulate Motion Canvas yield* durations and waitFor calls."""
    total = 0.0
    # Remove single-line comments to avoid matching yield* in comments
    code_no_comments = re.sub(r'//.*$', '', code_block, flags=re.MULTILINE)
    # yield* something().method(value, duration) — second arg is duration
    # Use [^\n,] to avoid matching across lines
    for m in re.finditer(r'yield\*\s*[^\n,]+\([^\n,]+,\s*([\d.]+)\s*\)', code_no_comments):
        try:
            total += float(m.group(1))
        except Exception:
            pass
    # yield* waitFor(duration)
    for m in re.finditer(r'yield\*\s*waitFor\(\s*([\d.]+)\s*\)', code_no_comments):
        try:
            total += float(m.group(1))
        except Exception:
            pass
    return total


def find_source_file(scene_dir: str) -> str:
    """Find scene source file (.py or .tsx) in scene directory."""
    for ext in ['.py', '.tsx']:
        candidate = os.path.join(scene_dir, f'scene{ext}')
        if os.path.exists(candidate):
            return candidate
    return ''


def count_formulas(code_block: str) -> int:
    return len(re.findall(r'\b(MathTex|Tex|ChineseMathTex)\b', code_block))


def segments_equal(a: dict, b: dict) -> bool:
    keys = ['id', 'time_range', 'keyframes', 'description', 'checks']
    for k in keys:
        if a.get(k) != b.get(k):
            return False
    return True


def get_project_root() -> str:
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def load_manifest(scene_dir: str) -> dict:
    manifest_path = os.path.join(scene_dir, 'manifest.json')
    with open(manifest_path, encoding='utf-8') as f:
        return json.load(f)


# ── File locking utilities ────────────────────────────

@contextmanager
def file_lock(lock_path: str, timeout: float = 10.0):
    """POSIX advisory file lock (flock) with timeout.

    Usage:
        with file_lock('/path/to/lockfile'):
            # critical section
    """
    os.makedirs(os.path.dirname(lock_path) if os.path.dirname(lock_path) else '.', exist_ok=True)
    fd = os.open(lock_path, os.O_RDWR | os.O_CREAT)
    start = time.time()
    while True:
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            break
        except OSError:
            if time.time() - start > timeout:
                os.close(fd)
                raise TimeoutError(f"Could not acquire lock on {lock_path} within {timeout}s") from None
            time.sleep(0.05)
    try:
        yield fd
    finally:
        fcntl.flock(fd, fcntl.LOCK_UN)
        os.close(fd)


def write_json_atomic(path: str, data: dict):
    """Atomically write JSON to path (tmp + replace), optionally inside a lock."""
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
        f.write("\n")
    os.replace(tmp, path)


# ── Scene claim / concurrency utilities ───────────────

CLAIM_TTL_SECONDS = 600  # 10 minutes


def _read_max_concurrent() -> int:
    """Read max_concurrent_scenes from project.yaml."""
    project_yaml = os.path.join(get_project_root(), "project.yaml")
    if not os.path.isfile(project_yaml):
        return 4
    try:
        import yaml
        with open(project_yaml, encoding="utf-8") as f:
            data = yaml.safe_load(f)
        return data.get("agent", {}).get("resource_limits", {}).get("max_concurrent_scenes", 4)
    except Exception:
        return 4


def _count_active_claims() -> int:
    """Count non-stale claim files across all scenes."""
    tmp_dir = os.path.join(".agent", "tmp")
    if not os.path.isdir(tmp_dir):
        return 0
    count = 0
    now = time.time()
    for entry in os.listdir(tmp_dir):
        claim_path = os.path.join(tmp_dir, entry, ".claimed_by")
        if os.path.isfile(claim_path):
            try:
                with open(claim_path, encoding="utf-8") as f:
                    data = json.load(f)
                if now - data.get("claimed_at", 0) < CLAIM_TTL_SECONDS:
                    count += 1
            except (json.JSONDecodeError, OSError):
                pass
    return count


def get_claim_path(scene_name: str) -> str:
    return os.path.join(".agent", "tmp", scene_name, ".claimed_by")


def claim_scene(scene_name: str, agent_id: str, check_global_limit: bool = True) -> dict:
    """Attempt to atomically claim a scene for rendering/checking.

    Returns {'ok': True} if claim succeeded, or {'ok': False, 'owner': ..., 'since': ...}
    if scene is already claimed by another agent.
    """
    claim_path = get_claim_path(scene_name)
    os.makedirs(os.path.dirname(claim_path), exist_ok=True)

    with file_lock(claim_path + ".lock", timeout=5.0):
        # Check existing claim
        if os.path.isfile(claim_path):
            try:
                with open(claim_path, encoding="utf-8") as f:
                    existing = json.load(f)
                claimed_at = existing.get("claimed_at", 0)
                if time.time() - claimed_at < CLAIM_TTL_SECONDS:
                    return {
                        "ok": False,
                        "owner": existing.get("agent_id", "unknown"),
                        "since": claimed_at,
                    }
            except (json.JSONDecodeError, OSError):
                pass  # corrupt claim file, overwrite

        # Global concurrency limit check
        if check_global_limit:
            max_slots = _read_max_concurrent()
            active = _count_active_claims()
            if active >= max_slots:
                return {
                    "ok": False,
                    "reason": "max_concurrent",
                    "max": max_slots,
                    "active": active,
                    "message": f"Global concurrency limit reached ({active}/{max_slots} scenes active)",
                }

        # Write new claim
        claim_data = {
            "agent_id": agent_id,
            "claimed_at": time.time(),
            "iso_time": datetime.now(UTC).isoformat(),
        }
        write_json_atomic(claim_path, claim_data)
        return {"ok": True}


def release_scene_claim(scene_name: str):
    """Release claim on a scene."""
    claim_path = get_claim_path(scene_name)
    if os.path.isfile(claim_path):
        with file_lock(claim_path + ".lock", timeout=5.0):
            try:
                os.remove(claim_path)
            except OSError:
                pass


def is_scene_claimed(scene_name: str) -> dict:
    """Check current claim status of a scene."""
    claim_path = get_claim_path(scene_name)
    if not os.path.isfile(claim_path):
        return {"claimed": False}
    try:
        with open(claim_path, encoding="utf-8") as f:
            data = json.load(f)
        claimed_at = data.get("claimed_at", 0)
        if time.time() - claimed_at > CLAIM_TTL_SECONDS:
            return {"claimed": False, "stale": True}
        return {
            "claimed": True,
            "agent_id": data.get("agent_id"),
            "claimed_at": claimed_at,
        }
    except (json.JSONDecodeError, OSError):
        return {"claimed": False, "corrupt": True}


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
