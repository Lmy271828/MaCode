#!/usr/bin/env bash
set -euo pipefail

# bin/detect-hardware.sh
# Detect hardware capabilities and write .agent/hardware_profile.json.
#
# Usage:
#   detect-hardware.sh

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

PROFILE_DIR="$PROJECT_ROOT/.agent"
PROFILE_FILE="$PROFILE_DIR/hardware_profile.json"

mkdir -p "$PROFILE_DIR"

# ── Defaults ─────────────────────────────────────────────
GPU_PRESENT=false
GPU_VENDOR=""
GPU_MODEL=""
GPU_DRIVER=""

CUDA_AVAILABLE=false
CUDA_VERSION=""

OPENGL_AVAILABLE=false
OPENGL_RENDERER=""
OPENGL_VERSION=""
OPENGL_VERSION_SHORT=""
OPENGL_VENDOR=""
OPENGL_IS_SOFTWARE=false

VULKAN_AVAILABLE=false
VULKAN_INFO=""

EGL_AVAILABLE=false
OSMESA_AVAILABLE=false

D3D12_AVAILABLE=false
D3D12_RENDERER=""

WARNINGS=()
CAPABILITIES=()

# ── GPU Detection ────────────────────────────────────────
if command -v nvidia-smi >/dev/null 2>&1; then
    GPU_PRESENT=true
    GPU_VENDOR="NVIDIA"
    # Prefer structured query-gpu output
    GPU_DRIVER=$(nvidia-smi --query-gpu=driver_version --format=csv,noheader 2>/dev/null | head -n1 | tr -d '[:space:]')
    GPU_MODEL=$(nvidia-smi --query-gpu=name --format=csv,noheader 2>/dev/null | head -n1 | sed 's/^ *//;s/ *$//')

    # Fallback to parsing human-readable output
    if [[ -z "$GPU_DRIVER" || -z "$GPU_MODEL" ]]; then
        NVIDIA_SMI_OUTPUT=$(nvidia-smi 2>/dev/null || true)
        if [[ -n "$NVIDIA_SMI_OUTPUT" ]]; then
            if [[ -z "$GPU_DRIVER" ]]; then
                GPU_DRIVER=$(echo "$NVIDIA_SMI_OUTPUT" | grep -E "Driver Version:\s+[0-9]" | head -n1 | grep -oE "Driver Version:\s+[0-9.]+" | awk '{print $3}')
            fi
            if [[ -z "$GPU_MODEL" ]]; then
                GPU_MODEL=$(echo "$NVIDIA_SMI_OUTPUT" | grep -E "^\|\s+[0-9]+\s+NVIDIA" | sed 's/.*NVIDIA/NVIDIA/' | awk '{$1=""; print $0}' | sed 's/^ *//;s/ *$//')
            fi
        fi
    fi
elif command -v lspci >/dev/null 2>&1; then
    VGA_INFO=$(lspci | grep -i vga || true)
    AMDGPU_INFO=$(lspci | grep -i amdgpu || true)
    if [[ -n "$VGA_INFO" ]]; then
        GPU_PRESENT=true
        if echo "$VGA_INFO" | grep -iq nvidia; then
            GPU_VENDOR="NVIDIA"
        elif echo "$VGA_INFO" | grep -iq amd; then
            GPU_VENDOR="AMD"
        elif echo "$VGA_INFO" | grep -iq intel; then
            GPU_VENDOR="Intel"
        else
            GPU_VENDOR="Unknown"
        fi
        GPU_MODEL=$(echo "$VGA_INFO" | head -n1 | cut -d':' -f3 | sed 's/^ *//;s/ *$//')
    elif [[ -n "$AMDGPU_INFO" ]]; then
        GPU_PRESENT=true
        GPU_VENDOR="AMD"
        GPU_MODEL=$(echo "$AMDGPU_INFO" | head -n1 | cut -d':' -f3 | sed 's/^ *//;s/ *$//')
    fi
fi

# ── CUDA Detection ───────────────────────────────────────
if command -v nvidia-smi >/dev/null 2>&1; then
    CUDA_VERSION=$(nvidia-smi 2>/dev/null | grep "CUDA Version:" | sed 's/.*CUDA Version://' | awk '{print $1}')
fi
if [[ -z "$CUDA_VERSION" ]] && command -v nvcc >/dev/null 2>&1; then
    CUDA_VERSION=$(nvcc --version 2>/dev/null | grep "release" | sed 's/.*release //' | awk '{print $1}' | tr -d ',')
fi
if [[ -n "$CUDA_VERSION" ]]; then
    CUDA_AVAILABLE=true
    CAPABILITIES+=("cuda_${CUDA_VERSION%%.*}")
fi

# ── OpenGL Detection ─────────────────────────────────────
# Primary: glxinfo (most reliable)
if command -v glxinfo >/dev/null 2>&1; then
    OPENGL_AVAILABLE=true
    GLX_B=$(glxinfo -B 2>/dev/null || true)
    if [[ -n "$GLX_B" ]]; then
        OPENGL_RENDERER=$(echo "$GLX_B" | grep -i "OpenGL renderer string:" | sed 's/.*OpenGL renderer string: *//i')
        OPENGL_VERSION=$(echo "$GLX_B" | grep -i "OpenGL version string:" | sed 's/.*OpenGL version string: *//i')
        OPENGL_VENDOR=$(echo "$GLX_B" | grep -i "OpenGL vendor string:" | sed 's/.*OpenGL vendor string: *//i')
    fi
fi

# Fallback: Python + pyglet (when glxinfo not installed but OpenGL context creatable)
# Try .venv-manimgl first (has pyglet), then system python3
PYTHON_FALLBACK=""
if [[ -x "$PROJECT_ROOT/.venv-manimgl/bin/python" ]]; then
    PYTHON_FALLBACK="$PROJECT_ROOT/.venv-manimgl/bin/python"
elif command -v python3 >/dev/null 2>&1; then
    PYTHON_FALLBACK="python3"
fi

if [[ "$OPENGL_AVAILABLE" != "true" && -n "$PYTHON_FALLBACK" ]]; then
    PYGL=$($PYTHON_FALLBACK -c "
import sys
try:
    from pyglet.gl import gl_info
    ver = gl_info.get_version()
    ver_str = '.'.join(map(str, ver)) if isinstance(ver, tuple) else str(ver)
    print('RENDERER|' + str(gl_info.get_renderer()))
    print('VERSION|' + ver_str)
    print('VENDOR|' + str(gl_info.get_vendor()))
except Exception as e:
    print('ERROR|' + str(e), file=sys.stderr)
    sys.exit(1)
" 2>/dev/null)
    if [[ $? -eq 0 && -n "$PYGL" && -z "$(echo "$PYGL" | grep '^ERROR|')" ]]; then
        OPENGL_AVAILABLE=true
        OPENGL_RENDERER=$(echo "$PYGL" | grep '^RENDERER|' | cut -d'|' -f2)
        OPENGL_VERSION=$(echo "$PYGL" | grep '^VERSION|' | cut -d'|' -f2)
        OPENGL_VENDOR=$(echo "$PYGL" | grep '^VENDOR|' | cut -d'|' -f2)
    fi
fi

# Process OpenGL info if available
if [[ "$OPENGL_AVAILABLE" == "true" && -n "$OPENGL_VERSION" ]]; then
    # Extract major.minor version
    OPENGL_VERSION_SHORT=$(echo "$OPENGL_VERSION" | grep -oE '[0-9]+\.[0-9]+' | head -n1)

    # Detect software renderer
    if echo "$OPENGL_RENDERER" | grep -iq "llvmpipe"; then
        OPENGL_IS_SOFTWARE=true
        WARNINGS+=("GPU detected but OpenGL uses software renderer (llvmpipe). WSL2 GPU passthrough may need configuration.")
    elif echo "$OPENGL_RENDERER" | grep -iq "software"; then
        OPENGL_IS_SOFTWARE=true
        WARNINGS+=("OpenGL uses software renderer.")
    else
        OPENGL_IS_SOFTWARE=false
    fi

    if [[ -n "$OPENGL_VERSION_SHORT" ]]; then
        CAPABILITIES+=("opengl_${OPENGL_VERSION_SHORT//./}")
    fi
fi

# ── D3D12 Detection (WSL2 GPU passthrough via Mesa) ──────
if [[ "$OPENGL_IS_SOFTWARE" == true || -z "$OPENGL_RENDERER" ]]; then
    if [[ -f "/usr/lib/x86_64-linux-gnu/dri/d3d12_dri.so" ]]; then
        # Try to probe D3D12 backend via pyglet
        D3D12_PYGL=""
        if [[ -n "$PYTHON_FALLBACK" ]]; then
            D3D12_PYGL=$(GALLIUM_DRIVER=d3d12 MESA_D3D12_DEFAULT_ADAPTER_NAME=NVIDIA \
                "$PYTHON_FALLBACK" -c "
import sys
try:
    from pyglet.gl import gl_info
    renderer = str(gl_info.get_renderer())
    ver = gl_info.get_version()
    ver_str = '.'.join(map(str, ver)) if isinstance(ver, tuple) else str(ver)
    print('RENDERER|' + renderer)
    print('VERSION|' + ver_str)
    print('VENDOR|' + str(gl_info.get_vendor()))
except Exception as e:
    print('ERROR|' + str(e), file=sys.stderr)
    sys.exit(1)
" 2>/dev/null)
        fi
        if echo "$D3D12_PYGL" | grep -q "^RENDERER|D3D12"; then
            D3D12_AVAILABLE=true
            D3D12_RENDERER=$(echo "$D3D12_PYGL" | grep "^RENDERER|" | cut -d'|' -f2)
            D3D12_VERSION=$(echo "$D3D12_PYGL" | grep "^VERSION|" | cut -d'|' -f2)
            D3D12_VENDOR=$(echo "$D3D12_PYGL" | grep "^VENDOR|" | cut -d'|' -f2)
            # Override OpenGL info with D3D12 values
            OPENGL_RENDERER="$D3D12_RENDERER"
            OPENGL_VERSION="$D3D12_VERSION"
            OPENGL_VERSION_SHORT=$(echo "$D3D12_VERSION" | grep -oE '[0-9]+\.[0-9]+' | head -n1)
            OPENGL_VENDOR="$D3D12_VENDOR"
            OPENGL_IS_SOFTWARE=false
            WARNINGS+=("OpenGL upgraded from llvmpipe to D3D12 GPU passthrough (WSL2).")
            if [[ -n "$OPENGL_VERSION_SHORT" ]]; then
                # Replace old opengl capability with new version
                CAPABILITIES=($(printf '%s\n' "${CAPABILITIES[@]}" | grep -v '^opengl_' || true))
                CAPABILITIES+=("opengl_${OPENGL_VERSION_SHORT//./}")
            fi
        fi
    fi
fi

# ── Vulkan Detection ─────────────────────────────────────
if command -v vulkaninfo >/dev/null 2>&1; then
    VULKAN_SUMMARY=$(vulkaninfo --summary 2>/dev/null || true)
    if [[ -n "$VULKAN_SUMMARY" ]]; then
        VULKAN_AVAILABLE=true
    fi
fi

# ── EGL / OSMesa Detection ───────────────────────────────
if command -v eglinfo >/dev/null 2>&1; then
    EGL_AVAILABLE=true
fi
if command -v pkg-config >/dev/null 2>&1 && pkg-config osmesa --exists 2>/dev/null; then
    OSMESA_AVAILABLE=true
fi

# ── Backend Selection ────────────────────────────────────
if [[ "$OPENGL_AVAILABLE" == true ]]; then
    if [[ "$OPENGL_IS_SOFTWARE" == false ]]; then
        if [[ "$D3D12_AVAILABLE" == true ]]; then
            RECOMMENDED_BACKEND="d3d12"
        else
            RECOMMENDED_BACKEND="gpu"
        fi
    else
        RECOMMENDED_BACKEND="cpu"
    fi
else
    RECOMMENDED_BACKEND="headless"
fi

# ── Build JSON ───────────────────────────────────────────
# Build arrays for capabilities and warnings
CAPABILITIES_JSON=""
for cap in "${CAPABILITIES[@]}"; do
    if [[ -n "$CAPABILITIES_JSON" ]]; then
        CAPABILITIES_JSON="$CAPABILITIES_JSON, "
    fi
    CAPABILITIES_JSON="$CAPABILITIES_JSON\"$cap\""
done

WARNINGS_JSON=""
for w in "${WARNINGS[@]}"; do
    if [[ -n "$WARNINGS_JSON" ]]; then
        WARNINGS_JSON="$WARNINGS_JSON, "
    fi
    WARNINGS_JSON="$WARNINGS_JSON\"$w\""
done

cat > "$PROFILE_FILE" <<EOF
{
  "gpu": {
    "present": ${GPU_PRESENT},
    "vendor": $(if [[ -n "$GPU_VENDOR" ]]; then echo "\"$GPU_VENDOR\""; else echo "null"; fi),
    "model": $(if [[ -n "$GPU_MODEL" ]]; then echo "\"$GPU_MODEL\""; else echo "null"; fi),
    "driver_version": $(if [[ -n "$GPU_DRIVER" ]]; then echo "\"$GPU_DRIVER\""; else echo "null"; fi)
  },
  "cuda": {
    "available": ${CUDA_AVAILABLE},
    "version": $(if [[ -n "$CUDA_VERSION" ]]; then echo "\"$CUDA_VERSION\""; else echo "null"; fi)
  },
  "opengl": {
    "available": ${OPENGL_AVAILABLE},
    "renderer": $(if [[ -n "$OPENGL_RENDERER" ]]; then echo "\"$OPENGL_RENDERER\""; else echo "null"; fi),
    "version": $(if [[ -n "$OPENGL_VERSION_SHORT" ]]; then echo "\"$OPENGL_VERSION_SHORT\""; else echo "null"; fi),
    "vendor": $(if [[ -n "$OPENGL_VENDOR" ]]; then echo "\"$OPENGL_VENDOR\""; else echo "null"; fi),
    "is_software": ${OPENGL_IS_SOFTWARE}
  },
  "vulkan": {
    "available": ${VULKAN_AVAILABLE}
  },
  "egl": {
    "available": ${EGL_AVAILABLE}
  },
  "osmesa": {
    "available": ${OSMESA_AVAILABLE}
  },
  "d3d12": {
    "available": ${D3D12_AVAILABLE},
    "renderer": $(if [[ -n "$D3D12_RENDERER" ]]; then echo "\"$D3D12_RENDERER\""; else echo "null"; fi)
  },
  "recommended_backend": "${RECOMMENDED_BACKEND}",
  "capabilities": [${CAPABILITIES_JSON}],
  "warnings": [${WARNINGS_JSON}]
}
EOF

echo "[detect-hardware] Profile written to: $PROFILE_FILE"
echo "[detect-hardware] Backend: ${RECOMMENDED_BACKEND}"
