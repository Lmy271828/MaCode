#!/usr/bin/env python3
"""
bin/state-read.py

读取 OrchestrationState v1.1 state.json，支持字段提取和简单 jq 风格查询。

用法:
    state-read.py <state_dir> [--field FIELD] [--jq EXPR]

示例:
    state-read.py .agent/tmp/01_test
    state-read.py .agent/tmp/01_test --field status
    state-read.py .agent/tmp/01_test --jq .outputs.port
    state-read.py .agent/tmp/01_test --jq .outputs.framesRendered
"""

from __future__ import annotations

import argparse
import json
import os
import sys


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Read OrchestrationState v1.1 state.json",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument("state_dir", help="Directory containing state.json")
    parser.add_argument(
        "--field",
        default="",
        help="Return a single top-level field value (raw string, no quotes)",
    )
    parser.add_argument(
        "--jq",
        default="",
        help="Simple jq-style path (e.g. .outputs.port, .status)",
    )
    return parser.parse_args(argv)


def jq_get(data: dict, expr: str) -> object:
    """Simple jq path resolver: .outputs.port -> data['outputs']['port']."""
    if not expr.startswith("."):
        raise ValueError("jq expression must start with '.'")
    parts = expr[1:].split(".")
    current: object = data
    for part in parts:
        if not part:
            continue
        if isinstance(current, dict) and part in current:
            current = current[part]
        else:
            raise KeyError(f"path '{expr}' not found")
    return current


def print_value(value: object, *, raw: bool = False) -> None:
    """Print a value: JSON for objects, raw string for scalars."""
    if value is None:
        print("")
    elif isinstance(value, (dict, list)):
        print(json.dumps(value))
    elif raw:
        print(value)
    else:
        print(json.dumps(value))


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)

    state_path = os.path.join(args.state_dir, "state.json")
    if not os.path.exists(state_path):
        print(f"state-read: state.json not found in {args.state_dir}", file=sys.stderr)
        return 1

    try:
        with open(state_path) as f:
            data = json.load(f)
    except (json.JSONDecodeError, OSError) as exc:
        print(f"state-read: failed to read {state_path}: {exc}", file=sys.stderr)
        return 1

    try:
        if args.field:
            value = data.get(args.field)
            print_value(value, raw=True)
        elif args.jq:
            value = jq_get(data, args.jq)
            print_value(value, raw=not isinstance(value, (dict, list)))
        else:
            print(json.dumps(data, indent=2))
    except (KeyError, ValueError) as exc:
        print(f"state-read: {exc}", file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
