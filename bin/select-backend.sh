#!/usr/bin/env bash
set -euo pipefail

# bin/select-backend.sh
# Read hardware profile and output the recommended render backend.

if [[ "${1:-}" == "--help" || "${1:-}" == "-h" ]]; then
    cat <<'EOF'
Usage: select-backend.sh [--print]

Read hardware profile and output the recommended render backend.

Options:
  --print    Output human-readable message instead of raw backend name

Outputs:
  gpu | cpu | headless
EOF
    exit 0
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
PROFILE_FILE="$PROJECT_ROOT/.agent/hardware_profile.json"

if [[ ! -f "$PROFILE_FILE" ]]; then
    BACKEND="cpu"
else
    BACKEND=$(python3 -c "
import json, sys
try:
    with open('$PROFILE_FILE') as f:
        data = json.load(f)
    print(data.get('recommended_backend', 'cpu'))
except Exception:
    print('cpu')
" 2>/dev/null || echo "cpu")
fi

if [[ "${1:-}" == "--print" ]]; then
    echo "        Selected backend: $BACKEND"
else
    echo "$BACKEND"
fi
