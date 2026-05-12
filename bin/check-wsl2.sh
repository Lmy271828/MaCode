#!/usr/bin/env bash
set -euo pipefail

# bin/check-wsl2.sh
# Detect WSL2 environment and surface configuration issues.
# Non-WSL systems: silently passes (exit 0).
# WSL2 systems: reports findings with actionable fixes.
#
# Checks:
#   1. Project on native Linux filesystem (not /mnt/c)
#   2. sysctl limits (vm.max_map_count, fs.inotify.max_user_watches)
#   3. /dev/shm size (Chromium / Playwright shared memory)
#   4. WSLg availability (GUI window support for ManimGL preview)
#   5. GPU driver passthrough status
#
# Usage:
#   check-wsl2.sh [--json]

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

JSON_MODE=false
if [[ "${1:-}" == "--json" ]]; then
    JSON_MODE=true
fi

# ── Detect WSL ───────────────────────────────────────────
is_wsl() {
    if [[ -f /proc/sys/fs/binfmt_misc/WSLInterop ]] || \
       grep -qi microsoft /proc/version 2>/dev/null || \
       [[ -n "${WSL_DISTRO_NAME:-}" ]]; then
        return 0
    fi
    return 1
}

if ! is_wsl; then
    if $JSON_MODE; then
        echo '{"is_wsl": false, "issues": []}'
    fi
    exit 0
fi

# ── Gather data ──────────────────────────────────────────
ISSUES=()
FIXES=()

# 1. Filesystem location
if df "$PROJECT_ROOT" 2>/dev/null | grep -qE '^[A-Za-z]:|/mnt/'; then
    ISSUES+=("Project is on a Windows-mounted filesystem (slow 9p/DRVFS). Move to native Linux fs (e.g. ~/MaCode).")
    FIXES+=("mv $PROJECT_ROOT ~/MaCode && cd ~/MaCode")
fi

# 2. sysctl limits
MAX_MAP=$(sysctl -n vm.max_map_count 2>/dev/null || echo "0")
if [[ "$MAX_MAP" -lt 262144 ]]; then
    ISSUES+=("vm.max_map_count=$MAX_MAP (Chromium/Playwright needs >= 262144).")
    FIXES+=("echo 'vm.max_map_count=262144' | sudo tee -a /etc/sysctl.conf && sudo sysctl -p")
fi

INOTIFY_MAX=$(sysctl -n fs.inotify.max_user_watches 2>/dev/null || echo "0")
if [[ "$INOTIFY_MAX" -lt 524288 ]]; then
    ISSUES+=("fs.inotify.max_user_watches=$INOTIFY_MAX (large projects need >= 524288).")
    FIXES+=("echo 'fs.inotify.max_user_watches=524288' | sudo tee -a /etc/sysctl.conf && sudo sysctl -p")
fi

# 3. /dev/shm size
SHM_SIZE_KB=$(df -k /dev/shm 2>/dev/null | awk 'NR==2 {print $2}' || echo "0")
SHM_SIZE_MB=$((SHM_SIZE_KB / 1024))
if [[ "$SHM_SIZE_MB" -lt 1024 ]]; then
    ISSUES+=("/dev/shm is only ${SHM_SIZE_MB}MB (Chromium may OOM; needs >= 1GB).")
    FIXES+=("Add 'wsl2' section to %USERPROFILE%\\.wslconfig with kernelCommandLine='tmpfs.size=2G'")
fi

# 4. WSLg
WSLG_PRESENT=false
if [[ -n "${WAYLAND_DISPLAY:-}" ]] || [[ -d /mnt/wslg ]]; then
    WSLG_PRESENT=true
fi
if [[ "$WSLG_PRESENT" == false ]]; then
    ISSUES+=("WSLg not detected. ManimGL interactive preview requires GUI support.")
    FIXES+=("Update WSL2: 'wsl --update' in Windows PowerShell (Admin).")
fi

# 5. GPU passthrough (cross-check with hardware profile)
if [[ -f "$PROJECT_ROOT/.agent/hardware_profile.json" ]]; then
    GPU_VENDOR=$(python3 -c "import json,sys; d=json.load(open('$PROJECT_ROOT/.agent/hardware_profile.json')); print(d.get('gpu',{}).get('vendor',''))" 2>/dev/null || true)
    BACKEND=$(python3 -c "import json,sys; d=json.load(open('$PROJECT_ROOT/.agent/hardware_profile.json')); print(d.get('recommended_backend',''))" 2>/dev/null || true)
    if [[ "$GPU_VENDOR" == "NVIDIA" && "$BACKEND" == "cpu" ]]; then
        ISSUES+=("NVIDIA GPU detected but backend is CPU (llvmpipe). D3D12 passthrough not active.")
        FIXES+=("Install/update WSL2 NVIDIA driver from https://developer.nvidia.com/cuda/wsl && reboot")
    fi
fi

# ── Output ───────────────────────────────────────────────
if $JSON_MODE; then
    # Build JSON arrays
    issues_json=""
    for i in "${!ISSUES[@]}"; do
        [[ -n "$issues_json" ]] && issues_json="$issues_json,"
        fix="${FIXES[$i]:-}"
        issues_json="$issues_json{\"message\":\"${ISSUES[$i]}\",\"fix\":\"${fix}\"}"
    done
    echo "{\"is_wsl\": true, \"issues\": [$issues_json]}"
else
    echo "=== WSL2 Configuration Check ==="
    if [[ ${#ISSUES[@]} -eq 0 ]]; then
        echo "  ✓ All checks passed"
    else
        for i in "${!ISSUES[@]}"; do
            echo "  ⚠ ${ISSUES[$i]}"
            echo "    Fix: ${FIXES[$i]}"
            echo ""
        done
        echo "WARNING: ${#ISSUES[@]} WSL2 issue(s) found."
        echo "  See: https://learn.microsoft.com/en-us/windows/wsl/wsl-config"
    fi
fi

exit $(( ${#ISSUES[@]} > 0 ? 1 : 0 ))
