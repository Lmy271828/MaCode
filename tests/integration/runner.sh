#!/usr/bin/env bash
# Thin wrapper — delegates to unified test runner.
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
bash "$SCRIPT_DIR/../lib/runner.sh" --suite integration "$@"
