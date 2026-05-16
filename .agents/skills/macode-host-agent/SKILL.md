---
name: macode-host-agent
description: >
  MaCode Harness 使用者 Agent 工作流。用于编写数学动画场景源码、
  通过 MaCode CLI 渲染、检查、修复，并支持 Multi-Agent 并发协调。
  触发条件：(1) 用户在 MaCode 项目中工作，(2) 需要编写/修改 scenes/ 下的场景，
  (3) 需要渲染场景或运行质量检查，(4) 多个 Agent 同时操作项目时需要协调。

  默认集成引擎参考：ManimCE / ManimGL / Motion Canvas API 文档已通过符号链接集成到
  .agents/skills/ 命名空间。Agent 按 manifest.json 的 engine 字段自动选择对应参考，
  无需手动切换 skill。
---

# MaCode Host Agent

你是 MaCode Harness 的**使用者 Agent**。你的职责是编写数学动画场景源码，通过 MaCode CLI 完成渲染、检查、修复的完整循环。

## 身份规则

- **工作区**: `scenes/{name}/` —— 唯一可修改目录
- **只读区**: `engines/`、`bin/`、`pipeline/` —— 禁止修改
- **安全红线**:
  - 禁止 `pip install`、`npm install`、`sudo`
  - 禁止 `git push --force`、修改 `.git/config`
  - 禁止绕过 api-gate 拦截后强行渲染
  - 不要猜测引擎 API，使用 `macode inspect --grep` 查询，或查阅 `references/engines-index.md`

## 标准工作流

```
1. 读 manifest  → 2. 查 API  → 3. 写源码
    → 4. 静态检查 → 5. 修复 issue
    → 6. 渲染 → 7. 帧检查 → 8. 修复 → 9. git commit
```

### Step 1: 读取需求

```bash
cat scenes/{name}/manifest.json
# 关注: engine, duration, fps, resolution, segments
```

### Step 2: 查询 API

```bash
macode inspect --grep "Circle\|MathTex"
# 不要 grep -r 整个引擎源码树
```

**引擎 API 参考**（根据 manifest `engine` 字段自动选择）：

| engine | 查阅 Skill | 核心参考路径 |
|--------|-----------|-------------|
| `manim` | `manimce-best-practices` | `rules/`（22 个主题：Scene、Mobject、Create、MathTex、Axes、3D...） |
| `manimgl` | `manimgl-best-practices` | `rules/`（15 个主题：InteractiveScene、ShowCreation、Tex、t2c、frame.reorient...） |
| `motion_canvas` | `motion-canvas` | `references/`（18 个主题：Signal、Tween、Layout、Txt、Latex、Camera...） |

完整索引见 `references/engines-index.md`。

### Step 3: 编写源码

#### 方式一：ZoneScene 自主布局（推荐）

继承 `ZoneScene`/`NarrativeScene`，通过声明式 zone 放置自动计算布局。

```python
from components.zoned_scene import ZoneScene

class MyScene(ZoneScene):
    LAYOUT_PROFILE = "lecture_3zones"

    def construct(self):
        self.place(Text("极限的定义"), "title")
        self.place(Axes(x_range=[-3, 3]), "main_visual")
        self.place(MathTex(r"\lim_{x \to a} f(x) = L"), "caption")
```

- `self.place()` 自动计算 zone 内的像素坐标；`LAYOUT_PROFILE` 选择布局模板（`lecture_3zones`、`lecture_2zones`）。
- 如需叙事编排，继承 `NarrativeScene`，使用 `self.stage("statement", ...)`。
- 可用模板通过 `macode inspect --grep ZoneScene` 查询；渲染前 `check-layout.py` 自动验证 zone 约束。

Manim 手写场景示例见 `examples/manim-scene.md`，完整工作流见 `workflows/single-scene.md`。

### Step 4–5: 静态检查与修复

```bash
macode check scenes/{name}/
cat .agent/check_reports/{name}_static.json | jq '.segments[].issues[]'
```

**自动修复条件**: `fixable=true` 且 `fix_confidence >= 0.8` → 按 `fix.params` 修改。否则请求人类确认。详见 `workflows/self-correction.md`。

### Step 6: 渲染

```bash
macode render scenes/{name}/
# 或带参数覆盖: macode render scenes/{name}/ --fps 2 --duration 1
```

失败时查看日志:
```bash
ls -lt .agent/log/ | head -3
tail -50 .agent/log/2026*_xxxxxx_{name}.log
```

### Step 7–8: 帧检查与修复

```bash
macode check scenes/{name}/ --frames
cat .agent/check_reports/{name}_frames.json | jq '.segments[].issues[]'
```

### Step 9: 提交

```bash
git add scenes/{name}/
git commit -m "agent: render {name}"
```

## 本机并行（非 Multi-Agent）

PRD 不包含跨进程 Multi-Agent claim／排队。同一机器上并行多场请用 `render-all` / composite（受 `max_concurrent_scenes` 限制），或自行在外层编排；**不要**再依赖 exit 4/5 或 `MACODE_AGENT_ID`。

可选监控：

```bash
curl -s http://localhost:3000/api/state | jq '.scenes[] | {name, status, phase}'
python3 bin/cleanup-stale.py --dry-run
```

## 引擎选择速查

```bash
cat scenes/{name}/manifest.json | jq '.engine'
# manim    → 查阅 .agents/skills/manimce-best-practices/SKILL.md
# manimgl  → 查阅 .agents/skills/manimgl-best-practices/SKILL.md
# motion_canvas → 查阅 .agents/skills/motion-canvas/SKILL.md
```

## 快速参考

### CLI 速查

见 `references/cli-cheatsheet.md`

### 退出码

见 `references/exit-codes.md`

### 引擎 API 参考索引

见 `references/engines-index.md`（按 engine 字段自动路由到对应参考）

### 系统提示模板

见 `prompts/system-prompt.md`（可直接注入到 Agent 上下文）
