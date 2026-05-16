# SOURCEMAP 协议 —— Agent 的安全地图

`engines/{name}/sourcemap.json` 是黑白名单与安全元数据的 **唯一机器真源**。同目录下的 `SOURCEMAP.md` 是由 `bin/sourcemap-sync.py` **从 JSON 生成**的人类可读视图；若二者不一致，`sourcemap-sync.py --check` 会报错。

它不是给使用者 Agent 随意编辑的草稿，而是 **Harness 用来约束和引导 Agent 的协议**（人类维护者修改 JSON → 再生 MD）。

## 核心原则

- **使用者 Agent 只读** SOURCEMAP，通过 `macode inspect` 查询 API
- **开发者 Agent 读写** SOURCEMAP，负责维护引擎适配层
- Harness 在启动时将它注入 Agent 的**工作记忆**，在编码时用它做**审查门**，在出错时用它做**诊断地图**

## Agent 工作流中的 SOURCEMAP

```bash
# 1. 启动时自动加载（macode CLI / setup）
python3 bin/sourcemap-sync.py --all
# → 校验 engines/{engine}/sourcemap.json（jsonschema）
# → 写回同源 SOURCEMAP.md + .agent/context/{engine}_sourcemap.json 等副本

# 2. 编码前查询 API
macode inspect --grep "NumberLine\|Axes\|MathTex"
# → 查询 SOURCEMAP WHITELIST，确认 API 存在且安全

# 3. 渲染前自动审查（pipeline/render.sh 内置）
pipeline/render.sh scenes/02_demo/
# → api-gate.py 对照 engines/<engine>/sourcemap.json BLACKLIST（与 manifest.engine 对齐）
# → 若发现 "import manimlib" → 立即阻断，提示修复

# 4. 出错时定向诊断（engines/*/scripts/render.sh 内置）
# → 日志解析器扫描错误关键词
# → 匹配 BLACKLIST 条目 → "你踩了 DEPRECATED_GL，修复方案是 X"
```

## 自动化维护工具链

| 工具 | 职责 | 何时运行 |
|------|------|---------|
| `sourcemap-version-check.py` | 检测引擎版本漂移 | `setup.sh` 自动调用；`macode status` 显示 |
| `sourcemap-scan-api.py` | 扫描未覆盖的公共 API / 适配层文件 | 引擎升级后手动运行，生成建议清单 |
| `sourcemap-sync.py` | JSON（真源）→ SOURCEMAP.md + `.agent/context` | `setup.sh` 自动调用；改 JSON 后手动 `sync` |
| `engines/*/scripts/validate_sourcemap.sh` | WHITELIST/BLACKLIST 路径存在性 | 改路径后或与 CI 对齐时运行 |

薄封装：`macode sourcemap validate|generate-md|scan-api|version-check`（见 `bin/macode`）。

**维护入口**：日常改 JSON → `macode sourcemap validate <engine>` 或 `python3 bin/sourcemap-sync.py --check`；查询 WHITELIST/BLACKLIST 仍可用 `bash bin/sourcemap-read <engine> whitelist|blacklist ...`（消费 `.agent/context/*_sourcemap.json`）。`sourcemap-sync.py`、`sourcemap-scan-api.py`、`sourcemap-version-check.py`、`sourcemap-read` 四者职责正交，不设再合并为单文件；`sourcemap-lint.py` 已删除（jsonschema 校验在 sync 内）。

```bash
# 快速健康检查（也见 macode sourcemap version-check）
python3 bin/sourcemap-version-check.py --all
# → 报告 engines/*/sourcemap.json version 字段与已安装引擎是否一致

# 扫描 API 覆盖缺口
python3 bin/sourcemap-scan-api.py --all
# → 列出适配层新文件、引擎公共类/函数中未在 WHITELIST 注册的项目
# → 开发者审核后选择性加入 engines/*/sourcemap.json（再 generate-md）
```

## 维护触发条件

- 引擎版本升级（`pip install --upgrade manim` / `npm update`）→ 先运行 `version-check`，再运行 `scan-api`
- Agent 误入陷阱（复盘后补入 BLACKLIST）
- 适配层新增代码（`engines/{name}/src/` 下新增文件）→ `scan-api` 会检测到
- 扩展计划变更（EXTENSION 中的 TODO → DONE/WONTFIX）

## 验证

修改 **sourcemap.json**（真源）后：

```bash
python3 bin/sourcemap-sync.py --check {name}                 # MD 与 JSON 一致
bash engines/{name}/scripts/validate_sourcemap.sh            # 路径存在性
python3 bin/sourcemap-sync.py {name}                       # 再生 SOURCEMAP.md / .agent/context
python3 bin/sourcemap-version-check.py {name}                # 版本匹配
```

或 `macode sourcemap validate {name}`（含 `--check` + `validate_sourcemap.sh`）。
