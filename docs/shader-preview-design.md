# Shader Preview 设计储备

> **状态**：P3 / 按需触发  
> **触发条件**：素材量 >15 或出现自定义 shader（非 LYGIA）需求  
> **当前替代路径**：`shader-render.py` 批量渲染 PNG + `macode dev` 通过 ShaderFrame 预览

---

## 1. 问题陈述

当前验证 Layer 2 shader 素材效果的路径：

1. `shader-render.py` → 批量输出 PNG 帧 → 图片查看器（~3-10s）
2. 临时 MC 场景 + `macode dev` → Vite HMR 预览（~5-8s 首次启动）

这两条路径在**实时调参**场景下效率低：修改一个 uniform 需要重新渲染整个帧序列。

---

## 2. 架构定位（Harness 2.0）

```
用户层命令                          内部实现
─────────────────────────────────────────────────────────────
macode shader preview <asset_id> [--port <n>] [--open]
    │                                   │
    │   ┌───────────────────────────────┘
    │   │
    │   ├── 1. 读取 _registry.json → 定位素材目录
    │   ├── 2. 读取 shader.json → 提取 uniforms schema
    │   ├── 3. 预解析 frag.glsl（LYGIA #include 内联）
    │   ├── 4. GLSL 转译（#version 330 → WebGL 2 ES）
    │   ├── 5. 启动 HTTP 预览服务（Node.js 原生 http）
    │   └── 6. 写入 state.json + progress.jsonl
    │
    └── stdout: { "url": "...", "asset": "...", "port": ..., "pid": ... }
```

**Harness 2.0 符合性**：

| 原则 | 实现 |
|------|------|
| 编排/执行分离 | `bin/macode` 路由 → `bin/shader-preview.mjs` 纯执行 |
| 状态外化 | `.agent/tmp/shader-preview-{asset}/state.json` |
| 文本流真相源 | Agent 读取 stdout JSON，人类用浏览器看可视化 |
| 引擎无关 | 不依赖 Manim/MC/Vite，纯浏览器 WebGL 2 |

---

## 3. CLI 接口

```bash
macode shader preview <asset_id> [--port <n>] [--open] [--watch] [--fps <n>]
macode shader preview-stop <asset_id>
```

**stdout JSON**：
```json
{
  "asset": "lygia_circle_heatmap",
  "url": "http://localhost:8765/preview",
  "api": "http://localhost:8765/api/asset",
  "port": 8765,
  "pid": 12345,
  "stateFile": ".agent/tmp/shader-preview-lygia_circle_heatmap/state.json"
}
```

---

## 4. HTTP 服务端点

| 端点 | 说明 | 消费者 |
|------|------|--------|
| `GET /preview` | 完整预览页面（WebGL + 控制面板） | 人类浏览器 |
| `GET /api/asset` | JSON：GLSL 源码 + uniforms schema | Agent / 外部工具 |
| `GET /api/frame?time=1.5` | 最接近该时间的预渲染 PNG | 对比验证 |
| `GET /api/registry` | 完整 `_registry.json` | 素材发现 |

---

## 5. GLSL 转译（桌面 → WebGL 2）

| 桌面 GLSL | WebGL 2 GLSL | 说明 |
|-----------|-------------|------|
| `#version 330` | `#version 300 es` | 版本声明 |
| `texture2D()` | `texture()` | WebGL 2 统一命名 |
| `textureCube()` | `texture()` | 同上 |
| 无精度修饰 | `precision highp float;` | ES 必须显式指定 |

LYGIA `#include` 在**服务端预解析**后传给浏览器，浏览器不再处理文件系统 include。

---

## 6. 浏览器端 UI

**自动生成控制面板**（基于 `shader.json` 的 `uniforms`）：

- `float` + `animation.enabled` → 时间轴 scrub slider
- `vec2`（如 `resolution`）→ 只读显示
- 其他类型 → 根据 schema 生成对应 input

**交互功能**：
- **Scrub**：拖动时间轴 → 更新 `u_time` → 重新渲染
- **Play/Pause**：`requestAnimationFrame` 循环驱动
- **Export PNG**：`gl.readPixels()` → Canvas 2D → `canvas.toDataURL()`
- **对比模式**：WebGL 实时输出 vs 预渲染 PNG 并排显示

---

## 7. 状态外化

```json
// .agent/tmp/shader-preview-{asset}/state.json
{
  "taskId": "shader-preview-lygia_circle_heatmap",
  "asset": "lygia_circle_heatmap",
  "port": 8765,
  "pid": 12345,
  "status": "running",
  "url": "http://localhost:8765/preview",
  "startedAt": "...",
  "lastUsedAt": "..."
}
```

进程管理复用 `macode-run` + `server-guardian.mjs`（TTL 自动回收）。

---

## 8. 与现有基础设施的复用

| 已有组件 | 复用方式 |
|---------|---------|
| `server-guardian.mjs` | 新增 `shader-preview` 类型扫描，TTL 自动回收 |
| `macode-run` | 统一进程生命周期 + 超时 + 信号转发 |
| `dashboard-server.mjs` | 读取 `shader-preview-*/state.json` 显示活跃预览 |
| `lygia_resolver.py` | Node.js 中移植简化版，或子进程调用 Python 预解析 |

---

## 9. 工作量估计

| 优先级 | 任务 | 预计行数 |
|--------|------|---------|
| P0 | GLSL 预解析 + 转译 | ~120 |
| P0 | HTTP server + 状态管理 | ~80 |
| P0 | 浏览器端 WebGL renderer | ~150 |
| P1 | UI：时间轴 + uniform 面板 | ~100 |
| P1 | macode CLI 路由 | ~15 |
| P1 | guardian 集成 | ~20 |
| P2 | 预渲染帧对比模式 | ~50 |
| P2 | 导出 PNG | ~30 |

**核心功能总计**：~565 行，1 天内可完成。

---

## 10. 为什么现在不做

| 理由 | 当前状态 |
|------|---------|
| 素材量仅 7 个，变化频率极低 | 5 个 LYGIA 标准库 + 2 个 builtin |
| 已有替代路径足够 | `shader-render.py` PNG + `macode dev` HMR |
| 项目最大短板是测试覆盖（2/10） | Phase 5 优先级更高 |
| 无自定义 shader（非 LYGIA）需求 | 当前全部为标准化素材 |

**触发条件**（满足任一即启动）：
1. `_registry.json` assets 数量 > 15
2. 出现自定义 GLSL（非 LYGIA）需求
3. Agent 迭代 shader 的频次显著上升（>3 次/天）
