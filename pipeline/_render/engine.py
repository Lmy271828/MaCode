"""Engine stage: cache check, pre-render, optional service, engine invocation.

Top-level: ``run(ctx)`` returns ``EngineResult``. Cache hits skip the engine.
Background dev servers (legacy MC path) are started under ``macode-run`` so
lifecycle/log capture stays unified.
"""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import time
from dataclasses import dataclass

from ._paths import PROJECT_ROOT, find_free_port
from .lifecycle import progress
from .validate import RenderContext


@dataclass
class EngineResult:
    service_was_started: bool
    cache_hit: bool = False


def _compute_source_hash(ctx: RenderContext) -> str:
    """Compute a short hash of scene source + manifest for cache validation."""
    h = hashlib.sha256()
    for path in (ctx.scene_file, os.path.join(ctx.scene_dir, "manifest.json")):
        if os.path.isfile(path):
            with open(path, "rb") as f:
                h.update(f.read())
    return h.hexdigest()[:16]


def _check_source_hash(ctx: RenderContext) -> bool:
    """Return True if cached output exists and source hasn't changed."""
    hash_file = os.path.join(ctx.output_dir, ".source_hash")
    current = _compute_source_hash(ctx)
    if os.path.isfile(hash_file):
        with open(hash_file, encoding="utf-8") as f:
            stored = f.read().strip()
        if stored == current:
            # Verify that at least one output artifact exists
            candidates = [
                os.path.join(ctx.output_dir, "final.mp4"),
                os.path.join(ctx.output_dir, "raw.mp4"),
            ]
            if ctx.engine_mode != "interactive":
                candidates.append(ctx.frames_dir)
            if any(os.path.exists(p) for p in candidates):
                return True
    return False


def _write_source_hash(ctx: RenderContext) -> None:
    hash_file = os.path.join(ctx.output_dir, ".source_hash")
    with open(hash_file, "w", encoding="utf-8") as f:
        f.write(_compute_source_hash(ctx))


def _resolve_engine_script(ctx: RenderContext) -> str:
    """Resolve engine entry script with backward-compat fallback to legacy render.sh."""
    rel = ctx.engine_conf.get("render_script")
    if rel:
        return os.path.join(PROJECT_ROOT, rel)
    legacy_script = os.path.join(PROJECT_ROOT, "engines", ctx.engine, "scripts", "render.sh")
    if os.path.isfile(legacy_script):
        return legacy_script
    print(f"Error: engine script not found for '{ctx.engine}'", file=sys.stderr)
    sys.exit(1)


def _run_pre_render(ctx: RenderContext) -> None:
    pre_render_rel = ctx.engine_conf.get("pre_render_script")
    if not pre_render_rel:
        return
    pre_render = os.path.join(PROJECT_ROOT, pre_render_rel)
    if not os.path.isfile(pre_render):
        return
    print(f"[pre-render] Running {pre_render}...")
    progress(ctx.scene_name, "shader", "running", message="Pre-rendering shader dependencies")
    subprocess.run(
        [
            "node",
            pre_render,
            ctx.scene_dir,
            "--fps",
            str(ctx.fps),
            "--duration",
            str(ctx.duration),
            "--width",
            str(ctx.width),
            "--height",
            str(ctx.height),
        ],
        check=True,
    )


def _start_service(ctx: RenderContext) -> tuple[str | None, dict | None]:
    """Legacy MC path: spawn a dev server, return (capture_url, state_dict).

    Returns (None, None) if engine.conf has no ``service_script`` or unified MC
    path is in use. Exits with code 1 on service-start failure.
    """
    if ctx.unified_mc_render:
        return None, None
    service_script_rel = ctx.engine_conf.get("service_script")
    if not service_script_rel:
        return None, None

    service_script = os.path.join(PROJECT_ROOT, service_script_rel)
    port_min = ctx.engine_conf.get("service_port_min") or 4567
    port_max = ctx.engine_conf.get("service_port_max") or 5999
    port = find_free_port(port_min, port_max)

    state_path = os.path.join(PROJECT_ROOT, ".agent", "tmp", ctx.scene_name, "state.json")
    stop_script = os.path.join(PROJECT_ROOT, "engines", ctx.engine, "scripts", "render.mjs")
    if os.path.isfile(stop_script) and os.path.isfile(state_path):
        subprocess.run(["node", stop_script, "--stop", ctx.scene_dir], check=False)

    print(f"[service] Starting background service on port {port}...")
    progress(
        ctx.scene_name,
        "serve",
        "running",
        port=port,
        message=f"Starting dev server on port {port}",
    )

    subprocess.run(
        [
            os.path.join(PROJECT_ROOT, "bin", "macode-run"),
            f"{ctx.scene_name}-service",
            "--log",
            ctx.log_file,
            "--",
            "node",
            service_script,
            ctx.scene_dir,
            "--port",
            str(port),
        ],
        check=True,
    )

    service_url: str | None = None
    service_state: dict | None = None
    for _ in range(60):  # 30s timeout, 0.5s steps
        if os.path.isfile(state_path):
            try:
                with open(state_path, encoding="utf-8") as f:
                    service_state = json.load(f)
                outputs = service_state.get("outputs", {})
                if outputs.get("port") == port:
                    service_url = outputs.get("captureUrl")
                    break
            except (json.JSONDecodeError, OSError):
                pass
        time.sleep(0.5)

    if not service_url:
        print(
            "[service] ERROR: Service failed to start or did not write state",
            file=sys.stderr,
        )
        sys.exit(1)
    print(f"[service] Ready at {service_url}")
    return service_url, service_state


def _stop_service(ctx: RenderContext) -> None:
    stop_script = os.path.join(PROJECT_ROOT, "engines", ctx.engine, "scripts", "render.mjs")
    if not os.path.isfile(stop_script):
        return
    print("[service] Stopping background service...")
    subprocess.run(["node", stop_script, "--stop", ctx.scene_dir], check=False)


def _invoke_engine(ctx: RenderContext, engine_script: str, service_url: str | None) -> None:
    if engine_script.endswith(".mjs"):
        cmd: list[str] = ["node", engine_script]
        if ctx.unified_mc_render:
            cmd.extend(
                [
                    ctx.scene_dir,
                    ctx.frames_dir,
                    str(ctx.fps),
                    str(ctx.duration),
                    str(ctx.width),
                    str(ctx.height),
                ]
            )
        elif service_url:
            cmd.extend(
                [
                    service_url,
                    ctx.frames_dir,
                    str(ctx.fps),
                    str(ctx.duration),
                    str(ctx.width),
                    str(ctx.height),
                ]
            )
        else:
            print(
                "Error: Node render script expects unified render.mjs or a running service URL",
                file=sys.stderr,
            )
            sys.exit(1)
    else:
        cmd = ["bash", engine_script]
        if ctx.engine_mode == "interactive":
            cmd.extend(
                [
                    ctx.scene_file,
                    ctx.output_dir,
                    str(ctx.fps),
                    str(ctx.duration),
                    str(ctx.width),
                    str(ctx.height),
                ]
            )
        else:
            cmd.extend(
                [
                    ctx.scene_file,
                    ctx.frames_dir,
                    str(ctx.fps),
                    str(ctx.duration),
                    str(ctx.width),
                    str(ctx.height),
                ]
            )

    subprocess.run(
        [
            os.path.join(PROJECT_ROOT, "bin", "macode-run"),
            ctx.scene_name,
            "--log",
            ctx.log_file,
            "--",
        ]
        + cmd,
        check=True,
    )


def run(ctx: RenderContext) -> EngineResult:
    """Pre-render → service → engine. Returns EngineResult."""
    os.environ["PROJECT_ROOT"] = PROJECT_ROOT

    engine_script = _resolve_engine_script(ctx)

    # P2-A: Source-hash cache check
    if _check_source_hash(ctx):
        print(f"[{ctx.engine}] Source unchanged — using cached output for {ctx.scene_name}")
        progress(
            ctx.scene_name,
            "capture",
            "completed",
            message="Cache hit — reusing previous render",
        )
        return EngineResult(service_was_started=False, cache_hit=True)

    progress(
        ctx.scene_name,
        "init",
        "running",
        message=f"Config: {ctx.fps}fps, {ctx.duration}s, {ctx.width}x{ctx.height}",
    )
    print(f"[{ctx.engine}] Rendering {ctx.scene_name}...")
    print(f"[{ctx.engine}] Scene: {ctx.scene_file}")
    print(f"[{ctx.engine}] Output: {ctx.frames_dir}")
    print(f"[{ctx.engine}] Settings: {ctx.width}x{ctx.height} @ {ctx.fps}fps for {ctx.duration}s")

    service_url: str | None = None
    service_state: dict | None = None

    _run_pre_render(ctx)
    service_url, service_state = _start_service(ctx)

    progress(
        ctx.scene_name,
        "capture",
        "running",
        message="Starting frame capture",
        fps=ctx.fps,
        duration=ctx.duration,
        width=ctx.width,
        height=ctx.height,
    )
    _invoke_engine(ctx, engine_script, service_url)
    progress(ctx.scene_name, "capture", "completed", message="Frame capture completed")

    service_was_started = service_state is not None
    if service_was_started:
        _stop_service(ctx)

    _write_source_hash(ctx)
    return EngineResult(service_was_started=service_was_started, cache_hit=False)
