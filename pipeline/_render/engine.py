"""Engine stage: cache check, pre-render, optional service, engine invocation.

Top-level: ``run(ctx)`` returns ``EngineResult``. Cache hits skip the engine.
Background dev servers (legacy MC path) are started under ``macode-run`` so
lifecycle/log capture stays unified.
"""

from __future__ import annotations

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
    cache_hit: bool
    service_was_started: bool


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


def _check_cache(ctx: RenderContext) -> bool:
    cache_script = os.path.join(PROJECT_ROOT, "pipeline", "cache.sh")
    if not (os.path.isfile(cache_script) and os.access(cache_script, os.X_OK)):
        return False
    with open(ctx.log_file, "a", encoding="utf-8") as logf:
        result = subprocess.run(
            ["bash", cache_script, ctx.scene_dir, "check", ctx.output_dir],
            stdout=logf,
            stderr=subprocess.STDOUT,
        )
    if result.returncode == 0:
        print("[cache] Using cached frames, skipping engine render")
        return True
    print("[cache] Cache miss, rendering with engine...")
    return False


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
    """Cache → pre-render → service → engine. Returns EngineResult."""
    os.environ["PROJECT_ROOT"] = PROJECT_ROOT

    engine_script = _resolve_engine_script(ctx)

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

    cache_hit = _check_cache(ctx)
    service_url: str | None = None
    service_state: dict | None = None

    if not cache_hit:
        _run_pre_render(ctx)
        service_url, service_state = _start_service(ctx)

    if not cache_hit:
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

    return EngineResult(cache_hit=cache_hit, service_was_started=service_was_started)
