"""Shader backend adaptation for MaCode.

Provides a ``Backend`` enum that maps the current hardware / driver
capabilities to the correct GLSL dialect and algorithm choices.
"""

import json
import os
from enum import Enum, auto


class Backend(Enum):
    """Target rendering backend.

    Members:
        GPU       -- Dedicated / integrated GPU (NVIDIA, AMD, Intel)
        CPU       -- Software rasteriser (Mesa llvmpipe, softpipe, …)
        HEADLESS  -- No display / no GPU available
    """

    GPU = auto()
    D3D12 = auto()
    CPU = auto()
    HEADLESS = auto()

    @classmethod
    def from_hardware_profile(cls, profile_path: str = ".agent/hardware_profile.json") -> "Backend":
        """Read hardware profile and return the most appropriate ``Backend``.

        Falls back to ``CPU`` when the profile is missing, unreadable, or
        indicates a software renderer.
        """
        if not os.path.exists(profile_path):
            return cls.CPU

        try:
            with open(profile_path, encoding="utf-8") as f:
                profile = json.load(f)
        except (json.JSONDecodeError, OSError):
            return cls.CPU

        # Support both flat and nested profile formats
        opengl = profile.get("opengl", {})
        gpu_raw = profile.get("gpu", {})
        if isinstance(gpu_raw, dict):
            gpu_info = gpu_raw
            gpu_vendor = str(gpu_info.get("vendor") or gpu_info.get("model") or "").lower()
            gpu_present = gpu_info.get("present", bool(gpu_vendor))
        else:
            gpu_info = {}
            gpu_vendor = str(gpu_raw).lower()
            gpu_present = bool(gpu_vendor)

        renderer = str(opengl.get("renderer") or profile.get("renderer", "")).lower()
        is_software = opengl.get("is_software", False)
        recommended = str(profile.get("recommended_backend", "")).lower()

        if recommended == "d3d12":
            return cls.D3D12

        if recommended == "headless":
            return cls.HEADLESS

        # Detect known CPU/software renderers
        if is_software or any(r in renderer for r in ("llvmpipe", "softpipe", "swrast", "virgl")):
            return cls.CPU

        if not gpu_present or gpu_vendor in ("none", "unknown", ""):
            return cls.HEADLESS

        if any(v in gpu_vendor for v in ("nvidia", "amd", "intel", "radeon")):
            return cls.GPU

        # Default conservative fallback
        return cls.CPU

    @property
    def glsl_version(self) -> str:
        """GLSL ``#version`` directive for this backend."""
        if self in (Backend.GPU, Backend.D3D12):
            return "#version 430"
        return "#version 330"

    @property
    def noise_impl(self) -> str:
        """Noise algorithm name suitable for this backend.

        * ``simplex`` – higher quality, better on GPU.
        * ``hash``    – cheaper, friendlier to CPU software rasterisers.
        """
        if self in (Backend.GPU, Backend.D3D12):
            return "simplex"
        return "hash"
