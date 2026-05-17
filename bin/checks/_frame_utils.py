"""bin/checks/_frame_utils.py
Shared frame-processing utilities for check scripts.

NOTE: Layer 2 runtime checks (text overlap via layout snapshots) are handled by
layout_overlap.py. This module retains general-purpose frame/video helpers
for composite timing and frame extraction.
"""

import json
import os
import subprocess

# ── Frame discovery ───────────────────────────────────


def find_frame(scene_tmp_dir: str, frame_num: int):
    """在预渲染帧目录中查找对应帧（1-indexed）。"""
    frames_dir = os.path.join(scene_tmp_dir, "frames")
    candidates = [
        os.path.join(frames_dir, f"frame_{frame_num:04d}.png"),
        os.path.join(frames_dir, f"frame_{frame_num:05d}.png"),
        os.path.join(frames_dir, f"{frame_num:04d}.png"),
        os.path.join(frames_dir, f"{frame_num:05d}.png"),
        os.path.join(frames_dir, f"frame_{frame_num}.png"),
    ]
    for c in candidates:
        if os.path.exists(c):
            return c
    return None


def extract_frame_from_mp4(mp4_path: str, time_sec: float, output_path: str) -> bool:
    cmd = [
        "ffmpeg",
        "-y",
        "-hide_banner",
        "-loglevel",
        "error",
        "-ss",
        str(time_sec),
        "-i",
        mp4_path,
        "-vframes",
        "1",
        "-q:v",
        "2",
        output_path,
    ]
    try:
        subprocess.run(cmd, check=True, capture_output=True)
        return True
    except subprocess.CalledProcessError:
        return False


# ── Composite timing ──────────────────────────────────


def get_composite_offsets(scene_dir: str, segments: list) -> list:
    """计算 composite 每个 segment 在最终视频中的时间偏移（扣除 transition 重叠）。"""
    offsets = []
    cumsum = 0.0
    for seg in segments:
        seg_dir = os.path.join(scene_dir, seg.get("scene_dir", ""))
        seg_manifest = os.path.join(seg_dir, "manifest.json")
        duration = 0.0
        if os.path.isfile(seg_manifest):
            with open(seg_manifest, encoding="utf-8") as f:
                data = json.load(f)
            duration = float(data.get("duration", 0))
        offsets.append(cumsum)
        trans = seg.get("transition", {})
        trans_dur = float(trans.get("duration", 0)) if isinstance(trans, dict) else 0.0
        cumsum += max(0.0, duration - trans_dur)
    return offsets
