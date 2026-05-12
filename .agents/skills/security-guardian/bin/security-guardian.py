#!/usr/bin/env python3
"""Security Guardian — filesystem watchdog for MaCode Harness.

Usage:
    security-guardian.py --foreground    # Run in foreground
    security-guardian.py --daemon        # Run as background daemon
    security-guardian.py --scan          # One-shot scan
"""

import argparse
import json
import os
import sys
import time
from datetime import UTC, datetime

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../.."))
AUDIT_LOG = os.path.join(PROJECT_ROOT, ".agent", "security", "audit.log")
SIGNAL_DIR = os.path.join(PROJECT_ROOT, ".agent", "signals")

WATCH_PATHS = [
    os.path.join(PROJECT_ROOT, "scenes"),
    os.path.join(PROJECT_ROOT, "assets"),
]

FORBIDDEN_PATHS = [
    os.path.join(PROJECT_ROOT, "engines"),
    os.path.join(PROJECT_ROOT, "bin"),
    os.path.join(PROJECT_ROOT, "pipeline"),
    os.path.join(PROJECT_ROOT, "tests"),
    os.path.join(PROJECT_ROOT, "docs"),
]

FORBIDDEN_FILES = {
    "project.yaml",
    "requirements.txt",
    "package.json",
    "package-lock.json",
}


def log_event(level: str, message: str, path: str = ""):
    os.makedirs(os.path.dirname(AUDIT_LOG), exist_ok=True)
    entry = {
        "timestamp": datetime.now(UTC).isoformat(),
        "level": level,
        "message": message,
        "path": path,
    }
    with open(AUDIT_LOG, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")

    if level in ("CRITICAL", "ERROR"):
        alert_path = os.path.join(SIGNAL_DIR, "security_alert")
        os.makedirs(os.path.dirname(alert_path), exist_ok=True)
        with open(alert_path, "w", encoding="utf-8") as f:
            f.write(json.dumps(entry, indent=2))
        print(f"[SECURITY_ALERT] {message}: {path}", file=sys.stderr)


def check_event(path: str):
    basename = os.path.basename(path)
    if basename in FORBIDDEN_FILES:
        log_event("CRITICAL", "Forbidden file touched", path)
        return

    for forbidden in FORBIDDEN_PATHS:
        if path.startswith(forbidden):
            log_event("CRITICAL", "Forbidden directory written", path)
            return

    if path.endswith(".glsl"):
        log_event("WARNING", "GLSL file created (should use Effect Registry)", path)


def scan_once():
    """One-shot scan of all watched paths."""
    for watch in WATCH_PATHS:
        if not os.path.isdir(watch):
            continue
        for root, _dirs, files in os.walk(watch):
            for f in files:
                check_event(os.path.join(root, f))


def run_foreground():
    """Simple polling-based watch (no inotify dependency)."""
    print("[guardian] Starting filesystem watch...")
    known = set()

    # Initial scan
    for watch in WATCH_PATHS:
        if os.path.isdir(watch):
            for root, _dirs, files in os.walk(watch):
                for f in files:
                    known.add(os.path.join(root, f))

    try:
        while True:
            time.sleep(2)
            current = set()
            for watch in WATCH_PATHS:
                if os.path.isdir(watch):
                    for root, _dirs, files in os.walk(watch):
                        for f in files:
                            current.add(os.path.join(root, f))

            new_files = current - known
            for f in new_files:
                check_event(f)

            known = current
    except KeyboardInterrupt:
        print("\n[guardian] Stopped.")


def main():
    parser = argparse.ArgumentParser(description="MaCode Security Guardian")
    parser.add_argument("--foreground", action="store_true", help="Run in foreground")
    parser.add_argument("--daemon", action="store_true", help="Run as daemon")
    parser.add_argument("--scan", action="store_true", help="One-shot scan")
    args = parser.parse_args()

    if args.scan:
        scan_once()
        return 0

    if args.daemon:
        pid = os.fork()
        if pid > 0:
            print(f"[guardian] Daemon started (PID {pid})")
            return 0
        os.setsid()
        run_foreground()
        return 0

    run_foreground()
    return 0


if __name__ == "__main__":
    sys.exit(main())
