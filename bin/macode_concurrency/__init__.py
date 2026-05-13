"""POSIX file locks and atomic JSON helpers (check reports, etc.).

Multi-Agent scene claim was removed per PRD — this module only retains
primitives still needed by ``bin/checks/_utils.write_check_report``.
"""

from __future__ import annotations

import fcntl
import json
import os
import time
from contextlib import contextmanager


@contextmanager
def file_lock(lock_path: str, timeout: float = 10.0):
    """POSIX advisory file lock (flock) with timeout."""
    os.makedirs(os.path.dirname(lock_path) if os.path.dirname(lock_path) else ".", exist_ok=True)
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


def write_json_atomic(path: str, data: dict) -> None:
    """Atomically write JSON to path (tmp + replace)."""
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
        f.write("\n")
    os.replace(tmp, path)
