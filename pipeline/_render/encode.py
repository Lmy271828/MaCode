"""Encode stage: layer2 runtime checks, resource fuses, concat, cache, deliver."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from dataclasses import dataclass

from ._paths import PROJECT_ROOT, get_python
from .validate import RenderContext

FUSE_MAX_FRAMES = 10000
FUSE_MAX_DISK_BYTES = 50 * 1024 * 1024 * 1024  # 50 GB


@dataclass
class EncodeResult:
    final_mp4: str
    frame_count: int


def _layer2_check(ctx: RenderContext) -> None:
    snapshot_path = os.path.join(ctx.output_dir, "layout_snapshots.jsonl")
    if not os.path.isfile(snapshot_path):
        return
    print("[layer2] Running runtime layout checks...")
    check_reports_dir = os.path.join(".agent", "check_reports")
    os.makedirs(check_reports_dir, exist_ok=True)
    report_path = os.path.join(check_reports_dir, f"{ctx.scene_name}_layer2.json")
    result = subprocess.run(
        [
            get_python(),
            os.path.join(PROJECT_ROOT, "bin", "check-runner.py"),
            ctx.scene_dir,
            "--layer",
            "layer2",
            "--format",
            "raw",
        ],
        capture_output=True,
        text=True,
    )
    try:
        layer2_data = json.loads(result.stdout)
    except json.JSONDecodeError:
        print(f"[layer2] Failed to parse output: {result.stderr}", file=sys.stderr)
        return
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(layer2_data, f, indent=2, ensure_ascii=False)
        f.write("\n")
    severity = layer2_data.get("severity_summary", {})
    if severity.get("error"):
        print("[layer2] ERROR: Blocking issues found. See report.")
        sys.exit(1)
    if severity.get("warning"):
        print("[layer2] WARNING: Layout issues found. See report.")
    else:
        print("[layer2] OK")


def _check_fuses(ctx: RenderContext) -> int:
    """Frame count fuse + disk usage fuse. Returns frame_count for downstream use."""
    if ctx.engine_mode == "interactive":
        return 0
    frame_count = len([f for f in os.listdir(ctx.frames_dir) if f.endswith(".png")])
    if frame_count > FUSE_MAX_FRAMES:
        print(
            f"FUSE: frame count {frame_count} exceeds limit {FUSE_MAX_FRAMES}",
            file=sys.stderr,
        )
        sys.exit(1)

    disk_bytes = 0
    tmp_dir = os.path.join(".agent", "tmp")
    if os.path.isdir(tmp_dir):
        result = subprocess.run(
            ["du", "-sb", tmp_dir], capture_output=True, text=True, check=False
        )
        if result.returncode == 0:
            disk_bytes = int(result.stdout.strip().split()[0])
    if disk_bytes > FUSE_MAX_DISK_BYTES:
        disk_gb = disk_bytes // 1024 // 1024 // 1024
        print(f"FUSE: disk usage {disk_gb}GB exceeds limit 50GB", file=sys.stderr)
        sys.exit(1)

    return frame_count


def _encode_mp4(ctx: RenderContext) -> str:
    raw_mp4 = os.path.join(ctx.output_dir, "raw.mp4")
    final_mp4 = os.path.join(ctx.output_dir, "final.mp4")

    if ctx.engine_mode == "interactive":
        print(f"[{ctx.engine}] Interactive engine — skipping frame encoding.")
        print(
            f"[{ctx.engine}] Preview complete. "
            "Use 'macode migrate' to export to batch engine for final render."
        )
        if os.path.isfile(raw_mp4):
            subprocess.run(["cp", raw_mp4, final_mp4], check=False)
        else:
            open(final_mp4, "a").close()
        return final_mp4

    with open(ctx.log_file, "a", encoding="utf-8") as logf:
        result = subprocess.run(
            [
                "bash",
                os.path.join(PROJECT_ROOT, "pipeline", "concat.sh"),
                ctx.frames_dir,
                raw_mp4,
                str(ctx.fps),
            ],
            stdout=logf,
            stderr=subprocess.STDOUT,
        )
    if result.returncode != 0:
        print("[concat] Frame encoding failed", file=sys.stderr)
        sys.exit(1)
    subprocess.run(["cp", raw_mp4, final_mp4], check=False)
    return final_mp4


def _populate_cache(ctx: RenderContext) -> None:
    cache_script = os.path.join(PROJECT_ROOT, "pipeline", "cache.sh")
    if not (os.path.isfile(cache_script) and os.access(cache_script, os.X_OK)):
        return
    with open(ctx.log_file, "a", encoding="utf-8") as logf:
        subprocess.run(
            ["bash", cache_script, ctx.scene_dir, "populate", ctx.output_dir],
            stdout=logf,
            stderr=subprocess.STDOUT,
            check=False,
        )


def _deliver(ctx: RenderContext) -> None:
    subprocess.run(
        [
            get_python(),
            os.path.join(PROJECT_ROOT, "pipeline", "deliver.py"),
            ctx.scene_name,
            ctx.output_dir,
            os.path.join(PROJECT_ROOT, "output"),
        ],
        check=False,
    )


def run(ctx: RenderContext, *, cache_hit: bool) -> EncodeResult:
    _layer2_check(ctx)
    frame_count = _check_fuses(ctx)
    final_mp4 = _encode_mp4(ctx)
    if not cache_hit and ctx.engine_mode != "interactive":
        _populate_cache(ctx)
    _deliver(ctx)

    # Recount after encode (for accurate JSON output)
    if os.path.isdir(ctx.frames_dir):
        frame_count = len([f for f in os.listdir(ctx.frames_dir) if f.endswith(".png")])
    return EncodeResult(final_mp4=final_mp4, frame_count=frame_count)
