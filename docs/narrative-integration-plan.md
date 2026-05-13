# P0-2 NarrativeScene 集成规划

> **状态**：NarrativeScene 基类与 3 个核心叙事模板已实施完毕并通过测试。
> **日期**：2026-05-12

---

## 1. 已交付资产（P0-2 实施成果）

### 1.1 引擎无关叙事模板 JSON

| 模板 | 路径（双引擎同步） | 叙事模式 |
|------|-------------------|---------|
| `definition_reveal.json` | `engines/manimgl/src/templates/narratives/` + `engines/manim/src/templates/narratives/` | Specific → General 变体：陈述→视觉→注释→举例 |
| `build_up_payoff.json` | 同上 | Build Up → Payoff：搭建→组合→惊艳结果→反思 |
| `wrong_to_right.json` | 同上 | Wrong → Less Wrong → Right：误解→失败→修正→正确 |

模板字段：
- `stages[].id / zone / type / duration_hint / must_be_first / requires`
- `rules.primary_zone_first_visual_within / max_text_chars_per_scene / text_to_visual_ratio`
- `meta.engine = "agnostic"`

### 1.2 NarrativeScene 编排基类

| 引擎 | 文件 | 关键差异 |
|------|------|---------|
| ManimGL | `engines/manimgl/src/components/narrative_scene.py` | `CREATION_ANIM = ShowCreation` |
| ManimCE | `engines/manim/src/components/narrative_scene.py` | `CREATION_ANIM = Create` |

基类功能：
- `setup()` 加载 `NARRATIVE_PROFILE` JSON
- `stage(stage_id, *mobjects, run_time=None)` — 验证顺序 → 自动 place 到模板指定 zone → 按 type 选动画 → 播放 → 记录时间
- `play_stage()` — 低层扩展钩子
- `narrative_summary()` — 诊断快照
- `primary_zone_first_visual_within` 在动画**播放前**检查（“出现” = 被调用）

### 1.3 纯验证工具

`utils/narrative_validator.py`（双引擎同步）：
- `get_stage_def()` / `validate_stage_order()` / `validate_primary_zone_visual_timing()`
- 异常：`StageOrderError`, `PrimaryZoneVisualTimeoutError`, `NarrativeProfileError`, `StageNotFoundError`

### 1.4 测试覆盖

- **单元测试**：`tests/unit/test_narrative_scene.py` — **30 个测试**全部通过
  - JSON schema（存在性、字段完备、stage 序列、engine=agnostic）
  - `get_stage_def`
  - `validate_stage_order`（must_be_first、requires、多依赖）
  - `validate_primary_zone_visual_timing`（超时、非 visual、非 primary、第二个 visual、零 timeout）
- **冒烟测试**：`scenes/10_narrative_test/` — 端到端渲染通过 `macode render`
- **零回归**：原有 152 个单元测试 + 11 个冒烟测试全部通过

---

## 2. Skill 集成路径规划

### 2.1 manim_skill 集成（`./manim_skill/skills/manim-composer/`）

**现状**：`manim-composer` 是 3b1b 风格叙事规划 Skill，已有：
- `SKILL.md`：把模糊想法转化为 `scenes.md` 计划
- `references/narrative-patterns.md`：6 种叙事模式（文字描述）
- `references/visual-techniques.md`：构图模板、空间语义、色彩方案

**集成点**：

```
manim-composer/SKILL.md 生成 scenes.md
        ↓
MaCode content_manifest.json（内容契约）
        ↓
engines/*/src/templates/narratives/*.json（已落地为 JSON 模板）
        ↓
NarrativeScene 基类消费（编排层）
```

具体映射：

| manim-composer 输出 | MaCode 消费方式 |
|--------------------|----------------|
| `scenes.md` 中的 "Pattern: Mystery → Investigation → Resolution" | 未来扩展为 `mystery_investigation.json` 模板 |
| `scenes.md` 中的 "Pattern: Build Up → Payoff" | 直接映射到 `build_up_payoff.json` |
| `scenes.md` 中的 "Pattern: Wrong → Right" | 直接映射到 `wrong_to_right.json` |
| `scenes.md` 中的 stage 列表（如 "1. Hook 2. Setup 3. Payoff"） | 映射到 JSON 的 `stages[]`，每个 stage 绑定 `zone` + `type` |
| `visual-techniques.md` 的 "Golden Layout" | 已映射为 `lecture_3zones.json`（P0-1） |
| `visual-techniques.md` 的 Timing Guidelines | 映射为 `duration_hint` + `rules` |

**建议**：在 `manim-composer/SKILL.md` 的 "输出格式" 章节中增加一段：

> 若目标项目使用 MaCode Harness，生成的 scenes.md 应额外包含 `narrative_profile` 字段（如 `definition_reveal`）和 `layout_profile` 字段（如 `lecture_3zones`）。Host Agent 可直接将这些字段写入 `manifest.json`，由 MaCode 的 `NarrativeScene` 自动加载。

**不修改 `manim_skill` 目录**：按需求约束，保持该 skill 只读，只在 MaCode 侧消费其产出。

### 2.2 skills/motion-canvas/ 集成（`./skills/motion-canvas/` / `./skills/motion-canvas-agent/`）

**现状**：Motion Canvas 已有声明式 Layout 系统（Flexbox、Grid、Anchor），不需要 ZoneScene 式的命令式基类。

**集成策略 —— 统一契约层、分轨实现层**：

```
content_manifest.json（引擎无关）
    ├── narrative_profile: "definition_reveal"
    ├── layout_profile: "lecture_3zones"
    └── stages: [...]

Manim 实现路径（P0-2 已完成）：
    NarrativeScene (Python) → place() + play()

Motion Canvas 实现路径（未来 P1-x）：
    JSX generator (TypeScript/Node) → 读取 narrative JSON → 生成含 Layout props 的 TSX
```

MC 端的等效映射示例：

```tsx
// 由 narrative_profile="definition_reveal" + layout_profile="lecture_3zones" 自动生成
export default makeScene2D(function* (view) {
  // statement → title zone
  const title = createRef<Txt>();
  view.add(<Txt ref={title} text="极限的定义" layout={{position: 'top'}} />);
  yield* title().opacity(1, 2);

  // visual → main_visual zone (primary)
  const axes = createRef<Axes>();
  view.add(<Axes ref={axes} layout={{position: 'center', size: [70%, 60%]}} />);
  yield* axes().opacity(1, 4);
  // ...
});
```

**关键原则**：MC 端不引入 `NarrativeScene` 基类，而是：
1. 保留同样的 `content_manifest.json` 契约
2. 由编排层（`pipeline/render-scene.py` → MC 时调用 `engines/motion_canvas/scripts/render.mjs`）在渲染前读取 `narrative_profile`（实现时需落在 manifest 解析或预检步骤）
3. 调用一个轻量的 `narrative-to-jsx.mjs` 生成器，将 JSON 模板转为 `Layout` props 和 `yield*` 时间轴
4. 最终输出与 Manim 端帧序列一致的 PNG 文件

### 2.3 引擎无关性保持

| 层级 | 文件/机制 | 引擎无关？ | 说明 |
|------|----------|-----------|------|
| 契约层 | `templates/narratives/*.json` | ✅ 完全无关 | 纯内容描述，无引擎关键字 |
| 编排层 | `NarrativeScene` (Python) | ❌ 引擎特定 | ManimGL/ManimCE 各一版，差异仅 `Create` vs `ShowCreation` |
| 执行层 | `ffmpeg` / `render.sh` | ✅ 通用 | 所有引擎输出统一为 PNG → MP4 |
| MC 生成层 | `narrative-to-jsx.mjs`（规划） | ❌ 引擎特定 | 未来新增，只服务 MC |

**保持策略**：
- 任何新增叙事模板 JSON 必须同时复制到 `manimgl/` 和 `manim/` 目录（当前已同步）
- JSON 中禁止出现引擎特定字段（如 `creation_anim`）
- 引擎差异通过基类属性 `CREATION_ANIM` / `WRITE_ANIM` 吸收

---

## 3. Skill 化建议

### 选项 A：集成到现有 `macode-host-agent/SKILL.md`

在 `.agents/skills/macode-host-agent/SKILL.md` 中新增一节 **"叙事模式工作流"**：

```markdown
## 叙事模式工作流

当用户要求 "用 definition_reveal 模式讲解 X" 时：

1. 读取 `engines/*/templates/narratives/{profile}.json` 确认 stages
2. 编写 scene.py，继承 `NarrativeScene`
3. 按 `stages[].id` 顺序调用 `self.stage()`
4. 运行 `macode render` 验证

禁止：
- 跳过 requires 依赖
- 在 primary zone 的 visual 超时后放置视觉对象
```

**优点**：与现有 Host Agent 工作流无缝融合，无额外目录。
**缺点**：SKILL.md 会变长。

### 选项 B：新建 `.agents/skills/narrative-compiler/SKILL.md`

独立的 narrative-compiler skill，职责：
- 将自然语言描述编译为 `narrative_profile` + `stages` 清单
- 提供 narrative 模板选择决策树（根据内容类型推荐 pattern）
- 维护叙事模板版本与兼容性矩阵

**优点**：职责单一，未来可独立演进（如增加 AI 辅助 pacing 计算）。
**缺点**：Host Agent 需要多读取一个 skill 文件。

### 推荐：选项 A（轻度集成）

当前 3 个模板 + NarrativeScene 的复杂度尚不足以支撑独立 skill。建议：

1. 在 `macode-host-agent/SKILL.md` 新增 "NarrativeScene 快速参考" 附录
2. 保留新建独立 skill 的入口（未来模板数量 > 6 或引入自动 pacing 时拆分）
3. 在 `macode-host-agent/references/` 下新增 `narrative-profiles.md` 速查表

---

## 4. 后续扩展 TODO

| 优先级 | 任务 | 触发条件 |
|--------|------|---------|
| P1 | 补充剩余 3 个叙事模板（`mystery_investigation.json`, `two_perspectives.json`, `history_narrative.json`） | 有实际场景需要时 |
| P1 | MC 端 `narrative-to-jsx.mjs` 生成器 | MC 场景需要 narrative 支持时 |
| P2 | `text_to_visual_ratio` 运行时检查（目前仅 JSON 声明） | 静态检查工具扩展时 |
| P2 | `max_text_chars_per_scene` 运行时检查 | 同上 |
| P2 | 叙事模板 JSON Schema 正式化（`engines/*/templates/narratives/schema.json`） | 模板数量 > 5 时 |
| P3 | 与 `manim-composer` 的 scenes.md → manifest.json 自动转换脚本 | manim-composer 活跃使用时 |

---

## 5. 验收状态

- [x] `definition_reveal.json`、`build_up_payoff.json`、`wrong_to_right.json` 模板存在且通过 JSON schema 检查
- [x] `NarrativeScene` 基类可工作，`stage()` 自动处理 zone + 动画 + 时序依赖
- [x] `scenes/10_narrative_test/` 可通过 `macode render` 端到端渲染
- [x] 单元测试 ≥ 10 个新增（实际 30 个），全部通过（182/182）
- [x] 冒烟测试 11/11 通过，零回归
- [x] 集成规划文档输出到 `docs/narrative-integration-plan.md`
