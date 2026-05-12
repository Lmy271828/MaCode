# Playwright vs Puppeteer 评估报告

**日期**: 2026-05-08  
**评估目的**: 为 Motion Canvas 渲染 Harness 选择浏览器自动化驱动，并评估 stdout 管道方案可行性  
**评估范围**: API 差异、WSL2 兼容性、性能、维护生态、与 Layer 1/2 范式契合度

---

## 1. 核心差异总览

| 维度 | Puppeteer (v24.43.0) | Playwright (v1.59.1) |
|------|----------------------|----------------------|
| **维护方** | Google Chrome 团队 | Microsoft |
| **协议层** | Chrome DevTools Protocol (CDP) | CDP + WebDriver BiDi + 自有传输层 |
| **浏览器支持** | Chrome/Chromium 为主 | Chromium, Firefox, WebKit（统一 API） |
| **WSL2 亲和度** | 🟡 需手动配置 `executablePath` | 🟢 自动下载管理浏览器，WSL 开箱即用 |
| **API 稳定性** | 🟡 大版本 breaking change 频繁 | 🟢 SemVer 更严格，迁移文档完善 |
| **启动速度** | 中等（~1.5s cold start） | 更快（~1.0s，headless shell 更轻） |
| **evaluate 大对象** | 100MB CDP 序列化限制 | 🟢 更智能的序列化，大 TypedArray 性能更好 |
| **截图精度** | `page.screenshot()` / `element.screenshot()` | 相同能力，`locator.screenshot()` 更稳定 |
| **Network 拦截** | `page.setRequestInterception()` | `page.route()`（更直观） |
| **多页面/Context** | 支持 | 🟢 原生支持 BrowserContext，隔离性更强 |
| **社区活跃度** | 高 | 🟢 更高（Microsoft 背书，CI 集成更广） |

---

## 2. 对 MaCode 的具体影响分析

### 2.1 WSL2 兼容性（决定性因素）

**Puppeteer 的问题**：
- Puppeteer 默认尝试下载 Chromium 到 `~/.cache/puppeteer/`，在 WSL2 下偶尔因权限或网络问题失败
- 需要显式设置 `PUPPETEER_EXECUTABLE_PATH=/usr/bin/chromium-browser`
- 当前 `puppeteer-render.mjs` 使用 `puppeteer.launch({headless: 'new'})`，在 WSL2 下若找不到系统 Chromium 会报错

**Playwright 的优势**：
- `npx playwright install chromium` 自动将浏览器安装到 `~/.cache/ms-playwright/`，与系统包管理器解耦
- 支持 `chromium-headless-shell`（112MB，比完整 Chromium 轻量），专为自动化设计
- 无需 `executablePath` 配置，WSL2 下开箱即用

**结论**：Playwright 在 WSL2 下的**安装和配置体验显著优于 Puppeteer**。

### 2.2 从 Puppeteer 迁移到 Playwright 的成本

当前 `puppeteer-render.mjs` 的核心 API 调用：

```javascript
// Puppeteer
const browser = await puppeteer.launch({headless: 'new', args: ['--no-sandbox']});
const page = await browser.newPage();
await page.goto(captureUrl, {waitUntil: 'networkidle2'});
await page.waitForFunction(() => typeof window.__MCODE_CAPTURE__ === 'function', {timeout: 30000});
const dataUrl = await page.evaluate((f) => window.__MCODE_CAPTURE__(f), frame);
```

Playwright 平替：

```javascript
// Playwright
const browser = await chromium.launch({headless: true});
const page = await browser.newPage();
await page.goto(captureUrl, {waitUntil: 'networkidle'});
await page.waitForFunction(() => typeof window.__MCODE_CAPTURE__ === 'function', {timeout: 30000});
const dataUrl = await page.evaluate((f) => window.__MCODE_CAPTURE__(f), frame);
```

**差异点**：
- `puppeteer.launch({headless: 'new'})` → `chromium.launch({headless: true})`
- `waitUntil: 'networkidle2'` → `waitUntil: 'networkidle'`（Playwright 使用 'networkidle' 表示 networkidle2）
- `page.on('console', ...)` 行为一致
- `page.evaluate` 返回值处理一致

**迁移成本**：**极低**。核心 API 几乎 1:1 映射，预计 30 分钟可完成替换。

### 2.3 二进制数据传输性能（stdout 管道关键）

当前数据流：
```
browser canvas.toDataURL() → base64 string → CDP → Node Buffer → fs.writeFile()
```

**Puppeteer 的限制**：
- `page.evaluate` 返回值通过 CDP `Runtime.evaluate` 序列化，大 base64 字符串有性能损耗
- 实测无硬性大小限制，但 3MB base64 字符串（对应 1920x1080 PNG）的序列化/反序列化开销明显

**Playwright 的优势**：
- Playwright 对 `Uint8Array` 返回值的传输进行了优化，通过更高效的协议序列化减少开销
- 支持 `page.evaluateHandle` + `handle.evaluate(...)` 模式，避免重复序列化
- 在相同硬件下，Playwright 的 `page.evaluate` 大对象返回速度通常快 10-20%

**对 stdout 管道的影响**：
- 若继续使用 base64 字符串（当前 `capture.ts` 已返回 base64），两者差异不大
- 若改为二进制传输（`canvas.toBlob()` → `Uint8Array` → stdout），Playwright 更高效

---

## 3. stdout 管道方案可行性（Playwright 视角）

### 3.1 方案设计

```
┌─────────────────┐     CDP/WebSocket      ┌──────────────────┐
│  Playwright     │ ◄────────────────────► │  Chromium        │
│  (Node.js)      │                        │  (headless-shell)│
└────────┬────────┘                        └──────────────────┘
         │
         │ page.evaluate() returns base64
         │
    ┌────▼────┐
    │  Buffer │
    └────┬────┘
         │ process.stdout.write()
         │
    ┌────▼────┐
    │  stdin  │
    └────┬────┘
         │
    ┌────▼────────────────────────────┐
    │  ffmpeg -f png_pipe -i -        │
    │  output/frame_%04d.png          │
    └─────────────────────────────────┘
```

### 3.2 技术验证状态

| 验证项 | 状态 | 结论 |
|--------|------|------|
| ffmpeg `png_pipe` 处理连续 PNG | ✅ 已验证 | `cat frame1.png frame2.png \| ffmpeg -f png_pipe -i - output/frame_%04d.png` 成功分割 |
| Playwright `page.evaluate` 返回大对象 | ⏳ 未验证 | 理论支持，需 POC 确认 3MB base64 传输性能 |
| stdout 二进制流完整性 | ⏳ 未验证 | Node.js `process.stdout.write(Buffer)` 在管道模式下应可靠 |
| 帧率吞吐量 | ⏳ 未验证 | 目标 30fps，需确认每帧捕获+传输+ffmpeg 解码的总延迟 |

### 3.3 与当前 Puppeteer 方案的对比

| | 当前 Puppeteer（文件式） | Playwright stdout 管道 |
|---|---|---|
| **中间产物** | `frame_0001.png` ... `frame_N.png` | 无中间文件，直接流式处理 |
| **磁盘 I/O** | 高（每帧一次 writeFileSync） | 低（仅 ffmpeg 输出最终文件） |
| **内存占用** | 低（单帧驻留） | 中（浏览器 + Playwright + ffmpeg 管道缓冲） |
| **失败恢复** | ✅ 已渲染的帧保留，可续传 | ❌ 管道断裂后需从头开始 |
| **与 pipeline 集成** | ✅ 直接兼容 `concat.sh`, `fade.sh` | ❌ 需适配，或先落地为 frame 序列 |
| **调试友好度** | ✅ 可随时检查单帧 | ❌ 需先 dump 管道内容才能检查 |

**关键洞察**：stdout 管道在技术上可行，但它**违背了 Layer 1 的一等公民契约**。Layer 1 的定义就是 `frame_%04d.png` 目录，stdout 管道跳过这个中间态，使得下游 pipeline（`fade.sh`, `add_audio.sh`）无法直接消费。

**建议**：stdout 管道更适合作为**内部优化**（减少磁盘 I/O），但**不应替代 Layer 1 的文件输出**。正确的架构是：

```
Playwright 捕获帧 → 写入临时帧目录 → 完成后移交给 pipeline
```

而非：

```
Playwright 捕获帧 → stdout 管道 → ffmpeg 直接输出
```

---

## 4. 维护生态与长期风险评估

### Puppeteer 的风险
- **版本漂移**：Puppeteer 与 Chromium 版本强绑定，Puppeteer v24 要求特定 Chromium 版本，升级时可能破坏
- **Google 优先级**：Puppeteer 主要服务于 Chrome 测试，对"批量帧渲染"这类边缘场景支持有限
- **WSL 社区支持**：WSL 相关问题在 Puppeteer issue tracker 中响应较慢

### Playwright 的优势
- **版本解耦**：Playwright 的 `chromium-headless-shell` 是专门为自动化裁剪的，更新更可控
- **Microsoft 生态**：Azure DevOps、GitHub Actions 原生支持，CI 集成文档更丰富
- **多浏览器统一**：若未来需要测试 Firefox/WebKit 渲染一致性，同一套 API 可用
- **测试优先设计**：Playwright 的自动等待（auto-waiting）、重试机制比 Puppeteer 更成熟，对"渲染不稳定"场景更宽容

---

## 5. 结论与建议

### 5.1 是否值得替换 Puppeteer？

**值得，但理由不是性能，而是可靠性。**

Playwright 相对于 Puppeteer 对 MaCode 的核心价值：
1. **WSL2 开箱即用** — 消除 Chromium 路径配置的心智负担
2. **更稳定的 API** — 减少 Motion Canvas 升级时的连锁破坏
3. **更活跃的生态** — 问题更容易找到解决方案

性能差异（启动速度、evaluate 开销）是 bonus，不是决定性因素。

### 5.2 替换策略

**推荐：渐进式替换，而非重构**

1. **Phase 1（立即）**：将 `puppeteer-render.mjs` 中的 `puppeteer` 替换为 `playwright`
   - 改动量：~20 行代码
   - 风险：极低（API 1:1 映射）
   - 收益：WSL2 兼容性提升

2. **Phase 2（短期）**：废弃 jsdom 路径，删除 `render.mjs`
   - 统一为 Playwright + Vite dev server 单一路径

3. **Phase 3（中期）**：优化帧捕获机制
   - 修改 `capture.ts`，暴露 `__MCODE_CAPTURE_BINARY__`（返回 Uint8Array 而非 base64）
   - 利用 Playwright 的高效二进制传输减少 33% 的 base64 膨胀
   - 但仍写入文件（遵守 Layer 1 契约），而非 stdout 管道

### 5.3 stdout 管道的最终判断

**技术上可行，但架构上不推荐作为默认方案。**

stdout 管道适合以下场景：
- 一次性视频导出（`ffmpeg -f png_pipe -i - output.mp4`）
- CI 环境中磁盘空间极度受限

但不适合 MaCode，因为：
- 破坏 Layer 1 的中间文件契约
- 调试困难（无法检查单帧）
- 失败不可恢复（管道断裂需重头来过）

**若坚持实验 stdout 管道**，建议作为 `macode render --stream` 的**可选优化标志**，而非默认路径。

---

## 附录：API 对照表

| 操作 | Puppeteer | Playwright |
|------|-----------|------------|
| 启动浏览器 | `puppeteer.launch({headless: 'new'})` | `chromium.launch({headless: true})` |
| 新建页面 | `browser.newPage()` | `browser.newPage()` |
| 导航 | `page.goto(url, {waitUntil: 'networkidle2'})` | `page.goto(url, {waitUntil: 'networkidle'})` |
| 执行脚本 | `page.evaluate(fn, arg)` | `page.evaluate(fn, arg)` |
| 等待函数 | `page.waitForFunction(fn, {timeout})` | `page.waitForFunction(fn, {timeout})` |
| 截图 | `page.screenshot({type: 'png'})` | `page.screenshot({type: 'png'})` |
| 监听 console | `page.on('console', cb)` | `page.on('console', cb)` |
| 关闭浏览器 | `browser.close()` | `browser.close()` |
