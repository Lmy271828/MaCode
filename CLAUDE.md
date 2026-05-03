# MaCode —— UNIX 原生的数学动画制作 Harness

> **设计信条**：Bash is all you need. Text is the universal interface. Make it work, then make it right, then make it fast.
>
> **名称来源**：Ma = Math（数学）+ Code（代码），亦致敬 UNIX 传统中简洁的命名哲学。

---

## 1. 项目愿景

MaCode 是一个 Claude Code 式的数学动画 Agent 工作流系统。它不封装高级 API，而是提供一个**透明的、可被 `ls / cat / grep` 完全理解的文件系统环境**，让 Agent 通过 Bash 命令探索、组合、修复数学动画的每一个环节。

核心目标：
- **引擎无关**：场景定义与引擎实现解耦。今天用 ManimCE，明天可迁移到 Motion Canvas，只需修改一行 `manifest.json`。
- **管道透明**：渲染、剪辑、压缩的每一步都是可见的文件转换，Agent 随时可以 `ls .agent/tmp/frames/` 检查中间状态。
- **状态可逆**：所有 Agent 行为通过 Git 流控制实现原子化与可回滚，错误是廉价的。
- **音频统一**：所有音频处理（合成、拼接、淡入淡出、压缩）由 `ffmpeg` 完成，不引入额外依赖。

---

## 2. UNIX 设计原则（核心哲学）

### 2.1 做一件事并做好
- **渲染引擎**只输出帧序列（PNG / rawvideo）。
- **ffmpeg**负责所有音视频编码、剪辑、滤镜、格式转换。
- **Agent**只负责生成场景源码与编排命令。
- **Git**只负责版本控制与状态回滚。
- 绝不内建"一站式"黑盒：没有 `render_and_upload()`，只有 `render.sh` 和 `upload.sh`。

### 2.2 文本流是通用接口
- 场景契约：`scenes/*/manifest.json`（JSON 文本）。
- 帧清单：`.agent/tmp/{scene}/frames/list.txt`（每行一个文件路径）。
- 时间码：`.agent/tmp/{scene}/timeline.csv`（帧号, 动作, 参数）。
- 渲染日志：`.agent/log/YYYYMMDD_HHMMSS_{task}.log`（纯文本）。
- Agent 无需解析二进制格式，`jq`、`awk`、`sed` 即可处理全部配置。

### 2.3 管道组合复杂任务
```bash
# 复杂动画的 UNIX 式表达
python -m manim scene.py --format png -o .agent/tmp/frames/ \
  | tee .agent/log/manim.log \
  && ffmpeg -f concat -i <(find .agent/tmp/frames -name "*.png" | sort | sed 's/^/file /') \
     -c:v libx264 -pix_fmt yuv420p out.mp4
```

### 2.4 透明性优于便利性
- 帧序列必须物理存在于文件系统，Agent 随时可用 `identify frame_120.png` 检查单帧。
- 引擎源码必须可被 `grep`：Agent 通过 `find $(python -c "import manim; print(manim.__path__[0]") -name "*.py" | xargs grep "class Circle"` 学习 API，而非查阅封闭文档。
- 所有命令执行日志写入 `.agent/log/`，Agent 出错时先 `tail -n 50 .agent/log/last_run.log`。
- 音频处理不隐藏为内部库调用，Agent 直接阅读 `pipeline/add_audio.sh` 中的 `ffmpeg` 命令。

### 2.5 优先使用工具而非机制
- 需要音频合成？调用 `ffmpeg -f lavfi` 生成测试音，不内建音频引擎。
- 需要公式渲染？调用 `pdflatex` 或 `mathjax-node-cli`，不内建排版系统。
- 需要缓存？使用 `just` 的文件时间戳判断，不内建数据库。
- 需要视频剪辑？调用 `ffmpeg` 的 filtergraph，不内建时间轴编辑器。

---

## 3. 系统架构

### 3.1 目录结构（Agent 的"API 文档"）

```text
macode/
├── .agent/                  # Agent 工作区（可写，gitignored）
│   ├── tmp/                 # 临时帧、中间文件、原始输出
│   │   └── {scene_name}/
│   │       ├── frames/
│   │       │   ├── frame_0001.png
│   │       │   └── ...
│   │       ├── raw.mp4      # 无音频的原始渲染输出
│   │       ├── final.mp4    # 合成音频后的最终输出
│   │       └── render.log   # 该场景的完整渲染日志
│   ├── cache/               # 渲染缓存（按场景内容哈希）
│   └── log/                 # 全局命令执行日志
│
├── engines/                 # 渲染引擎适配层（只读模板）
│   ├── manim/
│   │   ├── src/             # 引擎适配源码（Agent 可 grep 学习）
│   │   │   ├── templates/     # 基类模板（CameraScene, setup, construct）
│   │   │   ├── mobjects/      # 自定义 Mobject
│   │   │   └── utils/         # ffmpeg_pipe.py, latex_helper.py
│   │   ├── scripts/
│   │   │   ├── render.sh      # 入口：scene.py + output_dir → 帧序列
│   │   │   ├── inspect.sh     # 打印可用 Mobject / Animation 列表
│   │   │   └── site_packages.sh # 打印 manim 安装路径
│   │   └── Justfile
│   └── motion_canvas/
│       ├── src/
│       │   ├── templates/
│       │   │   └── scene_base.tsx
│       │   └── utils/
│       │       └── mathjax_bridge.ts
│       ├── scripts/
│       │   ├── render.sh
│       │   └── inspect.sh
│       └── Justfile
│
├── scenes/                  # 用户场景（Agent 主要工作区）
│   ├── 00_title/
│   │   ├── manifest.json      # 场景契约：引擎类型、时长、依赖
│   │   ├── scene.py           # 引擎实现（视图层）
│   │   └── assets/            # 图片、音频、字体、LaTeX 片段
│   ├── 01_intro/
│   │   ├── manifest.json
│   │   ├── scene.py
│   │   └── assets/
│   └── 02_fourier/
│       ├── manifest.json
│       ├── scene.tsx          # 若引擎为 motion_canvas
│       └── assets/
│
├── pipeline/                # 后处理管道（纯 bash，ffmpeg 驱动）
│   ├── render.sh            # 读取 manifest，分发到引擎渲染脚本
│   ├── concat.sh            # 场景拼接（ffmpeg concat demuxer）
│   ├── add_audio.sh         # 音轨合成（ffmpeg amix / amerge）
│   ├── fade.sh              # 淡入淡出（ffmpeg afade / fade filter）
│   ├── compress.sh          # 输出压缩（CRF / preset 控制）
│   └── preview.sh           # 快速预览（降分辨率 / 抽帧）
│
├── bin/                     # 全局工具脚本
│   ├── macode               # 主入口 CLI
│   ├── agent-shell          # Agent 默认 shell 入口，预装 PATH
│   ├── agent-run.sh         # Git 原子操作包装器
│   ├── safety-gate.sh       # 命令白名单拦截器
│   └── discover             # 交互式项目结构探索助手
│
└── project.yaml             # 全局配置：默认引擎、分辨率、fps、安全策略
```

### 3.2 三层解耦（可迁移性的基石）

```text
┌─────────────────────────────────────┐
│  Layer 3: Scene 描述 (manifest.json) │  ← 唯一不变层，引擎无关
├─────────────────────────────────────┤
│  Layer 2: Engine 适配 (engines/*)     │  ← 可替换：Manim ↔ Motion Canvas ↔ 未来引擎
├─────────────────────────────────────┤
│  Layer 1: 基础设施 (bash, ffmpeg, git)│  ← 绝对稳定，跨平台通用
└─────────────────────────────────────┘
```

**迁移示例**：将 Manim 场景迁移到 Motion Canvas：
1. Agent 读取 `manifest.json` 理解需求（时长、资产、依赖）。
2. Agent 用 `engines/motion_canvas/scripts/inspect.sh` 探索目标引擎能力。
3. Agent 用 `grep / find` 阅读目标引擎模板源码，理解映射关系。
4. Agent 生成新的 `scene.tsx`，修改 `manifest.json` 中的 `engine` 字段。
5. 重新运行 `pipeline/render.sh`，不修改任何管道脚本。

---

## 4. Agent 工作流（Bash-First）

### 4.1 引擎发现协议
Agent 不依赖外部 API 文档，通过文件系统自学：

```bash
# 查询当前项目默认引擎
cat project.yaml | yq '.default_engine'

# 发现可用模板
grep "^class " engines/manim/src/templates/*.py

# 探索引擎源码实现（学习内部机制）
find $(python -c "import manim; print(manim.__path__[0]") -name "*.py" \
  | xargs grep -l "def interpolate"

# 查看引擎提供了哪些脚本
ls engines/manim/scripts/
```

### 4.2 场景契约（manifest.json）
Agent 不直接调用引擎 API，而是生成符合契约的文件：

```json
{
  "engine": "manim",
  "template": "CameraScene",
  "duration": 10,
  "fps": 30,
  "resolution": [1920, 1080],
  "assets": ["assets/formula.tex", "assets/voiceover.mp3"],
  "dependencies": ["scenes/00_title/manifest.json"],
  "meta": {
    "title": "傅里叶级数展开",
    "author": "agent",
    "tags": ["fourier", "calculus"]
  }
}
```

### 4.3 渲染管道调用
```bash
# 渲染单个场景
pipeline/render.sh scenes/02_fourier/

# 内部展开为引擎特定命令
# → engines/manim/scripts/render.sh scenes/02_fourier/scene.py .agent/tmp/02_fourier/
# → ffmpeg -f image2 -i .agent/tmp/02_fourier/frames/frame_%04d.png ...
# → pipeline/add_audio.sh .agent/tmp/02_fourier/raw.mp4 scenes/02_fourier/assets/voiceover.mp3 .agent/tmp/02_fourier/final.mp4
```

### 4.4 后处理（ffmpeg 原生）
```bash
# 场景拼接（基于 manifest 依赖顺序）
cat > /tmp/concat_list.txt <<EOF
file 'scenes/00_title/output/final.mp4'
file 'scenes/01_intro/output/final.mp4'
file 'scenes/02_fourier/output/final.mp4'
EOF
ffmpeg -f concat -safe 0 -i /tmp/concat_list.txt -c copy output/lecture.mp4

# 音频淡入淡出（ffmpeg filtergraph）
ffmpeg -i input.mp4 -af "afade=t=in:ss=0:d=0.5,afade=t=out:st=9.5:d=0.5" output.mp4

# 压缩（用于预览）
ffmpeg -i output/lecture.mp4 -vcodec libx264 -crf 28 -preset fast -vf "scale=1280:-2" output/lecture_preview.mp4

# 生成测试音（替代 SoX synth）
ffmpeg -f lavfi -i "sine=frequency=1000:duration=1" -acodec pcm_s16le ding.wav

# 生成静音填充
ffmpeg -f lavfi -i anullsrc=r=48000:cl=stereo -t 5 -acodec pcm_s16le silence_5s.wav
```

---

## 5. 安全模型：Git 核心 + 三层硬壳

在显式指定工具边界（`manim` + `ffmpeg` + 白名单命令）后，纵深防御收敛为以下四层：

### 5.1 Layer 0: 工具白名单（命令拦截）
Agent 只能调用预声明的工具，不能执行任意 bash：

```yaml
# project.yaml —— 安全策略片段
agent:
  allowed_commands:
    - manim
    - ffmpeg
    - ffprobe
    - jq
    - yq
    - git
    - find
    - grep
    - sed
    - awk
    - just
    - du
    - df
    - cat
    - ls
    - cp
    - mv
    - rm
  blocked_patterns:
    - "rm -rf /"
    - "curl|wget"
    - "eval|exec|bash -c"
    - "pip install"
    - "npm install"
  resource_limits:
    max_frames_per_scene: 10000
    max_disk_gb: 50
    max_render_time_sec: 600
```

### 5.2 Layer 1: Git 流控制（核心防御）
所有 Agent 行为原子化、可回滚：

```bash
# bin/agent-run.sh —— harness 自动执行（Agent 无感知）
git stash push -m "pre-task"
git checkout -b agent/${TASK_ID}
# → 运行 Agent 命令
# → 成功：git commit + merge --no-ff
# → 失败：git checkout - + git branch -D（自动回滚）
```

**关键设计**：
- 按"渲染任务"批量 commit，不按文件修改频繁提交。
- 渲染实验使用临时 branch，确认后 merge，废弃则直接删除 branch。
- Git 只管理代码 / 配置，帧 / 视频等大文件通过 `.gitignore` 排除，必要时用 Git LFS。

### 5.3 Layer 2: 资源熔断（外部守护）
```bash
# 渲染前检查（harness 预置）
frames=$(find .agent/tmp/ -name "*.png" | wc -l)
if [ $frames -gt 10000 ]; then
  echo "FUSE: 帧数超限，停止渲染" >&2
  exit 1
fi
```

### 5.4 Layer 3: 规则引擎（系统提示）
Agent 系统提示中明确约束：
- 禁止修改 `engines/` 目录（只读）。
- 禁止删除 `.git` 目录。
- 禁止跳出项目根目录执行命令。
- 优先使用 `inspect.sh` 了解引擎能力，不假设 API 存在。
- 音频处理必须使用 `ffmpeg`，禁止引入 `sox` 或其他音频工具。

---

## 6. 引擎选型策略

### 6.1 默认引擎：ManimCE
- **理由**：生态最成熟，Agent 训练数据丰富，LaTeX 支持原生，3Blue1Brown 风格标杆。
- **约束**：必须通过 `engines/manim/scripts/render.sh` 调用，Agent 不直接执行 `python -m manim`。

### 6.2 轻量备选：Motion Canvas
- **理由**：热重载友好，实时预览加速 Agent 迭代，MIT 协议无商业限制。
- **约束**：通过 `engines/motion_canvas/scripts/render.sh` 统一入口。

### 6.3 3D 备选：DefinedMotion / Three.js 原生
- **理由**：基于 Three.js，Agent 理解成本低，3D 几何可视化强。
- **约束**：待 Phase 2（引擎抽象层）引入，Phase 0/1 不实现。

### 6.4 明确不选
- **Remotion（作为主引擎）**：通用视频 / 营销视频工具，数学动画需要从零写 SVG/Canvas 绘制逻辑，无内置数学对象抽象。它更适合作为"最终拼接层"（若需将动画片段与 UI 数据结合），而非数学动画主引擎。
- **SoX（音频处理）**：Windows 下管道不可靠，MP3 支持经常缺失，PowerShell 集成体验差。所有音频处理统一由 `ffmpeg` 完成，保持依赖单一化。

---

## 7. 文件命名与接口约定

### 7.1 场景目录命名
```text
scenes/
├── 00_title/          # 序号前缀保证管道拼接顺序
├── 01_intro/
├── 02_fourier_series/
└── 03_epilogue/
```

### 7.2 中间产物命名
```text
.agent/tmp/{scene_name}/
├── frames/
│   ├── frame_0001.png
│   └── ...
├── raw.mp4            # 无音频的原始渲染输出
├── final.mp4          # 合成音频后的最终输出
└── render.log         # 该场景的完整渲染日志
```

### 7.3 日志规范
所有脚本必须将 stderr + stdout 追加到 `.agent/log/YYYYMMDD_HHMMSS_{script_name}.log`，Agent 调试时通过 `tail` 读取。

---

## 8. 反模式（Agent 禁止做的事）

1. **不要内建 IDE**：Agent 不需要"智能提示"，它需要 `grep` 和 `find`。
2. **不要抽象过度**：不要为 Manim 和 Motion Canvas 创建统一的 Python/TypeScript SDK。统一层只在 `manifest.json` 和 `pipeline/*.sh` 中存在。
3. **不要隐藏中间状态**：禁止将帧序列输出为内存流或临时删除。Agent 必须能 `ls` 看到每一帧。
4. **不要动态下载依赖**：Agent 禁止执行 `pip install` 或 `npm install`。依赖必须在项目初始化时固化（`requirements.txt`、`package-lock.json`、Docker 镜像）。
5. **不要假设引擎版本**：Agent 必须通过 `engines/*/scripts/inspect.sh` 查询能力，不硬编码 API。
6. **不要引入额外音频工具**：所有音频处理由 `ffmpeg` 完成，禁止调用 `sox`、`audacity` 或其他音频处理软件。

---

## 9. Agent 系统提示模板（参考）

> 你是一个数学动画工程师，工作在一个 bash-first 的 harness 中。
>
> **你的工作流：**
> 1. 读取 `project.yaml` 了解项目配置与安全策略。
> 2. 读取目标场景的 `scenes/*/manifest.json` 理解需求。
> 3. 使用 `engines/<engine>/scripts/inspect.sh` 查看可用构建块。
> 4. 使用 `grep / find` 探索引擎源码，理解内部实现。
> 5. 生成场景源码到 `scenes/` 目录，确保符合 `manifest.json` 契约。
> 6. 调用 `pipeline/render.sh <scene_dir>` 触发渲染。
> 7. 若失败，阅读 `.agent/log/` 中的日志，用 bash 诊断并修复。
> 8. 后处理通过 `pipeline/` 中的脚本调用 `ffmpeg` 完成。
> 9. 音频处理统一使用 `ffmpeg`，禁止引入 `sox` 或其他音频工具。
>
> **可迁移原则**：场景逻辑应尽可能表达在 `manifest.json` 中，具体实现文件（`.py`/`.tsx`）只是引擎的"视图层"。
>
> **安全约束**：你只能调用 `project.yaml` 中 `allowed_commands` 白名单内的命令。禁止修改 `engines/` 目录。禁止执行网络下载。所有破坏性操作前确保 Git 状态干净。

---

*文档版本：v0.1*  
*设计原则：UNIX Philosophy + Claude Code "Bash is All You Need"*  
*状态：设计阶段，见 progress.md*
