# MaCode — UNIX 原生的数学动画制作 Harness

> **Ma**th + **Code**. Make it work, then make it right, then make it fast.

MaCode 是一个 Bash-First 的数学动画 Agent 工作流系统。它不封装高级 API，而是提供一个**透明的、可被 `ls / cat / grep` 完全理解的文件系统环境**，让 Agent 通过 Bash 命令探索、组合、修复数学动画的每一个环节。

## 设计哲学

- **引擎无关**：场景定义与引擎实现解耦。ManimCE → Motion Canvas 迁移只需修改 `manifest.json`。
- **管道透明**：渲染、剪辑、压缩的每一步都是可见的文件转换。
- **状态可逆**：所有 Agent 行为通过 Git 流控制实现原子化与可回滚。
- **音频统一**：所有音频处理由 `ffmpeg` 完成，不引入额外依赖。

## 快速开始

```bash
# 克隆后首次：初始化权限、目录、依赖检查、配置 API
bash bin/setup.sh

# 启动 Coding Agent（配置检查 + 系统提示 + 安全 shell）
bin/agent

# 或直接进入 Agent 环境
bin/agent-shell

# 查看项目状态
macode status

# 查看引擎可用 API
macode inspect --level P0

# 渲染单个场景
pipeline/render.sh scenes/01_test/

# 批量渲染所有场景
bin/render-all.sh

# 并行渲染（最多 4 个场景同时）
bin/render-all.sh --parallel 4
```

## 目录结构

```text
macode/
├── .macode/                # Agent 运行时配置（API Key、模型）
├── .agent/                 # Agent 工作区（临时帧、缓存、日志）
│   ├── tmp/{scene}/        # 帧序列、渲染输出
│   ├── cache/              # 帧级缓存（按内容哈希寻址）
│   └── log/                # 全局渲染日志
├── engines/                # 渲染引擎适配层
│   ├── manim/              #   ManimCE（Python）
│   │   ├── SOURCEMAP.md    #     源码地图（Agent 的 API 导航）
│   │   ├── scripts/        #     render.sh, inspect.sh, validate_sourcemap.sh
│   │   └── src/            #     适配层模板与工具
│   └── motion_canvas/      #   Motion Canvas（TypeScript）
│       ├── SOURCEMAP.md
│       ├── scripts/
│       └── src/templates/
├── scenes/                 # 用户场景（Agent 主要工作区）
│   ├── 00_title/           #   序号前缀保证管道拼接顺序
│   │   ├── manifest.json   #     场景契约（引擎类型、时长、依赖）
│   │   └── scene.py        #     引擎实现
│   └── ...
├── pipeline/               # 后处理管道（纯 bash，ffmpeg 驱动）
│   ├── render.sh           #   场景渲染入口（含缓存 + api-gate 审查）
│   ├── concat.sh           #   帧序列 → MP4
│   ├── add_audio.sh        #   音轨合成
│   ├── fade.sh             #   淡入淡出
│   ├── compress.sh         #   输出压缩
│   ├── preview.sh          #   快速预览
│   ├── smart-cut.sh        #   静默段自动剪辑
│   ├── thumbnail.sh        #   关键帧提取
│   └── cache.sh            #   帧级缓存
├── bin/                    # 全局工具脚本
│   ├── setup.sh             #   项目初始化（权限修复 + 依赖检查）
│   ├── macode               #   主入口 CLI
│   ├── agent-shell          #   Agent 默认 shell 入口
│   ├── agent-run.sh         #   Git 原子操作包装器
│   ├── safety-gate.sh       #   命令白名单拦截器
│   ├── api-gate.py          #   SOURCEMAP 导入审查门
│   ├── render-all.sh        #   批量渲染（支持并行）
│   └── discover             #   交互式项目结构探索
├── project.yaml            # 全局配置（引擎、分辨率、安全策略）
├── SOURCEMAP_SPEC.md       # SOURCEMAP 规范
└── progress.md             # 开发路线图
```

## 核心概念

### 三层解耦

```
Layer 3: Scene 描述 (manifest.json)  ← 唯一不变层，引擎无关
Layer 2: Engine 适配 (engines/*)     ← 可替换层
Layer 1: 基础设施 (bash, ffmpeg, git) ← 绝对稳定层
```

### SOURCEMAP 协议

每个引擎目录下有一份 `SOURCEMAP.md`，是 Agent 的**源码探索地图**：

- **WHITELIST**：安全的、值得阅读的 API 表面（P0/P1/P2 分级）
- **BLACKLIST**：陷阱路径（废弃 API、内部黑魔法、测试代码）
- **EXTENSION**：引擎支持但 MaCode 尚未接入的能力

Agent 通过 `macode inspect --grep <keyword>` 查询，渲染前 `api-gate.py` 自动拦截 BLACKLIST 导入。

### 场景契约 (manifest.json)

```json
{
  "engine": "manim",
  "duration": 10,
  "fps": 30,
  "resolution": [1920, 1080],
  "assets": ["assets/formula.tex"],
  "dependencies": ["scenes/00_title/manifest.json"]
}
```

## 配置

### Agent API 配置（`.macode/settings.json`）

```json
{
  "provider": "kimi-for-coding",
  "env": {
    "ANTHROPIC_API_KEY": "sk-...",
    "ANTHROPIC_BASE_URL": "https://api.kimi.com/coding"
  },
  "model": "kimi-for-coding"
}
```

`agent-shell` 启动时自动加载并导出环境变量。

### 项目配置（`project.yaml`）

```yaml
defaults:
  engine: manim
  resolution: [1920, 1080]
  fps: 30
```

## 工作流示例

```bash
# 1. 进入 Agent 环境
bin/agent-shell

# 2. 查看 ManimCE 引擎提供了什么
engines/manim/scripts/inspect.sh

# 3. 搜索特定 API
macode inspect --grep "NumberLine\|Axes"

# 4. 编写场景（scene.py + manifest.json）到 scenes/02_fourier/

# 5. 渲染（自动通过 api-gate 审查 + 缓存检查）
pipeline/render.sh scenes/02_fourier/

# 6. 如果渲染失败，查看日志中的 SOURCEMAP 诊断
tail -50 .agent/log/$(ls -t .agent/log/ | head -1)

# 7. 预览
pipeline/preview.sh .agent/tmp/02_fourier/final.mp4

# 8. 多场景拼接 + 音频合成
pipeline/concat.sh scenes/*/output/final.mp4 output/lecture.mp4
pipeline/add_audio.sh output/lecture.mp4 assets/bgm.mp3 output/final.mp4
```

## 引擎

| 引擎 | 语言 | 状态 | 适用场景 |
|------|------|------|----------|
| ManimCE | Python | **默认** | 3Blue1Brown 风格、LaTeX 公式、几何动画 |
| Motion Canvas | TypeScript | 备选 | 热重载迭代、Web 原生导出 |

迁移引擎只需修改 `manifest.json` 的 `engine` 字段并重写场景文件，管道脚本无需改动。

## 开发阶段

| Phase | 内容 | 状态 |
|-------|------|------|
| 0 | 骨架 — 单场景渲染 | ✅ |
| 1 | 管道 — 多场景拼接 + ffmpeg 音频 | ✅ |
| 2 | 引擎抽象 — Motion Canvas 适配 | ✅ |
| 3 | Agent Harness — Git 流控制 + 安全门 | ✅ |
| 4 | 优化 — 缓存 + 并行 + 智能剪辑 | ✅ |

详见 [`progress.md`](progress.md)。

## 许可

MIT
