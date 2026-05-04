# MaCode SOURCEMAP 规范

> **版本**: v1.0  
> **状态**: 必须遵循  
> **适用范围**: 所有 `engines/{name}/SOURCEMAP.md` 的生成与维护

---

## 1. 什么是 SOURCEMAP

SOURCEMAP 是 MaCode 引擎的**源码探索地图**。它是一份结构化的黑白名单文档，告诉 Agent（包括 Claude Code）：

- **WHITELIST**: 哪些源码路径是安全的、值得深入阅读的 API 表面
- **BLACKLIST**: 哪些路径是陷阱（测试代码、内部黑魔法、废弃 API），应当避让
- **EXTENSION**: 哪些能力尚未接入 MaCode，但未来可能扩展

设计哲学：**透明性优于便利性**。Agent 不应盲目 `grep -r` 整个文件树，而应按图索骥。

---

## 2. 文件位置

每个引擎目录下**必须**存在一份：

```text
engines/
├── manim/
│   ├── SOURCEMAP.md          ← 本文件
│   ├── scripts/
│   │   └── inspect.sh        ← 读取 SOURCEMAP.md 输出结构化信息
│   └── ...
├── motion_canvas/
│   ├── SOURCEMAP.md
│   └── ...
└── definedmotion/
    ├── SOURCEMAP.md
    └── ...
```

**禁止**在项目根目录或 `docs/` 下放置全局 SOURCEMAP。每个引擎的 SOURCEMAP 必须与引擎代码同目录，确保 Agent 在 `cd engines/manim/` 后就能直接 `cat SOURCEMAP.md`。

---

## 3. 文档格式（严格三段式）

使用标准 Markdown，三段式标题固定大小写：

```markdown
# MaCode Engine Source Map: {引擎名}

> 生成日期: {YYYY-MM-DD}
> 引擎版本: {通过 pip / npm 查询到的确切版本}
> 适配层版本: {MaCode 引擎适配层版本，如 1.0.0}

## WHITELIST: 推荐探索路径

| 标识 | 路径/命令 | 用途 | 优先级 |
|------|-----------|------|--------|
| CORE_SCENE | `{可 eval 的真实路径}` | Scene 基类与生命周期 | P0 |
| ... | ... | ... | ... |

## BLACKLIST: 禁止/不建议探索

| 标识 | 路径/命令 | 原因 |
|------|-----------|------|
| INTERNAL_GL | `{路径}` | 配置黑魔法，修改会破坏环境 |
| ... | ... | ... |

## EXTENSION: 待补充/可添加

| 标识 | 描述 | 状态 |
|------|------|------|
| SHADER_PIPELINE | 自定义着色器接入点 | TODO |
| ... | ... | ... |
```

### 格式约束

- 三段式标题必须**严格**为 `## WHITELIST`、`## BLACKLIST`、`## EXTENSION`
- 表格每行必须以 `|` 开头和结尾
- 路径必须用反引号 `` ` `` 包裹，便于 `inspect.sh` 用正则提取
- 禁止在表格内使用多行文本或嵌套表格

---

## 4. 填充规则

### 4.1 WHITELIST 分级

| 优先级 | 含义 | 必须包含的内容 |
|--------|------|----------------|
| **P0** | 核心 API | 场景基类、主要图形对象、核心动画/变换类 |
| **P1** | 工具函数 | 相机控制、LaTeX/文本渲染、颜色工具、坐标系 |
| **P2** | MaCode 适配层 | `engines/{name}/src/templates/`、`engines/{name}/src/utils/` 下的自定义封装 |

**数量控制**：WHITELIST 不超过 20 行。Agent 的上下文有限，地图不是目录树 dump。

### 4.2 BLACKLIST 必须包含

- **测试代码目录**: `test/`、`__tests__/`、`*.spec.ts`、`*_test.py`
- **构建产物**: `dist/`、`build/`、`.agent/tmp/`、`node_modules/.cache/`
- **内部黑魔法**: `_config/`、`internal/`、以 `_` 开头的私有模块、元编程文件
- **废弃 API**: 旧版兼容层、已标记 deprecated 的模块
- **非本引擎目录**: 如 Python 引擎中的 `node_modules/`，JS 引擎中的 `venv/`

### 4.3 EXTENSION 用途

记录当前引擎**原生支持**但 MaCode **尚未接入**的能力：

```markdown
| 标识 | 描述 | 状态 |
|------|------|------|
| GPU_RENDER | 引擎支持 CUDA 加速渲染 | TODO |
| LIVE_PREVIEW | 引擎支持 WebSocket 实时预览 | WONTFIX |
```

状态必须是 `TODO` / `DOING` / `DONE` / `WONTFIX` 之一。

---

## 5. 路径真实性验证（强制步骤）

生成或修改 SOURCEMAP.md 后，**必须**执行验证。无效路径必须立即修正或删除。

### 5.1 验证脚本

```bash
#!/bin/bash
# 保存为 engines/{engine}/scripts/validate_sourcemap.sh

SOURCEMAP="engines/$1/SOURCEMAP.md"

echo "=== Validating WHITELIST paths ==="
grep -A1000 "^## WHITELIST" "$SOURCEMAP" | grep "^| " | while IFS='|' read -r _ id path _ _; do
  path=$(echo "$path" | sed 's/^[ 	]*//;s/[ 	]*$//;s/`//g')
  # 跳过表头
  [[ "$id" == " 标识 " ]] && continue
  # 尝试 eval（支持 $(python -c ...) 动态路径）
  eval_path=$(eval echo "$path" 2>/dev/null)
  if [ -e "$eval_path" ] || [ -d "$eval_path" ]; then
    echo "  ✓ $id: $eval_path"
  else
    echo "  ✗ INVALID WHITELIST: $id -> '$path' (resolved: '$eval_path')" >&2
    exit 1
  fi
done

echo "=== Validating BLACKLIST paths ==="
grep -A1000 "^## BLACKLIST" "$SOURCEMAP" | grep "^| " | while IFS='|' read -r _ id path reason; do
  path=$(echo "$path" | sed 's/^[ 	]*//;s/[ 	]*$//;s/`//g')
  [[ "$id" == " 标识 " ]] && continue
  eval_path=$(eval echo "$path" 2>/dev/null)
  if [ -e "$eval_path" ] || [ -d "$eval_path" ]; then
    echo "  ✓ $id: $eval_path (exists, blacklisted OK)"
  else
    echo "  ~ $id: '$path' not found on filesystem (may be import path)"
  fi
done
```

### 5.2 路径书写规范

- **物理路径**: 使用可 `eval` 的绝对路径或动态解析命令
  ```markdown
  | CORE_SCENE | `$(python -c "import manim; print(manim.__path__[0])")/scene/scene.py` | ... | P0 |
  ```
- **导入路径（无物理文件）**: 允许出现在 BLACKLIST，但必须在"原因"列标注 `(import path)`
  ```markdown
  | DEPRECATED_MODULE | `manimlib.scene.scene` | 旧版导入路径，无物理文件，已废弃 |
  ```

---

## 6. 与 inspect.sh 的契约

`engines/{engine}/scripts/inspect.sh` 必须能解析本文件：

```bash
#!/bin/bash
# engines/{engine}/scripts/inspect.sh

SOURCEMAP="$(dirname "$0")/../SOURCEMAP.md"

echo "=== WHITELIST (Safe to explore) ==="
grep -A1000 "^## WHITELIST" "$SOURCEMAP" | grep "^| " | grep -v "^| 标识 " | awk -F'|' '{printf "%-20s %s\n", $2, $3}'

echo ""
echo "=== BLACKLIST (Do not touch) ==="
grep -A1000 "^## BLACKLIST" "$SOURCEMAP" | grep "^| " | grep -v "^| 标识 " | awk -F'|' '{printf "%-20s %s\n", $2, $3}'

echo ""
echo "=== EXTENSION (Future work) ==="
grep -A1000 "^## EXTENSION" "$SOURCEMAP" | grep "^| " | grep -v "^| 标识 " | awk -F'|' '{printf "%-20s %-30s %s\n", $2, $3, $4}'
```

Agent 的使用方式：

```bash
engines/manim/scripts/inspect.sh
# 输出：
# CORE_SCENE            $(python -c "import manim; print(manim.__path__[0])")/scene/scene.py
# CORE_MOBJECT          $(python -c "import manim; print(manim.__path__[0])")/mobject/geometry.py
# ...
```

---

## 7. 维护触发条件

以下事件发生时，**必须**更新 SOURCEMAP.md：

1. **引擎版本升级**（`pip install --upgrade manim` / `npm update`）
2. **Agent 误入陷阱**（复盘后补入 BLACKLIST）
3. **适配层新增代码**（`engines/{name}/src/` 下新增模板或工具）
4. **扩展计划变更**（EXTENSION 中的 TODO 转为 DOING 或 WONTFIX）

---

## 8. 反模式（禁止做的事）

| 反模式 | 正确做法 |
|--------|----------|
| 把整个 `find . -type f` 结果 dump 进 WHITELIST | 只放 API 表面，不超过 20 行 |
| 使用相对路径 `./src/` | 使用 `$(node -e ...)` 或 `$(python -c ...)` 动态解析的绝对路径 |
| 在 BLACKLIST 中放"我不喜欢的代码风格" | BLACKLIST 只放"会导致破坏或浪费时间"的路径 |
| 用自然语言段落代替表格 | 每行必须有可执行的 `路径/命令` 列 |
| 路径不验证就提交 | 必须运行 `validate_sourcemap.sh` |
| 一个 SOURCEMAP 覆盖多个引擎 | 每个引擎独立一份，禁止全局合并 |

---

## 9. 示例：ManimCE SOURCEMAP.md

```markdown
# MaCode Engine Source Map: ManimCE

> 生成日期: 2026-05-04
> 引擎版本: 0.19.0
> 适配层版本: 1.0.0

## WHITELIST: 推荐探索路径

| 标识 | 路径/命令 | 用途 | 优先级 |
|------|-----------|------|--------|
| CORE_SCENE | `$(python -c "import manim; print(manim.__path__[0])")/scene/scene.py` | Scene 基类，construct() 生命周期 | P0 |
| CORE_MOBJECT_GEOMETRY | `$(python -c "import manim; print(manim.__path__[0])")/mobject/geometry.py` | Circle, Square, Line 等几何体 | P0 |
| CORE_MOBJECT_TYPES | `$(python -c "import manim; print(manim.__path__[0])")/mobject/types/vectorized_mobject.py` | VMobject 基类，路径与贝塞尔曲线 | P0 |
| CORE_ANIMATION_CREATION | `$(python -c "import manim; print(manim.__path__[0])")/animation/creation.py` | Create, DrawBorderThenFill, Uncreate | P0 |
| CORE_ANIMATION_TRANSFORM | `$(python -c "import manim; print(manim.__path__[0])")/animation/transform.py` | Transform, ReplacementTransform | P0 |
| UTIL_CAMERA | `$(python -c "import manim; print(manim.__path__[0])")/camera/` | 相机控制与取景 | P1 |
| UTIL_TEX | `$(python -c "import manim; print(manim.__path__[0])")/mobject/text/tex_mobject.py` | MathTex, Tex 实现 | P1 |
| UTIL_NUMBER_LINE | `$(python -c "import manim; print(manim.__path__[0])")/mobject/graphing/number_line.py` | NumberLine, 坐标轴基础 | P1 |
| ADAPTER_TEMPLATE | `engines/manim/src/templates/scene_base.py` | MaCode 场景基类模板 | P0 |
| ADAPTER_UTILS | `engines/manim/src/utils/ffmpeg_pipe.py` | 直接调用 ffmpeg 编码帧序列 | P2 |

## BLACKLIST: 禁止/不建议探索

| 标识 | 路径/命令 | 原因 |
|------|-----------|------|
| DEPRECATED_GL | `manimlib/` | ManimGL 旧版 API，与 CE 不兼容 |
| TEST_SUITE | `$(python -c "import manim; print(manim.__path__[0])")/test/` | 测试代码，非 API 表面 |
| INTERNAL_CONFIG | `$(python -c "import manim; print(manim.__path__[0])")/_config/` | 全局配置黑魔法，修改会破坏渲染环境 |
| INTERNAL_UTILS | `$(python -c "import manim; print(manim.__path__[0])")/utils/` | 内部工具函数，非稳定 API |
| BUILD_ARTIFACT | `.agent/tmp/` | 中间产物，非源码 |
| NODE_MODULES | `node_modules/` | 非 Python 引擎目录 |

## EXTENSION: 待补充/可添加

| 标识 | 描述 | 状态 |
|------|------|------|
| SHADER_PIPELINE | 自定义 GLSL 着色器接入 | TODO |
| AUDIO_SYNC | 音频节拍同步（BPM 驱动动画） | TODO |
| GPU_RENDER | CUDA/OpenCL 加速渲染 | WONTFIX |
```

---

## 10. 执行检查清单

为引擎生成 SOURCEMAP.md 时，按此顺序执行：

- [ ] 查询引擎版本并记录到文档头部
- [ ] 通过 `find` + `grep` 探索源码，识别核心 API 文件
- [ ] 按 P0/P1/P2 分级填入 WHITELIST（不超过 20 行）
- [ ] 识别测试文件、内部模块、废弃路径填入 BLACKLIST
- [ ] 检查 MaCode 适配层 `engines/{name}/src/` 内容，补入 WHITELIST
- [ ] 运行 `engines/{name}/scripts/validate_sourcemap.sh` 验证路径真实性
- [ ] 修正或删除所有无效路径
- [ ] 将结果写入 `engines/{name}/SOURCEMAP.md`
- [ ] 运行 `engines/{name}/scripts/inspect.sh` 验证输出格式正确
- [ ] `git add` 并提交，提交信息格式：`docs(manim): update SOURCEMAP for v0.19.0`

---

*规范版本: v1.0*  
*最后更新: 2026-05-04*  
*状态: 生效中*


---

## Part II: SOURCEMAP 在 MaCode Harness 中的使用与融入

> **适用范围**: 本部分描述 SOURCEMAP.md 如何被 Harness 基础设施消费，以支持"数学动画引擎使用者 Agent"的安全、高效工作流。
>
> **核心原则**: 使用者 Agent **只读** SOURCEMAP；Harness 负责在关键节点注入、审查与诊断。

---

## 11. 两类 Agent 的权限模型

| 角色 | 对 SOURCEMAP 的权限 | 职责 |
|------|-------------------|------|
| **开发者 Agent** | **读写** | 维护引擎适配层、升级引擎版本、修正 BLACKLIST |
| **使用者 Agent** | **只读** | 编写 `scenes/` 下的场景代码，调用 `pipeline/` 渲染 |

**禁止**: 使用者 Agent 直接修改 `engines/{name}/SOURCEMAP.md`。若发现版本不匹配，应通过 `macode status` 报告，由开发者 Agent 或人类维护者更新。

---

## 12. Harness 启动自举（Bootstrap）

当使用者 Agent 通过 `bin/agent-shell` 进入工作环境时，Harness 自动完成 SOURCEMAP 的加载与校验：

```bash
#!/bin/bash
# bin/agent-shell 片段

ENGINE=$(cat project.yaml | yq -r '.default_engine')
SOURCEMAP="engines/${ENGINE}/SOURCEMAP.md"

# 1. 校验 SOURCEMAP 存在
if [ ! -f "$SOURCEMAP" ]; then
  echo "FATAL: SOURCEMAP.md not found for engine '$ENGINE'" >&2
  echo "Run: macode sourcemap init $ENGINE" >&2
  exit 1
fi

# 2. 校验新鲜度（引擎版本 vs SOURCEMAP 版本）
ENG_VER=$(pip show "$ENGINE" 2>/dev/null | grep Version | awk '{print $2}' || node -e "console.log(require('$ENGINE/package.json').version)")
MAP_VER=$(grep "引擎版本" "$SOURCEMAP" | head -1 | sed 's/.*引擎版本:[[:space:]]*//')

if [ "$ENG_VER" != "$MAP_VER" ]; then
  echo "WARN: SOURCEMAP outdated (map: $MAP_VER, engine: $ENG_VER)" >&2
  echo "Some API paths may be invalid. Proceed with caution." >&2
fi

# 3. 提取 WHITELIST P0/P1 到 Agent 上下文目录
mkdir -p .agent/context
grep -A1000 "^## WHITELIST" "$SOURCEMAP" | grep "^| " | grep -v "^| 标识 " | awk -F'|' '$4 ~ /P0|P1/ {print $2, $3}' > .agent/context/engine_api.txt

# 4. 提取 BLACKLIST 到安全门上下文
grep -A1000 "^## BLACKLIST" "$SOURCEMAP" | grep "^| " | grep -v "^| 标识 " | awk -F'|' '{print $2, $3}' > .agent/context/engine_blacklist.txt

# 5. 设置环境变量供 Agent 查询
export MACODE_ENGINE="$ENGINE"
export MACODE_SOURCEMAP="$SOURCEMAP"
export MACODE_CONTEXT=".agent/context"

exec bash
```

**Agent 感知**: 它不需要知道 SOURCEMAP 的存在，但会在系统提示中看到注入的 P0/P1 API 速查表。

---

## 13. 系统提示注入（Prompt Injection）

Harness 在调用 LLM（Agent）前，将 SOURCEMAP 转化为精简、结构化的工作记忆，而非完整文档：

```yaml
# project.yaml —— Agent 上下文配置片段
agent:
  context_bootstrap:
    - "engines/${default_engine}/SOURCEMAP.md"
  prompt_injection:
    whitelist_max: 10        # 只注入前 N 个 WHITELIST 条目，防止上下文爆炸
    blacklist_enforcement: true  # 启用代码静态检查
    extension_visibility: false   # 使用者 Agent 不感知 EXTENSION（避免分心）
```

**注入格式示例**（自动附加到 Agent 系统提示末尾）：

```markdown
【引擎环境: ManimCE v0.19.0 | MaCode 适配层 v1.0.0】

可用核心 API（P0/P1）:
- Scene: `manim.scene.scene.Scene` —— 基类，重写 `construct()`
- Circle: `manim.mobject.geometry.Circle`
- MathTex: `manim.mobject.text.tex_mobject.MathTex`
- Create: `manim.animation.creation.Create`
- Transform: `manim.animation.transform.Transform`
- NumberLine: `manim.mobject.graphing.number_line.NumberLine`

陷阱避让（禁止导入）:
- `manimlib.*` —— 旧版 API，已废弃
- `manim._config.*` —— 内部配置黑魔法
- `manim.test.*` —— 测试代码，非稳定 API

探索更多: 运行 `macode inspect --grep <keyword>` 查询完整 WHITELIST。
```

**规则**:
- 只注入 P0/P1，P2（适配层工具）在需要时由 `macode inspect` 按需查询。
- BLACKLIST 只列出模块/包名，不展开内部细节，避免反向提示（teaching agent how to hack）。

---

## 14. 代码审查门：API-Gate

在场景代码执行渲染前，Harness 必须运行静态检查，拦截 BLACKLIST 中的违规导入：

### 14.1 api-gate.py 实现

```python
#!/usr/bin/env python3
# bin/api-gate.py
"""利用 SOURCEMAP BLACKLIST 做导入静态拦截"""

import sys, re, os

def load_blacklist(sourcemap_path):
    """解析 SOURCEMAP.md 的 BLACKLIST 表格"""
    patterns = []
    with open(sourcemap_path, 'r', encoding='utf-8') as f:
        content = f.read()
    # 提取 BLACKLIST 段
    m = re.search(r'## BLACKLIST:.*?\n(.*?)(?=\n## |\Z)', content, re.DOTALL)
    if not m:
        return patterns
    for line in m.group(1).splitlines():
        if not line.startswith('|') or ' 标识 ' in line:
            continue
        parts = [p.strip() for p in line.split('|')]
        if len(parts) >= 4:
            path_raw = parts[2].strip().strip('`')
            if path_raw:
                patterns.append(path_raw)
    return patterns

def check_scene(filepath, blacklist):
    """检查场景源码是否包含 BLACKLIST 导入"""
    with open(filepath, 'r', encoding='utf-8') as f:
        code = f.read()

    violations = []
    for raw in blacklist:
        # 将路径模式转换为导入模式
        # e.g., "manimlib/" -> "import manimlib" / "from manimlib"
        # e.g., "manim/_config/" -> "import manim._config" / "from manim._config"
        module = raw.rstrip('/').replace('/', '.')
        # 匹配 import 语句
        if re.search(rf'(?:import\s+{re.escape(module)}|from\s+{re.escape(module)}\s+import)', code):
            violations.append(f"BLACKLIST import: {module} (matched pattern: {raw})")

    return violations

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: api-gate.py <scene_file> <sourcemap_path>", file=sys.stderr)
        sys.exit(2)

    scene_file = sys.argv[1]
    sourcemap_path = sys.argv[2]

    if not os.path.exists(scene_file):
        print(f"FATAL: Scene file not found: {scene_file}", file=sys.stderr)
        sys.exit(2)

    blacklist = load_blacklist(sourcemap_path)
    violations = check_scene(scene_file, blacklist)

    if violations:
        print("API_GATE_VIOLATIONS:")
        for v in violations:
            print(f"  - {v}")
        print(f"\n修复建议: 查阅 {sourcemap_path} 的 WHITELIST，使用推荐 API 替代。")
        sys.exit(1)
    else:
        print("API_GATE_OK")
        sys.exit(0)
```

### 14.2 嵌入渲染管道

```bash
#!/bin/bash
# pipeline/render.sh —— 渲染前检查片段

SCENE_DIR=$1
SCENE_FILE=$(find "$SCENE_DIR" -maxdepth 1 \( -name "*.py" -o -name "*.tsx" \) | head -1)
ENGINE=$(cat "$SCENE_DIR/manifest.json" | jq -r '.engine')
SOURCEMAP="engines/${ENGINE}/SOURCEMAP.md"

# --- API-Gate: 代码审查门 ---
echo "[api-gate] Checking scene code against SOURCEMAP BLACKLIST..."
if ! bin/api-gate.py "$SCENE_FILE" "$SOURCEMAP"; then
  echo "[api-gate] BLOCKED. Fix violations before rendering." >&2
  exit 1
fi

# --- 继续渲染 ---
engines/${ENGINE}/scripts/render.sh "$SCENE_FILE" ".agent/tmp/$(basename "$SCENE_DIR")/"
```

**设计意图**: 让错误在**渲染前**被发现，而不是在 5 分钟后渲染失败时才暴露。

---

## 15. 交互式探索：macode inspect

使用者 Agent 在编码过程中可能遗忘 API，Harness 提供标准化的 SOURCEMAP 查询接口：

### 15.1 命令设计

```bash
# 查询 WHITELIST 中的 P0 API
macode inspect --level P0

# 模糊搜索 API（支持正则）
macode inspect --grep "circle\|round"

# 查询 BLACKLIST（确认某个导入是否被禁止）
macode inspect --blacklist --grep "manimlib"

# 输出 JSON（供 Agent 程序化解析）
macode inspect --format json --grep "Transform"
```

### 15.2 JSON 输出示例

```bash
$ macode inspect --format json --grep "NumberLine"
{
  "engine": "manim",
  "sourcemap_version": "1.0.0",
  "query": "NumberLine",
  "matches": [
    {
      "section": "WHITELIST",
      "id": "UTIL_NUMBER_LINE",
      "path": "$(python -c \"import manim; print(manim.__path__[0])\")/mobject/graphing/number_line.py",
      "purpose": "NumberLine, 坐标轴基础",
      "priority": "P1"
    }
  ]
}
```

### 15.3 在 Agent 工作流中的使用

```bash
# Agent 想画坐标轴但忘了类名
$ macode inspect --grep "axis\|coordinate\|NumberLine"
# Harness 读取 SOURCEMAP.md，返回匹配条目
# Agent 根据结果写代码，无需猜测
```

---

## 16. 错误恢复：从异常反查 SOURCEMAP

当渲染失败时，Harness 的日志解析器自动关联 SOURCEMAP，提供定向修复建议：

```bash
#!/bin/bash
# engines/{engine}/scripts/render.sh —— 错误处理片段

LOG_FILE=".agent/log/$(date +%Y%m%d_%H%M%S)_render.log"
ENGINE_NAME="${ENGINE}"
SOURCEMAP="engines/${ENGINE_NAME}/SOURCEMAP.md"

# 执行渲染
if ! python -m manim "$SCENE_FILE" --format png -o "$OUTPUT_DIR" > "$LOG_FILE" 2>&1; then
    echo "[render] FAILED. Analyzing log..." >&2

    # 1. 检查是否触发 BLACKLIST 模式
    if grep -q "manimlib" "$LOG_FILE"; then
        echo "[diagnosis] 你可能使用了已废弃的 manimlib API。" >&2
        echo "[action]    查阅 $SOURCEMAP BLACKLIST 条目 DEPRECATED_GL" >&2
        echo "[fix]       将 'from manimlib...' 替换为 'from manim...'" >&2
    fi

    # 2. 检查是否误触内部模块
    if grep -q "_config" "$LOG_FILE" || grep -q "cannot import name.*from 'manim._config'" "$LOG_FILE"; then
        echo "[diagnosis] 导入了引擎内部配置模块。" >&2
        echo "[action]    查阅 $SOURCEMAP BLACKLIST 条目 INTERNAL_CONFIG" >&2
        echo "[fix]       移除对 manim._config 的导入，使用公开 API。" >&2
    fi

    # 3. 检查是否使用了测试模块
    if grep -q "manim.test" "$LOG_FILE"; then
        echo "[diagnosis] 误导入测试模块。" >&2
        echo "[action]    查阅 $SOURCEMAP BLACKLIST 条目 TEST_SUITE" >&2
    fi

    # 4. 通用建议
    echo "[hint] Run 'macode inspect --grep <keyword>' to find correct API." >&2

    exit 1
fi
```

**关键设计**: 错误信息不是"ModuleNotFoundError"的裸堆栈，而是**"你踩了 BLACKLIST 中的陷阱，地图在这里，修复方案是 X"**。

---

## 17. 完整工作流：使用者 Agent 的一天

```text
┌──────────────────────────────────────────────────────────────┐
│ 1. 启动                                                        │
│    $ macode agent-shell                                        │
│    → Harness 读取 project.yaml，确定引擎（如 manim）            │
│    → 校验 engines/manim/SOURCEMAP.md 存在且版本匹配             │
│    → 提取 P0/P1 API 到 .agent/context/engine_api.txt            │
│    → 提取 BLACKLIST 到 .agent/context/engine_blacklist.txt      │
│    → 将 API 速查表注入 Agent 系统提示                            │
├──────────────────────────────────────────────────────────────┤
│ 2. 探索                                                        │
│    Agent: "我想画一个带 LaTeX 标注的坐标系"                       │
│    → $ macode inspect --grep "NumberLine\|Axes\|MathTex"        │
│    → Harness 查询 SOURCEMAP WHITELIST，返回匹配条目               │
│    → Agent 确认 API 存在且安全                                   │
├──────────────────────────────────────────────────────────────┤
│ 3. 编码                                                        │
│    Agent 写 scenes/02_demo/scene.py                             │
│    → 系统提示中的 WHITELIST 作为"工作记忆"指导 API 选择            │
│    → Agent 不会误用 manimlib（因为系统提示明确禁止）               │
├──────────────────────────────────────────────────────────────┤
│ 4. 审查门（渲染前）                                             │
│    $ pipeline/render.sh scenes/02_demo/                        │
│    → 调用 bin/api-gate.py 检查 scene.py                         │
│    → 若发现 "import manimlib" → 立即阻断，返回 SOURCEMAP 修复建议  │
│    → 通过则继续                                                  │
├──────────────────────────────────────────────────────────────┤
│ 5. 渲染                                                        │
│    → engines/manim/scripts/render.sh 输出帧序列                  │
│    → ffmpeg 编码为 MP4                                          │
├──────────────────────────────────────────────────────────────┤
│ 6. 错误恢复（若渲染失败）                                        │
│    → 日志解析器扫描错误关键词                                     │
│    → 匹配 BLACKLIST 条目 → 输出定向诊断                           │
│    → Agent 根据诊断修复代码，而非盲目重试                          │
├──────────────────────────────────────────────────────────────┤
│ 7. 提交                                                        │
│    $ git add scenes/02_demo/ && git commit -m "add demo scene"   │
│    → SOURCEMAP.md 本身不被提交（它是引擎基础设施，非场景内容）      │
└──────────────────────────────────────────────────────────────┘
```

---

## 18. 需要新增/修改的文件清单

| 文件 | 类型 | 说明 |
|------|------|------|
| `bin/agent-shell` | 修改 | 启动时加载 SOURCEMAP 到 `.agent/context/` |
| `bin/macode` | 修改 | 新增 `inspect [--grep] [--format json] [--level P0/P1/P2]` 子命令 |
| `bin/api-gate.py` | **新增** | 基于 SOURCEMAP BLACKLIST 做导入静态检查 |
| `pipeline/render.sh` | 修改 | 渲染前调用 `api-gate.py` |
| `engines/{name}/scripts/render.sh` | 修改 | 错误处理中增加 SOURCEMAP 诊断提示 |
| `engines/{name}/scripts/validate_sourcemap.sh` | 已有 | 维护时使用，使用者 Agent 不直接调用 |
| `project.yaml` | 修改 | 新增 `agent.context_bootstrap` 和 `agent.prompt_injection` 配置 |
| `engines/{name}/SOURCEMAP.md` | 按规范维护 | 引擎地图本身 |

---

## 19. 反模式（使用者 Agent 侧）

| 反模式 | 正确做法 |
|--------|----------|
| 使用者 Agent 直接编辑 `SOURCEMAP.md` | 只读；发现版本不匹配时报告 `macode status` |
| 在场景代码中 `import` 未在 WHITELIST 中的模块 | 先用 `macode inspect --grep` 确认 API 存在 |
| 忽略 `API_GATE_VIOLATIONS` 强行渲染 | 必须先修复违规导入，再提交渲染 |
| 在系统提示中请求"列出所有可用 API" | 会超出上下文；应使用 `macode inspect --level P0` |
| 在错误恢复时盲目重试 | 先阅读 Harness 提供的 SOURCEMAP 定向诊断 |

---

## 20. 总结

> **SOURCEMAP.md 不是给 Agent 看的文档，而是给 Harness 用的约束协议。**
>
> Harness 在启动时把它变成 Agent 的**工作记忆**，在编码时用它做**审查门**，在出错时用它做**诊断地图**。使用者 Agent 始终只读，开发者 Agent 负责维护。地图与引擎同目录，与代码同版本，与错误同诊断。

---

*规范版本: v1.0*  
*最后更新: 2026-05-04*  
*状态: 生效中*
