# MaCode Shader Preview 设计

> **状态**：P3 / 设计完成，待实现
> **触发条件**：素材量 >15 或出现自定义 shader（非 LYGIA）需求
> **当前替代路径**：`shader-render.py` 批量渲染 PNG + `macode dev` 通过 ShaderFrame 预览

---

## 第一部分：MaCode 人类监控机制梳理

MaCode 的人类监控体系由 7 个相互独立、可组合的文件系统原语构成。Shader Preview 必须**完全复用**这些原语，绝不引入新的通信协议。

### 1. 信号系统（Signals）

**路径**：`.agent/signals/`

```text
.agent/signals/
├── global/
│   ├── pause              # touch → 全局暂停所有 Agent
│   └── abort              # touch → 全局中止所有 Agent
├── human_override.json    # 全局覆盖决策
└── per-scene/
    └── {scene_name}/
        ├── pause          # 只暂停该 scene
        ├── abort          # 只中止该 scene
        ├── review_needed  # 等待人类审核
        ├── reject         # 该 scene 被驳回
        └── human_override.json  # 该 scene 的覆盖决策
```

**核心原则**：
- 信号 = **文件存在性**（零字节文件即有效信号）
- Agent 义务：每次执行动作前调用 `bin/signal-check.py` 检查
- 人类权利：`touch`/`rm` 即可控制，无需进程间通信

**Shader Preview 集成**：
- Shader Preview 进程启动前检查 `global/abort`
- 人类可通过 `touch .agent/signals/per-scene/shader-preview-{asset}/review_needed` 标记 shader 需审核
- Agent 渲染含 shader 的场景前，检查对应的 preview 信号

### 2. 进度文本流（Progress Stream）

**路径**：`.agent/progress/{task}.jsonl`

```jsonl
{"timestamp":"2026-05-12T07:32:01Z","phase":"compile","status":"running","progress":0.0}
{"timestamp":"2026-05-12T07:32:03Z","phase":"render","status":"running","progress":0.33,"frames_rendered":30,"frames_total":90}
```

**核心原则**：
- 文本流是唯一真相源，Agent 只写 `.jsonl`
- 人类用 `tail -f` 或 Dashboard SSE 消费
- Agent **不感知** Dashboard 是否存在

**Shader Preview 集成**：
- Preview 服务将渲染状态写入 `.agent/progress/shader-preview-{asset}.jsonl`
- 字段：`phase` ∈ {`init`, `compile`, `preview`, `export`}, `progress` ∈ [0, 1]
- Dashboard 自动消费，显示在场景列表中

### 3. 状态文件（State）

**路径**：`.agent/tmp/{task}/state.json`

```json
{
  "version": "1.0",
  "tool": "shader-preview.mjs",
  "status": "running",
  "outputs": { "url": "http://localhost:8765/preview", "port": 8765 },
  "durationSec": 120.5,
  "agentId": "agent-desktop-1234",
  "pid": 12345
}
```

**核心原则**：
- v1.0 Schema 统一所有引擎和工具
- `state-write.py` 原子写入，支持合并已有状态
- Guardian 通过 `pid` 字段判断进程存活

**Shader Preview 集成**：
- Preview 服务状态写入 `.agent/tmp/shader-preview-{asset}/state.json`
- `outputs.url` 提供浏览器访问地址
- `pid` 用于 Guardian TTL 回收

### 4. 检查报告（Check Reports）

**路径**：`.agent/check_reports/{scene}_{type}.json`

```json
{
  "scene": "02_shader_mc",
  "timestamp": "...",
  "segments": [
    {"id": "main", "status": "pass", "issues": []},
    {"id": "overlay", "status": "warning", "issues": [{"type": "occlusion", "message": "..."}]}
  ]
}
```

**核心原则**：
- POSIX `flock` (.json.lock) 保证并发安全
- Layer1（静态）→ Layer2（帧像素）→ Layer3（人工）
- `check-runner.py` 按 engine 的 `check-registry.json` 分发

**Shader Preview 集成**：
- 新增 `check-shader.py`：对比预渲染 PNG vs 实时 WebGL 输出
- 报告写入 `.agent/check_reports/{scene}_shader.json`
- 人类在 Dashboard 中直接查看差异热力图

### 5. HTML 画面报告（Reports）

**路径**：`.agent/reports/{scene}/index.html`

**核心原则**：
- `report-generator.py` 生成幕画廊（帧 + issues + 代码片段）
- 浏览器打开即可查看，无需服务器
- 每个 UI 元素可追溯到具体文件路径

**Shader Preview 集成**：
- 新增 Shader 专用报告：`.agent/reports/shader-preview-{asset}/index.html`
- 内容：uniform 调参历史 + 帧对比画廊 + 代码片段
- 人类离线审查（无 running server 时仍可查看）

### 6. 实时仪表盘（Dashboard）

**路径**：`bin/dashboard-server.mjs`

**核心原则**：
| 原则 | 实现 |
|------|------|
| **只读文件系统** | 不写入任何状态，重启后重建视图 |
| **文本流真相源** | 消费 `.agent/progress/*.jsonl` |
| **Agent 零感知** | Agent 不依赖 Dashboard，崩溃不影响渲染 |
| **暴露底层路径** | 每个 UI 元素显示对应的文件路径 |

**端点**：
- `GET /` — HTML 仪表盘
- `GET /api/state` — 全量状态 JSON
- `GET /api/scene/{name}` — 单场景详情
- `GET /api/events` — SSE 实时推送

> Multi-Agent 任务队列端点已从 dashboard 移除（PRD 不做 `/api/queue`）。

**Shader Preview 集成**：
- Dashboard 读取 `.agent/tmp/shader-preview-*/state.json` 和 `.jsonl`
- 在场景列表中新增 "Shader Preview" 分类，显示活跃预览
- 右侧 Signal 面板显示 shader 相关的 `review_needed` / `reject`
- 点击 shader 项跳转预览 URL

### 7. 进程与生命周期管理

**组件**：
- `bin/macode-run`：统一进程生命周期 + 超时 + 信号转发
- `server-guardian.mjs`：TTL 自动回收（默认 5 分钟空闲 → stop）
- `bin/cleanup-stale.py`：将 dead PID 的 running 标记为 stalled，可选裁剪旧日志

**Shader Preview 集成**：
- Preview 服务由 `macode-run` 启动，继承超时和信号处理
- Guardian 新增 `shader-preview` 类型扫描
- 空闲 TTL 后自动写入 `state.json` {`status`: `stopped`} 并释放端口

---

## 第二部分：Shader Preview 架构设计

### 1. 问题陈述

当前验证 Layer 2 shader 素材效果的两条路径：

1. `shader-render.py` → 批量输出 PNG 帧 → 图片查看器（~3–10s）
2. 临时 MC 场景 + `macode dev` → Vite HMR 预览（~5–8s 首次启动）

**痛点**：
- 修改一个 uniform 需要重新渲染整个帧序列
- 无**对比模式**：无法并排查看预渲染帧 vs 实时输出
- 无**审查集成**：shader 质量检查游离于人类监控体系之外
- Agent 无法通过标准进度流了解 shader 编译状态

### 2. 设计定位

Shader Preview 不是独立的开发工具，而是**人类监控体系的一个专用扩展面板**：

```
┌─────────────────────────────────────────────┐
│           MaCode 人类监控体系                  │
├─────────────┬─────────────┬─────────────────┤
│  信号系统    │  进度文本流  │   检查报告        │
│  (Signals)  │  (Progress) │  (Check Reports) │
├─────────────┴─────────────┴─────────────────┤
│         实时仪表盘 (Dashboard)                │
│  ┌─────────┐ ┌─────────┐ ┌───────────────┐  │
│  │ Scene   │ │ Queue   │ │ Shader Preview│  │
│  │ Monitor │ │ Status  │ │   Panel       │  │
│  └─────────┘ └─────────┘ └───────────────┘  │
└─────────────────────────────────────────────┘
```

### 3. 用户层命令与内部实现

```
用户层命令                             内部实现
─────────────────────────────────────────────────────────────
macode shader preview <asset_id> [--port <n>] [--open]
    │                                   │
    │   ┌───────────────────────────────┘
    │   │
    │   ├── 1. signal-check.py --scene shader-preview-{asset}
    │   ├── 2. 读取 _registry.json → 定位素材目录
    │   ├── 3. 读取 shader.json → 提取 uniforms schema
    │   ├── 4. 预解析 frag.glsl（LYGIA #include 内联）
    │   ├── 5. GLSL 转译（#version 330 → WebGL 2 ES）
    │   ├── 6. macode-run 启动 HTTP preview 服务
    │   ├── 7. state-write.py → .agent/tmp/shader-preview-{asset}/state.json
    │   ├── 8. progress-write.py → .agent/progress/shader-preview-{asset}.jsonl
    │   └── 9. 注册到 guardian（shader-preview 类型，TTL 5min）
    │
    └── stdout: { "url": "...", "asset": "...", "port": ..., "pid": ... }

macode shader preview-stop <asset_id>
    └── 读取 state.json → SIGTERM → 更新 state → guardian 清理
```

### 4. 文件系统契约

```text
.agent/tmp/shader-preview-{asset_id}/
├── state.json              # v1.0 Schema，含 url/port/pid
├── progress.jsonl          # 渲染进度文本流
├── frames/                 # 导出的 PNG 帧（人类审核用）
│   └── frame_0001.png
└── logs/
    └── shader-preview.log  # GLSL 编译日志

.agent/signals/per-scene/shader-preview-{asset_id}/
├── review_needed           # 人类标记：该 shader 需审核
├── reject                  # 人类标记：该 shader 被驳回
└── human_override.json     # 覆盖决策 + reject 理由（复用现有机制）
                            # { "action": "reject", "reason": "...", "suggested_fix": "..." }

.agent/check_reports/
└── {scene}_shader.json     # check-shader.py 对比报告

.agent/reports/shader-preview-{asset_id}/
└── index.html              # 离线审查报告（uniform 历史 + 帧对比）
```

### 5. HTTP 服务端点

| 端点 | 说明 | 消费者 |
|------|------|--------|
| `GET /preview` | WebGL 预览页面 + 控制面板 | 人类浏览器 |
| `GET /api/asset` | JSON：GLSL 源码 + uniforms schema | Agent / 外部工具 |
| `GET /api/frame?time=1.5` | 最接近该时间的预渲染 PNG | 对比验证 |
| `GET /api/registry` | 完整 `_registry.json` | 素材发现 |
| `GET /api/export/png` | `gl.readPixels()` → PNG 下载 | 人类导出 |
| `POST /api/signal` | 写入人类信号（review/reject/approve） | 浏览器 UI |

### 6. GLSL 转译（桌面 → WebGL 2）

| 桌面 GLSL | WebGL 2 GLSL | 说明 |
|-----------|-------------|------|
| `#version 330` | `#version 300 es` | 版本声明 |
| `texture2D()` | `texture()` | WebGL 2 统一命名 |
| `textureCube()` | `texture()` | 同上 |
| 无精度修饰 | `precision highp float;` | ES 必须显式指定 |

LYGIA `#include` 在**服务端预解析**后传给浏览器，浏览器不再处理文件系统 include。

### 7. 浏览器端 UI

**控制面板**（基于 `shader.json` 的 `uniforms` schema 自动生成）：

- `float` + `animation.enabled` → 时间轴 scrub slider
- `vec2`（如 `resolution`）→ 只读显示
- `vec3`（如 `color`）→ 颜色选择器
- 其他类型 → 根据 schema 生成对应 input

**交互功能**：
- **Scrub**：拖动时间轴 → 更新 `u_time` → 重新渲染
- **Play/Pause**：`requestAnimationFrame` 循环驱动
- **Export PNG**：`gl.readPixels()` → Canvas 2D → `canvas.toDataURL()`
- **对比模式**：WebGL 实时输出 vs 预渲染 PNG 并排显示
- **信号按钮**：浏览器直接 `POST /api/signal` 创建 `review_needed` / `reject` / `approve`
  - `reject` 携带的理由写入同目录 `human_override.json`（复用现有信号机制，零改动）

### 8. Dashboard 集成

Dashboard 的 `listScenes()` 函数需扩展，读取 `.agent/tmp/shader-preview-*/`：

```javascript
// dashboard-server.mjs 新增
function listShaderPreviews() {
  const previews = [];
  if (!fs.existsSync(TMP_DIR)) return previews;
  for (const dir of fs.readdirSync(TMP_DIR)) {
    if (!dir.startsWith('shader-preview-')) continue;
    const statePath = path.join(TMP_DIR, dir, 'state.json');
    const progressPath = path.join(PROGRESS_DIR, `${dir}.jsonl`);
    // ... 类似 listScenes 的逻辑
    previews.push({ name: dir, type: 'shader-preview', ... });
  }
  return previews;
}
```

UI 变更：
- 场景列表顶部新增 "Shader Previews" 分组
- 状态 dot：蓝色脉冲 = 运行中，绿色 = 已审核，黄色 = review_needed，红色 = reject
- 主面板显示：WebGL canvas iframe + uniform 面板 + 信号按钮
- 右侧 Signals 面板显示 shader 专用信号

---

## 第三部分：与现有基础设施的复用

| 已有组件 | 复用方式 | 新建/修改代码量 |
|---------|---------|---------------|
| `signal-check.py` | 无需修改，shader-preview 作为 scene_name 传入 | 0 |
| `progress-write.py` | 无需修改，shader preview 复用同一 JSONL 格式 | 0 |
| `state-write.py` | 无需修改，输出标准 v1.0 state.json | 0 |
| `server-guardian.mjs` | 新增 `shader-preview` 类型扫描逻辑 | ~20 行 |
| `macode-run` | 直接启动 `bin/shader-preview.mjs` | 0 |
| `dashboard-server.mjs` | 新增 `listShaderPreviews()` + UI 分组 | ~80 行 |
| `report-generator.py` | 新增 shader 专用报告模板 | ~50 行 |
| `lygia_resolver.py` | Node.js 中移植简化版，或子进程调用 Python 预解析 | ~80 行 |
| `check-shader.py` | 新建：预渲染 PNG vs WebGL 输出对比 | ~100 行 |
| `bin/shader-preview.mjs` | 新建：HTTP server + WebGL renderer + UI | ~350 行 |

---

## 第四部分：CLI 接口

```bash
# 启动 shader 预览
macode shader preview <asset_id> [--port <n>] [--open] [--watch] [--fps <n>]

# 停止 shader 预览
macode shader preview-stop <asset_id>

# 生成 shader 审查报告
macode shader report <asset_id> [--output <dir>]

# 运行 shader 对比检查
bin/check-shader.py scenes/02_shader_mc/
```

**stdout JSON**（`macode shader preview`）：
```json
{
  "asset": "lygia_circle_heatmap",
  "url": "http://localhost:8765/preview",
  "api": "http://localhost:8765/api/asset",
  "port": 8765,
  "pid": 12345,
  "stateFile": ".agent/tmp/shader-preview-lygia_circle_heatmap/state.json",
  "progressFile": ".agent/progress/shader-preview-lygia_circle_heatmap.jsonl"
}
```

---

## 第五部分：实现优先级

| 优先级 | 任务 | 预计行数 | 依赖 |
|--------|------|---------|------|
| P0 | GLSL 预解析 + 转译（Node.js） | ~120 | lygia_resolver |
| P0 | HTTP server + 状态/进度管理 | ~80 | state-write, progress-write |
| P0 | 浏览器端 WebGL renderer | ~150 | 无 |
| P1 | UI：时间轴 + uniform 面板 + 信号按钮 | ~100 | 无 |
| P1 | Dashboard 集成（listShaderPreviews + UI） | ~80 | dashboard-server |
| P1 | Guardian 集成（shader-preview 类型） | ~20 | server-guardian |
| P1 | macode CLI 路由（shader preview / preview-stop） | ~15 | 无 |
| P2 | check-shader.py（对比检查） | ~100 | 无 |
| P2 | 报告生成器扩展（shader 专用报告） | ~50 | report-generator |
| P2 | 对比模式（WebGL vs 预渲染 PNG） | ~50 | 无 |
| P2 | 导出 PNG | ~30 | 无 |

**核心功能总计**：~795 行，预计 1–2 天完成。

---

## 第六部分：触发条件

满足任一即启动实现：

1. `_registry.json` assets 数量 > 15
2. 出现自定义 GLSL（非 LYGIA）需求
3. Agent 迭代 shader 的频次显著上升（>3 次/天）
4. 人类审查 shader 的时间成本超过 10 分钟/素材

---

## 附录：人类监控原语速查

| 原语 | 路径 | 写入者 | 消费者 | 格式 |
|------|------|--------|--------|------|
| 信号 | `.agent/signals/` | 人类 (touch) | Agent (signal-check.py) | 文件存在性 |
| 进度 | `.agent/progress/*.jsonl` | Agent (progress-write.py) | Dashboard / tail -f | JSON Lines |
| 状态 | `.agent/tmp/*/state.json` | Agent (state-write.py) | Dashboard / Guardian | JSON v1.0 |
| 检查 | `.agent/check_reports/*.json` | check-runner.py | Dashboard / report-gen | JSON |
| 报告 | `.agent/reports/*/index.html` | report-generator.py | 人类浏览器 | HTML |
| 日志 | `.agent/log/*.log` | 所有脚本 (tee) | 人类 (tail) | 纯文本 |
