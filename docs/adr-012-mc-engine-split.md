# ADR-012: Motion Canvas 引擎编排/执行拆分（路径 B）

**状态**: Accepted（讨论归档）  
**日期**: 2026-05-10  
**决策者**: agent (Kimi Code CLI)  
**影响范围**: `engines/motion_canvas/`, `pipeline/render-scene.py`, `bin/macode`

> **当前实现补充（2026-05）**：Motion Canvas 侧已合并为单一入口 **`engines/motion_canvas/scripts/render.mjs`**（批量渲染 / `--serve-only` / `--stop` / `--snapshot`）。`render-cli.mjs`、`serve.mjs`、`stop.mjs`、`playwright-render.mjs`、`browser-pool.mjs`、`server-guardian.mjs` 等旧文件已从仓库移除。下文保留当时的**问题陈述与方案推演**，便于理解决策脉络；具体 CLI 以 `render.mjs --help` 与 `AGENTS.md` Motion Canvas 小节为准。

---

## 背景

Phase 5 测试骨架完成后，四问法审计暴露出 Motion Canvas 引擎存在严重的职责混杂：

- `render-cli.mjs` 是一个**披着执行层外衣的编排器**——它内部编排 shader 预渲染、dev server 生命周期、playwright 抓帧三个执行单元。
- `serve.mjs` 泄露了编排职责——全局端口扫描其他场景的 `state.json`、启动跨任务 guardian 守护进程。
- `pipeline/render-scene.py` 内联了执行逻辑——`run_copilot`（终端 I/O）、`parse_engine_conf`（YAML/grep 解析）、`.mjs` 引擎直接 `subprocess.run` 绕过 `macode-run`。

这些违反破坏了 Harness 2.0 的编排/执行分离原则。

---

## 问题

在修复上述问题的同时，**能否保持引擎无关性**？

如果保守包装只是把 `render-cli.mjs` 的逻辑上提到 `render-scene.py`，用硬编码的 `if engine == 'motion_canvas'` 处理 MC 特殊需求，就会彻底破坏引擎无关。

---

## 调研：Vite 冷启动机制

关键发现：**不同场景之间本来就不共享 dev server**。`serve.mjs` 每次启动都会重写 `project.ts`（指向对应场景的 `scene.tsx`），然后启动独立的 Vite 进程。当前实现的"复用"只是让**同一场景的多次调用**（如 retry）跳过 Vite 启动。

Vite 冷启动的真实开销：

| 阶段 | 首次场景 | 后续场景（缓存命中） |
|------|---------|-------------------|
| 依赖预构建（esbuild） | **2-5s** | **0ms** |
| Vite 配置加载 + 项目编译 | ~300-800ms | ~300-800ms |
| HTTP server 就绪 | ~50ms | ~50ms |
| Playwright 浏览器连接 | ~100ms（Browser Pool 全局复用） | ~100ms |

Browser Pool（`browser-pool.mjs`）已经是**跨场景全局复用**的 Chromium 实例，不受 Vite server 生命周期影响。

**结论**："每调用独立 server" vs "复用"的差异只在于同一场景 retry 时多花 1-2s。这个代价在工程上完全可以接受。

---

## 方案对比

| 方案 | 引擎无关性 | 性能影响 | 复杂度 |
|------|-----------|---------|--------|
| A. 激进拆分（3 个独立执行工具 + render-scene.py 统一编排） | ✅ | retry +1-2s | 高 |
| **B. 保守包装（声明式 engine.conf 扩展 + 每调用独立 server）** | **✅** | **retry +1-2s** | **中** |
| C. 硬编码上提（render-scene.py 内联 MC 特殊逻辑） | ❌ | 无 | 低（债务重） |

**选择路径 B**。

---

## 实施细节

### 1. engine.conf 声明式扩展

新增顶层字段（扁平化，grep 可解析）：

```yaml
render_script: engines/motion_canvas/scripts/playwright-render.mjs
pre_render_script: engines/motion_canvas/scripts/shader-prepare.mjs
service_script: engines/motion_canvas/scripts/serve.mjs
service_port_min: 4567
service_port_max: 5999
```

`render-scene.py` 通过扩展后的 `parse_engine_conf()` 读取这些字段，按通用协议执行：
- 有 `pre_render_script` → 渲染前执行
- 有 `service_script` → 分配端口 → 启动后台服务 → 传 URL 给 `render_script` → 渲染完成后停止服务

**这保持了引擎无关**：新增一个需要后台服务的引擎（如 Blender 实时预览），只需提供新的 `engine.conf` 和脚本，无需修改 `render-scene.py`。

### 2. 执行层拆分

- **`shader-prepare.mjs`**：从 `render-cli.mjs` 提取。纯执行：读取 manifest → 检查 shader 缓存 → 调用 `bin/shader-render.py`。
- **`serve.mjs` 瘦身**：去掉 `getAllocatedPorts`（全局端口协调）、`ensureGuardianRunning`（guardian 启动）。保留位置参数 `[port]`（向后兼容 `macode mc serve`），新增 `--port` 支持。在 `state.json` 中增加 `captureUrl` 字段。
- **`playwright-render.mjs`**：保持不变（已足够干净）。
- **删除 `render-cli.mjs`**：其编排职责上提到 `render-scene.py`。

### 3. render-scene.py 改造

- `.mjs` 引擎统一走 `macode-run` 生命周期管理（之前直接 `subprocess.run` 绕过）。
- 新增通用后台服务编排：`find_free_port()` + `macode-run` 启动 + 轮询 `state.json` + `stop.mjs` 清理。
- 新增 `write_progress()` 为所有引擎统一输出 `progress.jsonl`。
- 修复 `find_free_port()` 的 socket 超时问题（`s.settimeout(0.2)`），避免某些端口状态导致无限阻塞。

### 4. bin/macode 去硬编码

删除 `render` 子命令中的 `if [[ "$ENGINE" == "motion_canvas" ]]` 分支，所有引擎统一走 `pipeline/render.sh` → `render-scene.py`。

### 5. validate-manifest.py 改进

`resolution` 字段变为可选（`render-scene.py` 已有默认 `[1920, 1080]`），避免已有场景因缺少该字段而无法渲染。

---

## 后续：Phase 3B — 状态外化统一格式

路径 B 完成后，所有引擎统一走 `macode-run`，但各工具的 `state.json` 格式仍然不一致。Phase 3B 定义了 **MaCode Task State v1** 统一 schema：

```json
{
  "version": "1.0",
  "tool": "serve.mjs",
  "status": "completed",
  "exitCode": 0,
  "outputs": {
    "port": 4567,
    "captureUrl": "http://localhost:4567/..."
  }
}
```

**关键改动**：
- `bin/macode-run`：增加 `version`、`outputs` 字段；子进程可通过 `MACODE_STATE_DIR` 环境变量写 `task.json`，退出后自动合并到 `state.json`
- `serve.mjs`：`port` / `captureUrl` 移入 `outputs` 字典，保留顶层 `pid`（stop.mjs 需要）
- `playwright-render.mjs`：渲染完成后写 `task.json`
- `render-scene.py`：统一通过 `outputs` 字典读取工具输出，不再硬编码引擎特定字段名

**透明性**：`docs/task-state-schema.md` 文档化 schema，所有状态文件是纯 JSON，可用 `cat`/`jq` 直接查看。

---

## 后续：Phase 4 — 缓存升级（UNIX 风格）

旧 `cache.sh` 是单体式 bash 脚本（计算哈希 + 检查 + 存储/恢复混在一起）。Phase 4 将其拆分为 4 个独立工具：

| 工具 | 职责 | UNIX 哲学 |
|------|------|----------|
| `cache-key.py` | 输入 scene_dir → 输出缓存键（stdout） | 只做一件事 |
| `cache-check.py` | 输入 key → exit 0/1 | 只做一件事 |
| `cache-store.py` | 输入 key + source_dir → 存入 `.agent/cache/{key}/` | 只做一件事 |
| `cache-restore.py` | 输入 key + dest_dir → 恢复到目标目录 | 只做一件事 |

`pipeline/cache.sh` 变为向后兼容的**适配层**，内部调用上述工具链。

**关键改进**：
- 缓存键纳入 **shader 依赖哈希**（`frag.glsl` / `vert.glsl` / `shader.json`），shader 源文件变更自动失效
- 缓存存储**整个 output_dir**（frames + final.mp4 + 其他产物），不只是 frames/
- 每个缓存目录包含 `.cache_manifest`（JSON 文本），可直接查看缓存来源
- **引擎无关**：`cache-key.py` 不再只匹配 `scene.*`，而是扫描场景目录下所有非隐藏文件 + 一级子目录文件（排除 `__pycache__` / `node_modules` / 编辑器备份等）

---

## 验证

9/9 冒烟测试全部通过：

- `test_manim_single_render` ✅
- `test_manim_param_override` ✅
- `test_mc_single_render` ✅
- `test_mc_dev_server_lifecycle` ✅
- `test_mc_shaderframe` ✅
- `test_composite_render` ✅
- `test_composite_unified_render` ✅
- `test_hybrid_overlay` ✅
- `test_manifest_validation_fail` ✅

---

## 四问法合规检查（Phase 3B + Phase 4）

| 文件 | 层 | 违反？ | 说明 |
|------|---|--------|------|
| `bin/macode-run` | 执行 | ❌ | 管理单子进程生命周期 + 合并 task.json，符合 Q1/Q2/Q3/Q4 |
| `bin/cache-key.py` | 执行 | ❌ | 纯计算：输入目录 → 输出哈希 |
| `bin/cache-check.py` | 执行 | ❌ | 纯检查：输入 key → exit 0/1 |
| `bin/cache-store.py` | 执行 | ❌ | 纯存储：输入 key + dir → 文件系统写入 |
| `bin/cache-restore.py` | 执行 | ❌ | 纯恢复：输入 key + dir → 文件系统复制 |
| `pipeline/cache.sh` | 执行 | ❌ | 适配层，只调度上述 4 个工具 |
| `serve.mjs` | 执行 | ❌ | 生成 project.ts + 启动 Vite + 写状态，只做"启动 dev server"一件事 |
| `playwright-render.mjs` | 执行 | ❌ | 连接 dev server + 抓帧 + 写 task.json，只做"抓帧"一件事 |
| `render-scene.py` | 编排 | ❌ | 按 engine.conf 调度 pre-render → service → capture → concat，符合四问 |

---

## 后果

### 正面
- MC 引擎从"子编排器"退化为纯执行层，四问法合规。
- 新增引擎支持后台服务时，只需声明式配置，无需修改编排层代码。
- 所有引擎统一走 `macode-run`，`state.json` / `progress.jsonl` 输出格式一致。
- `bin/macode render` 不再有引擎硬编码分支。
- 缓存键纳入 shader 依赖，避免"场景文件未改但 shader 改了"的缓存误命中。
- 缓存工具链符合 UNIX 哲学：4 个独立工具，每个只做一件事，exit 码传递状态。

### 负面
- 同一场景 retry 时无法复用 dev server，多花 1-2s Vite 启动时间。
- `engine.conf` 的 grep 解析更复杂（需加 `^` 行首锚点避免 `pre_render_script` 误匹配 `render_script`）。
- 缓存存储整个 output_dir（包括 MP4），占用更多磁盘空间。

### 未来工作
- 如果 retry 性能成为瓶颈，可在 `render-scene.py` 中增加可选的 dev server 复用逻辑（检查旧 state.json → 健康检查 → 复用），但这会增加编排层的复杂度，需要重新评估四问法合规性。
- `cache-key.py` 可扩展为支持外部依赖（如 `node_modules` 版本变更）的哈希纳入。
