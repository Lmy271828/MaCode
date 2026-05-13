# Host Agent Skill 规划 — MaCode Multi-Agent Coordinator

> **状态**: 设计储备（Design Reserve）  
> **目标**: 为 Kimi / Claude Code / Cursor 等 Host Agent 提供一套可复用的 MaCode 工作流 Skill  
> **范围**: 单 Agent 场景编写 + Multi-Agent 任务协调

---

## 1. Skill 定位

**不是** MaCode 的替代实现，而是 Host Agent 的"工作记忆扩展"。

Host Agent 在 MaCode 中的角色是**使用者 Agent**（per SOURCEMAP 权限模型）：
- ✅ 读写 `scenes/` 下的场景源码
- ✅ 调用 `bin/macode`、`pipeline/render.sh` 等 CLI
- ✅ 读取 `.agent/check_reports/`、`state.json`、`progress.jsonl`
- ❌ 不修改 `engines/`、`SOURCEMAP.md`、`.git/config`

---

## 2. Skill 目录结构（建议）

```
skills/macode-host-agent/
├── SKILL.md              # 主文档：工作流、CLI 速查、安全规则
├── workflows/
│   ├── single-scene.md   # 单场景完整工作流（manifest → render → check → fix → commit）
│   ├── multi-agent.md    # Multi-Agent 协调工作流（claim → render → 监控 → 冲突处理）
│   └── self-correction.md # Check report 解读 + 自动修复决策树
├── prompts/
│   ├── system-prompt.md  # 系统提示模板（注入到 Agent 上下文）
│   └── check-diagnosis.md # Check report → 修复建议的 prompt 模板
├── reference/
│   ├── cli-cheatsheet.md # macode / render / check / composite 命令速查
│   ├── exit-codes.md     # 所有 CLI 退出码及含义
│   └── manifest-schema.md # manifest.json 完整字段说明
└── examples/
    ├── manim-scene.md    # Manim 场景编写示例
    ├── mc-scene.md       # Motion Canvas 场景编写示例
    └── composite-scene.md # Composite 场景编写示例
```

---

## 3. 核心内容规划

### 3.1 SYSTEM PROMPT 设计（system-prompt.md）

**注入时机**: Agent 进入 MaCode 项目时自动加载（通过 `.kimi/skills/` 或 `.claude/skills/` 机制）。

**内容结构**:

```markdown
# MaCode Host Agent 系统提示

你是 MaCode Harness 的使用者 Agent。你的职责是编写数学动画场景源码并通过 MaCode CLI 渲染。

## 项目结构速查
- `scenes/{name}/` —— 你的工作区（manifest.json + scene.py/scene.tsx）
- `engines/{manim,motion_canvas}/` —— 引擎适配层（只读，禁止修改）
- `.agent/tmp/{scene}/` —— 渲染输出（frames/ + final.mp4）
- `.agent/check_reports/` —— 质量检查报告
- `project.yaml` —— 全局配置

## 你必须遵守的规则
1. 禁止修改 `engines/`、`bin/`、`pipeline/` 下的任何文件
2. 禁止直接编辑 `.git/config` 或执行 `git push --force`
3. 渲染前必须先运行 `macode check`，修复 issue 后再渲染
4. 修改 source 后必须 `git add scenes/ && git commit -m "..."`
5. 不要猜测引擎 API，使用 `macode inspect --grep <keyword>` 查询

## 标准工作流
1. 读取 `scenes/{name}/manifest.json` 理解需求
2. 使用 `macode inspect --grep` 查询所需 API
3. 编写 `scenes/{name}/scene.py`（或 .tsx）
4. `macode check scenes/{name}/` —— 静态检查
5. 读取 `.agent/check_reports/{name}_static.json`，修复 issue
6. `macode render scenes/{name}/` —— 渲染
7. 读取 `.agent/check_reports/{name}_frames.json`，修复 issue
8. `git add scenes/{name}/ && git commit -m "agent: render {name}"`

## 本机并行（PRD 不做 Multi-Agent）

- 无 `MACODE_AGENT_ID`、无 scene claim、`macode render` 无 exit 4/5
- 多场并行：`render-all` / composite + `max_concurrent_scenes`
- 可选 `curl http://localhost:<port>/api/state`；`cleanup-stale.py` 修复 stalled state
```

### 3.2 SELF-CORRECTION WORKFLOW（self-correction.md）

**目标**: 让 Agent 能够自动读取 check report，理解 issue，决定修复策略，执行修复，重新验证。

**Schema v2 Fix 消费协议**:

Check report 中的每个 issue 现在包含 `fixable`, `fix_confidence`, `fix.strategy/action/params`：

```json
{
  "type": "duration_mismatch",
  "message": "声明时长 3.00s 与计算动画时间 9.30s 偏差超过 0.5s",
  "fixable": true,
  "fix_confidence": 0.9,
  "fix": {
    "strategy": "adjust_wait",
    "action": "modify_wait_duration",
    "params": {"target_duration": 3.0}
  }
}
```

**Agent 决策树**:

```
读取 check report
  → 所有 issue fixable=true 且 fix_confidence > 0.8?
      → YES: 按 fix.params 自动修改 source
      → NO:  请求人类确认（创建 .agent/signals/review_needed）
  → 修改后重新运行 check
  → 通过后重新渲染
```

**Prompt 模板（check-diagnosis.md）**:

```markdown
你收到了以下 check report issue。请决定是否自动修复：

Issue: {type}
Message: {message}
Fix strategy: {strategy}
Fix action: {action}
Fix params: {params}
Confidence: {fix_confidence}

决策规则：
- 如果 fix_confidence >= 0.8 且 strategy 是 "adjust_wait" / "increase_buff" / "adjust_position" / "adjust_font" / "adjust_scale" → 自动修复
- 如果 fix_confidence < 0.8 或 strategy 是 "complex_refactor" → 请求人类确认
- 如果涉及删除内容 → 请求人类确认

请输出：
1. 决策（auto_fix / human_confirm / ignore）
2. 具体的代码修改方案（行号 + 修改内容）
3. 修改后的验证命令
```

### 3.3 ~~MULTI-AGENT COORDINATION~~（已弃用）

PRD 已移除 Harness 内 Multi-Agent claim/队列。外层若需多进程，请自行用 shell `flock` 或任务调度器；场内并行用 `render-all` / composite。

**历史策略（仅供参考，代码路径已删）**：

```
Phase 1: 扫描 scenes/
Phase 2: （已删）claim_scene
Phase 3: 标准工作流 check → render
Phase 4: cleanup-stale / dashboard 观测
```

**冲突解决（仍适用）**：

| 冲突类型 | 解决策略 |
|----------|----------|
| Git commit 冲突 | `git pull --rebase` 后重试 |
| Check report 竞态 | flock 保护；重跑 check |

---

## 4. 集成方式（建议）

### 4.1 Kimi CLI

将 `skills/macode-host-agent/` 放到项目根目录或用户目录：

```bash
# 项目级 skill（仅当前项目生效）
mkdir -p .kimi/skills/macode-host-agent
cp docs/host-agent-skill-plan.md .kimi/skills/macode-host-agent/SKILL.md

# 用户级 skill（全局生效）
mkdir -p ~/.kimi/skills/macode-host-agent
cp docs/host-agent-skill-plan.md ~/.kimi/skills/macode-host-agent/SKILL.md
```

### 4.2 Claude Code

通过 `.claude/settings.local.json` 注入系统提示：

```json
{
  "systemPrompt": "[读取 docs/host-agent-skill-plan.md 的 system-prompt.md 内容]"
}
```

### 4.3 Cursor

通过 `.cursorrules` 文件注入：

```markdown
# MaCode 工作流规则
[system-prompt.md 的精简版]
```

---

## 5. 未解决问题 / 待决策

1. **Skill 版本管理**: MaCode 版本升级时，如何自动更新 Host Agent 的 skill？
   - 选项 A: 在 `bin/setup.sh` 中自动同步 skill 到 `.kimi/skills/`
   - 选项 B: 通过 `macode skill sync` CLI 手动同步
   - 选项 C: 不托管 skill，只在 AGENTS.md 中提供链接

2. **Prompt 注入粒度**: 系统提示应该包含多少 SOURCEMAP 内容？
   - 选项 A: 完整 SOURCEMAP（上下文爆炸风险）
   - 选项 B: 只注入 P0 API + BLACKLIST 模块名（当前推荐）
   - 选项 C: 不注入，让 Agent 按需调用 `macode inspect`

3. **Multi-Agent 通信协议**: 除了文件系统 claim，是否需要 Agent 间直接通信？
   - 选项 A: 纯文件系统（当前实现，UNIX 哲学）
   - 选项 B: Dashboard WebSocket（Agent → Dashboard → Agent）
   - 选项 C: 共享 SQLite / JSON 数据库

---

## 6. 验收标准（Skill Ready）

- [ ] Host Agent 能在零人类干预下完成单场景的 write → check → fix → render → commit
- [ ] Host Agent 能正确解读 Schema v2 的 fix 块并执行修改
- [ ] 3 个 Host Agent 同时运行，各自处理不同 scene，无冲突、无重复工作
- [ ] Host Agent 能识别并处理 `exit 4`（claimed）和 `exit 5`（queued）
- [ ] Skill 文档随 MaCode 版本更新自动同步
