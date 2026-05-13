# Escape hatches baseline (MaCode)

**Generated:** 2026-05-13 09:04:54 UTC · **HEAD:** `89507a20ceba5a1937e09e44f4dfab8f444e1b28`

Source scan: `bin/`, `pipeline/`, `engines/` with `--glob '!**/node_modules/**'`.

## Table of contents

- [Group 1 — CLI flags (`--no-claim`, `--no-review`, `--skip-checks`, `--fresh`, `--keep-server`)](#group-1--cli-flags---no-claim---no-review---skip-checks---fresh---keep-server)
- [Group 2 — `fallback`, `guardian`, `stale`, `override`, `bypass`](#group-2--fallback-guardian-stale-override-bypass)

## Group 1 — CLI flags (`--no-claim`, `--no-review`, `--skip-checks`, `--fresh`, `--keep-server`)

Command:

```text
rg -n --glob '!**/node_modules/**' \
  -e '--no-claim|--no-review|--skip-checks|--fresh|--keep-server' \
  bin/ pipeline/ engines/
```

Output:

```text
pipeline/composite-unified-render.py:8:        [--width W] [--height H] [--no-review]
pipeline/composite-unified-render.py:70:               "  %(prog)s scenes/04_composite_unified_demo --json --no-review",
pipeline/composite-unified-render.py:79:    parser.add_argument("--no-review", action="store_true", help="Skip review-needed marking")
pipeline/composite-unified-render.py:126:        render_cmd.append("--no-review")
pipeline/render-scene.py:103:    parser.add_argument("--no-review", action="store_true", help="Skip review-needed marking (for batch testing)")
pipeline/render-scene.py:104:    parser.add_argument("--no-claim", action="store_true", help="Skip scene concurrency claim (for internal composite calls)")
pipeline/render-scene.py:105:    parser.add_argument("--skip-checks", action="store_true", help="Skip static checks (for manual debugging)")
```

## Group 2 — `fallback`, `guardian`, `stale`, `override`, `bypass`

Command:

```text
rg -n --glob '!**/node_modules/**' \
  -e 'fallback|guardian|stale|override|bypass' \
  bin/ pipeline/ engines/
```

Output:

```text
engines/manim/src/components/narrative_scene.py:44:    Subclasses override :attr:`NARRATIVE_PROFILE` to select a narrative
bin/cleanup-stale.py:2:"""bin/cleanup-stale.py
bin/cleanup-stale.py:3:Scan and clean up stale agent states.
bin/cleanup-stale.py:6:    cleanup-stale.py [--dry-run]
bin/cleanup-stale.py:25:def scan_stale_states(tmp_dir: str, dry_run: bool = False) -> int:
bin/cleanup-stale.py:106:    parser = argparse.ArgumentParser(description="Clean up stale agent states and expired claims.")
bin/cleanup-stale.py:116:    stalled = scan_stale_states(tmp_dir, dry_run=args.dry_run)
bin/macode:360:                    echo "  JSON sync: ✗ stale (run: macode sourcemap validate $engine_name)"
bin/macode:523:        python3 "$PROJECT_ROOT/bin/cleanup-stale.py" "$@"
bin/macode:661:  review <list|approve|reject|override|log> [args]
bin/macode:666:    override <scene> --action <action> --instruction <msg>
bin/macode:667:                                  Human override (retry/modify/stop)
engines/manim/src/components/zoned_scene.py:26:    Subclasses override :attr:`LAYOUT_PROFILE` to select a layout template
bin/signal-check.py:8:Per-scene signals (pause, abort, review_needed, reject, override, feedback)
bin/signal-check.py:41:    """Check per-scene signals (pause, abort, review_needed, override, feedback, reject)."""
bin/signal-check.py:47:        "human_override": None,
bin/signal-check.py:51:    override_path = scene_dir / "human_override.json"
bin/signal-check.py:52:    if override_path.exists():
bin/signal-check.py:54:            result["human_override"] = json.loads(override_path.read_text(encoding="utf-8"))
bin/macode-hash:231:    # Temporarily override sys.path for resolution
bin/api-gate.py:23:    """解析 SOURCEMAP，返回禁止的模块模式列表。优先读取 JSON sourcemap，fallback 到 Markdown。"""
bin/api-gate.py:61:                # fallback to markdown below
bin/api-gate.py:189:    (r'\b__import__\s*\(', '__import__() — dynamic import bypass'),
engines/manim/src/utils/shader_bridge.py:43:        duration: override rendering duration (seconds)
engines/manim/src/utils/shader_bridge.py:44:        fps: override rendering fps
bin/agent:131:- 定期运行 python3 bin/cleanup-stale.py 清理残留
bin/agent:152:- python3 bin/cleanup-stale.py 清理 dead-PID 和过期 claim
bin/sourcemap-read:124:    # fallback: Python
bin/sandbox-check.py:21:    # Dynamic import bypass
bin/sandbox-check.py:22:    (r'\b__import__\s*\(', '__import__() — dynamic import bypass'),
pipeline/render-scene.py:119:    # ── Check for previous round human_override ──
pipeline/render-scene.py:122:    override_path = per_scene_dir / "human_override.json"
pipeline/render-scene.py:125:    if override_path.exists():
pipeline/render-scene.py:127:            override = json.loads(override_path.read_text(encoding="utf-8"))
pipeline/render-scene.py:128:            action = override.get("action")
pipeline/render-scene.py:131:                override_path.unlink(missing_ok=True)
pipeline/render-scene.py:135:                reason = override.get("reason", "")
pipeline/render-scene.py:137:                override_path.unlink(missing_ok=True)
pipeline/render-scene.py:141:                instruction = override.get("instruction", "")
pipeline/render-scene.py:143:                override_path.unlink(missing_ok=True)
pipeline/render-scene.py:145:                    "status": "override_received",
pipeline/render-scene.py:152:            print(f"[review] Warning: corrupt override file: {e}", file=sys.stderr)
pipeline/render-scene.py:153:            override_path.unlink(missing_ok=True)
pipeline/render-scene.py:155:    # ── If review is pending and no override yet, skip re-render ──
pipeline/render-scene.py:397:        # Clean up any stale service state for this scene
bin/shader-preview.mjs:212:    <textarea class="signal-reason" id="signalReason" placeholder="Reason / override / suggested fix (optional)"></textarea>
bin/shader-preview.mjs:439:            const override = {
bin/shader-preview.mjs:445:            fs.writeFileSync(path.join(sceneDir, 'human_override.json'), JSON.stringify(override, null, 2));
bin/detect-hardware.sh:204:            # Remove stale llvmpipe/software renderer warnings — D3D12 is now active
bin/security-advise.py:22:        "why": "os.system() executes arbitrary shell commands, bypassing MaCode's process lifecycle management (macode-run) and audit trails.",
bin/shader-render.py:56:    parser.add_argument("--fps", type=float, default=None, help="Frames per second (override shader.json)")
bin/shader-render.py:57:    parser.add_argument("--duration", type=float, default=None, help="Duration in seconds (override shader.json)")
bin/shader-render.py:58:    parser.add_argument("--resolution", type=str, default=None, help="Resolution as WxH, e.g. 1920x1080 (override shader.json)")
bin/shader-render.py:74:    # Resolve overrides
bin/macode-review:11:#   macode-review override <scene> --action retry --instruction "..."
bin/macode-review:29:  override <scene> --action <retry|skip> --instruction "..."
bin/macode-review:37:  macode-review override 01_test --action retry --instruction "Reduce font size by 20%"
bin/macode-review:72:    cat > "$scene_dir/human_override.json" <<EOF
bin/macode-review:84:    cat > "$scene_dir/human_override.json" <<EOF
bin/macode-review:90:override_scene() {
bin/macode-review:112:    cat > "$scene_dir/human_override.json" <<EOF
bin/macode-review:139:    if [[ -f "$scene_dir/human_override.json" ]]; then
bin/macode-review:140:        echo "  Pending override:"
bin/macode-review:141:        cat "$scene_dir/human_override.json" | python3 -m json.tool 2>/dev/null || cat "$scene_dir/human_override.json"
bin/macode-review:168:    override)
bin/macode-review:169:        [[ -z "${1:-}" ]] && { echo "Usage: macode-review override <scene> --action <retry|skip> --instruction \"...\"" >&2; exit 1; }
bin/macode-review:170:        override_scene "$@"
engines/manim/scripts/render.sh:114:        # Clean old snapshots to avoid stale data
bin/checks/_utils.py:349:    """Count non-stale claim files across all scenes."""
bin/checks/_utils.py:441:            return {"claimed": False, "stale": True}
engines/manimgl/scripts/inspect.sh:82:    echo "--- Built-in Mobjects (static fallback) ---"
engines/manimgl/src/components/narrative_scene.py:44:    Subclasses override :attr:`NARRATIVE_PROFILE` to select a narrative
engines/manimgl/src/components/narrative_scene.py:50:    # Animation primitives — subclasses may override for stylistic tweaks.
engines/manimgl/scripts/render.sh:101:        # Clean old snapshots to avoid stale data
engines/manimgl/scripts/render.sh:141:# Remove old MACODE_HEADLESS check (or keep as override)
engines/manimgl/scripts/render.sh:143:    echo "[manimgl] MACODE_HEADLESS override active."
engines/manimgl/src/components/zoned_scene.py:43:    Subclasses override :attr:`LAYOUT_PROFILE` to select a layout template
engines/manimgl/src/templates/scene_base.py:25:    Subclasses can override class attributes to adjust behavior::
engines/manimgl/src/templates/scene_base.py:72:        """Intro animation. Default no-op; override for unified intro effects."""
engines/manimgl/src/templates/scene_base.py:76:        """Outro animation. Default no-op; override for unified outro effects."""
engines/manimgl/src/utils/shader_backend.py:74:        # Default conservative fallback
engines/motion_canvas/scripts/stop.mjs:63:  console.log(`[stop] No PID in state file. Cleaning up stale state.`);
engines/manimgl/src/utils/lygia_resolver.py:27:# Consumers can override via environment variable MACODE_LYGIA_ROOT.
engines/motion_canvas/scripts/serve.mjs:15: *   - NO global port coordination, NO guardian spawning, NO orchestration
engines/motion_canvas/src/components/ShaderFrame.tsx:82:   * Explicit time override in seconds. When negative (default) the node's
engines/manimgl/src/utils/shader_runner.py:239:        override_resolution: tuple[int, int] | None = None,
engines/manimgl/src/utils/shader_runner.py:240:        override_duration: float | None = None,
engines/manimgl/src/utils/shader_runner.py:241:        override_fps: float | None = None,
engines/manimgl/src/utils/shader_runner.py:257:        fps = override_fps or render_cfg.get("fps", 30)
engines/manimgl/src/utils/shader_runner.py:258:        duration = override_duration or render_cfg.get("duration", 3.0)
engines/manimgl/src/utils/shader_runner.py:259:        res = override_resolution or tuple(render_cfg.get("resolution", [1920, 1080]))
engines/manimgl/src/utils/shader_builder.py:41:        Default is empty; override when a node needs to declare functions or
engines/motion_canvas/SOURCEMAP.md:73:| Use `eval()` or `new Function()` | Use static imports and MaCode helper functions | Arbitrary execution bypasses sandbox |
engines/motion_canvas/scripts/server-guardian.mjs:3: * engines/motion_canvas/scripts/server-guardian.mjs
engines/motion_canvas/scripts/server-guardian.mjs:7: *   server-guardian.mjs [--daemon] [--ttl <minutes>]
engines/motion_canvas/scripts/server-guardian.mjs:18: *   5. daemon 模式下：若连续 10min 无存活 server，guardian 自毁
engines/motion_canvas/scripts/server-guardian.mjs:28:const GUARDIAN_TMP = path.join(PROJECT_ROOT, '.agent', 'tmp', 'dev-guardian');
engines/motion_canvas/scripts/server-guardian.mjs:35:  console.log(`Usage: node server-guardian.mjs [--daemon] [--ttl <minutes>]
engines/motion_canvas/scripts/server-guardian.mjs:37:Dev Server lazy-reclaim guardian.
engines/motion_canvas/scripts/server-guardian.mjs:75:    if (entry.name === 'browser-pool' || entry.name === 'dev-guardian') continue;
engines/motion_canvas/scripts/server-guardian.mjs:101:          console.log(`[guardian] ${entry.name}: idle ${Math.round(idle/1000)}s > TTL, stopping...`);
engines/motion_canvas/scripts/server-guardian.mjs:106:          console.log(`[guardian] ${entry.name}: active, idle ${Math.round(idle/1000)}s`);
engines/motion_canvas/scripts/server-guardian.mjs:109:        console.log(`[guardian] ${entry.name}: active (no idle tracking)`);
engines/motion_canvas/scripts/server-guardian.mjs:133:      console.log(`[guardian] ${entry.name}: idle ${Math.round(idle / 1000)}s > ${Math.round(TTL_MS / 1000)}s, stopping...`);
engines/motion_canvas/scripts/server-guardian.mjs:138:      console.log(`[guardian] ${entry.name}: active, idle ${Math.round(idle / 1000)}s`);
engines/motion_canvas/scripts/server-guardian.mjs:149:  console.log(`[guardian] Daemon started (pid=${process.pid}, ttl=${Math.round(TTL_MS / 1000)}s)`);
engines/motion_canvas/scripts/server-guardian.mjs:163:      console.log(`[guardian] Stopped ${sc} idle server(s)`);
engines/motion_canvas/scripts/server-guardian.mjs:167:    const guardianIdle = Date.now() - lastHadServers;
engines/motion_canvas/scripts/server-guardian.mjs:168:    if (ac === 0 && guardianIdle > GUARDIAN_IDLE_TTL_MS) {
engines/motion_canvas/scripts/server-guardian.mjs:169:      console.log(`[guardian] No servers for ${Math.round(guardianIdle / 1000)}s, shutting down`);
engines/motion_canvas/scripts/server-guardian.mjs:238:  // 检查是否已有 guardian 在运行
engines/motion_canvas/scripts/server-guardian.mjs:243:        console.log(`[guardian] Already running (pid=${st.pid}), exiting`);
engines/motion_canvas/scripts/server-guardian.mjs:251:    console.log(`[guardian] Scan complete: ${activeCount} active, ${stoppedCount} stopped`);
engines/motion_canvas/scripts/inspect.sh:75:    echo "--- Common Nodes (static fallback) ---"
engines/manimgl/src/utils/ffmpeg_builder.py:198:        Setting this overrides simple -vf / -af filter chains.
engines/motion_canvas/src/utils/mathjax_bridge.ts:81:    const fallbackSvg = `<?xml version="1.0" encoding="UTF-8"?>
engines/motion_canvas/src/utils/mathjax_bridge.ts:89:    fs.writeFileSync(outPath, fallbackSvg, 'utf-8');
```
