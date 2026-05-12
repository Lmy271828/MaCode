# MaCode Security Harness 2.0

## 设计原则

1. **没有上帝脚本**：每个安全工具只检查一类威胁，通过 `security-run.sh` 薄分发器组合
2. **拒绝优于检测**：原语隔离层让 Agent **物理上写不了**危险文件，而非依赖事后检测
3. **只读检查器**：所有安全脚本都是只读的，不修改任何文件
4. **Exit code 契约**：0=通过，1=违规，2=参数错误（与 api-gate 兼容）

---

## 四层架构

```
Layer 0: Prompt Guardrails      (软性约束，君子协定)
  └── .agents/security/prompt-policy.yml
      → .claude/settings.local.json
      → .cursorrules
      → .aider.conf.yml

Layer 1: Runtime Enforcement    (硬性强制，渲染前拦截)
  └── bin/security-run.sh       (薄分发器，~40 行)
      ├── bin/api-gate.py       (导入/API 检查 — 已有)
      ├── bin/sandbox-check.py  (危险 Python 调用)
      ├── bin/primitive-gate.py (原语写入检测)
      └── bin/fs-guard.py       (文件系统边界)

Layer 2: Commit Interception    (版本保护，提交前拦截)
  └── .githooks/pre-commit      (版本化模板，调用 security-run.sh --staged)
  └── .githooks/pre-push        (版本化模板，调用 security-run.sh --all)
  └── bin/install-hooks.sh      (安装脚本：复制模板到 .git/hooks/)

Layer 3: Infrastructure Isolation (根本解决，权限隔离)
  ├── engines/*/effect-registry/    (chmod 644 — Agent 只读)
  ├── engines/*/templates/          (chmod 644 — Agent 只读)
  ├── engines/*/src/                (chmod 644 — Agent 只读)
  ├── bin/                          (chmod 755 — Agent 只读)
  ├── pipeline/                     (chmod 755 — Agent 只读)
  └── assets/shaders/*/             (chmod 644 — Agent 只读)
```

---

## 工具职责（四问法验证）

| 工具 | Q1 决策/副作用 | Q2 失败范围 | Q3 并发 | Q4 跨任务信息 |
|------|---------------|------------|---------|--------------|
| api-gate.py | 纯决策（只读代码） | 仅当前 scene | 只读，可并行 | 不依赖其他任务 |
| sandbox-check.py | 纯决策（只读代码） | 仅当前 scene | 只读，可并行 | 不依赖其他任务 |
| primitive-gate.py | 纯决策（只读目录） | 仅当前 scene | 只读，可并行 | 不依赖其他任务 |
| fs-guard.py | 纯决策（只读目录） | 仅当前 scene | 只读，可并行 | 不依赖其他任务 |
| security-run.sh | 纯编排（调用子工具） | 当前 scene | 并行调度 | 汇总 exit code |

---

## 原语隔离矩阵

| 原语 | 隔离措施 | 替代方案 | 检测工具 |
|------|---------|---------|---------|
| GLSL | `assets/shaders/` 只读 | Effect Registry 声明引用 | primitive-gate.py |
| Raw LaTeX | SYNTAX_REDIRECTS 拦截 | `natural_math.py` API | sandbox-check.py |
| ffmpeg filtergraph | SYNTAX_REDIRECTS 拦截 | `ffmpeg_builder.py` API | sandbox-check.py |
| JSON/TOML/YAML 引擎配置 | `engine.conf` / `project.yaml` 只读 | `macode` CLI 修改 | fs-guard.py |
| socket/http | SANDBOX_PATTERNS 拦截 | `macode-run` 统一 IPC | sandbox-check.py |
| subprocess/os.system | SANDBOX_PATTERNS 拦截 | `macode-run` 白名单执行 | sandbox-check.py |
| 文件越界写入 | `engines/`, `bin/`, `pipeline/` 只读 | 只允许 `scenes/` / `assets/` 写入 | fs-guard.py |

---

## Security Guardian Subagent

独立进程，可选部署：

```
.agents/skills/security-guardian/
├── SKILL.md                  # 角色定义
└── bin/security-guardian.py  # 文件系统监控守护进程
```

职责：
- 通过 `inotifywait` / `fswatch` 监控 `scenes/` 目录
- 检测到违规写入时立即发送 SIGUSR1 给 Host Agent
- 写审计日志到 `.agent/security/audit.log`

注意：Security Guardian 是**可选增强**，不是必需路径。Layer 1-3 已足够覆盖主要威胁。
