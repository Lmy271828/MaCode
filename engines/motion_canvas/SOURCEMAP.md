# MaCode Engine Source Map: Motion Canvas

> 生成日期: 2026-05-12
> 引擎版本: 3.17.2
> 适配层版本: 1.0.1
> 源码根目录: `node_modules/@motion-canvas/core/lib/`, `node_modules/@motion-canvas/2d/lib/`

## WHITELIST: 推荐探索路径

| 标识 | 路径/命令 | 用途 | 优先级 |
|------|-----------|------|--------|
| CORE_SCENE | `node_modules/@motion-canvas/2d/lib/scenes/makeScene2D.js` | Scene/Scene2D 基类与 makeScene2D 工厂 | P0 |
| CORE_NODE | `node_modules/@motion-canvas/2d/lib/components/Node.js` | 节点树基类（Node, Shape, Layout） | P0 |
| CORE_SHAPES | `node_modules/@motion-canvas/2d/lib/components/` | 几何节点：Circle, Rect, Line, Path, Polygon | P0 |
| CORE_TEXT | `node_modules/@motion-canvas/2d/lib/components/` | 文本节点：Txt, Latex, CodeBlock | P1 |
| CORE_MEDIA | `node_modules/@motion-canvas/2d/lib/components/` | 媒体节点：Img, Video, SVG | P1 |
| CORE_VIEW | `node_modules/@motion-canvas/2d/lib/components/` | 视口节点：Camera, Grid, View2D | P1 |
| FLOW_SEQUENCE | `node_modules/@motion-canvas/core/lib/flow/sequence.js` | 顺序执行动画 | P0 |
| FLOW_ALL | `node_modules/@motion-canvas/core/lib/flow/all.js` | 并行执行动画 | P0 |
| FLOW_DELAY | `node_modules/@motion-canvas/core/lib/flow/delay.js` | 延迟与等待 | P1 |
| FLOW_LOOP | `node_modules/@motion-canvas/core/lib/flow/loop.js` | 循环控制流 | P1 |
| FLOW_CHAIN | `node_modules/@motion-canvas/core/lib/flow/chain.js` | 链式组合 | P1 |
| TWEENING | `node_modules/@motion-canvas/core/lib/tweening/` | 缓动函数与插值 | P1 |
| SIGNALS | `node_modules/@motion-canvas/core/lib/signals/` | 响应式信号系统 | P1 |
| ADAPTER_TEMPLATE | `engines/motion_canvas/src/templates/scene_base.tsx` | MaCode 场景基类模板 | P0 |

## BLACKLIST: 禁止/不建议探索

| 标识 | 路径/命令 | 原因 |
|------|-----------|------|
| INTERNAL_APP | `node_modules/@motion-canvas/core/lib/app/` | 内部渲染管线与播放器，非公开 API |
| INTERNAL_PLUGIN | `node_modules/@motion-canvas/core/lib/plugin/` | 插件系统内部实现 |
| INTERNAL_META | `node_modules/@motion-canvas/core/lib/meta/` | 元数据序列化，非 API 表面 |
| INTERNAL_RENDERER | `node_modules/@motion-canvas/2d/lib/curves/` | 曲线渲染内部实现 |
| INTERNAL_EDITOR | `node_modules/@motion-canvas/2d/src/editor/` | 编辑器内部组件 |
| INTERNAL_SRC | `node_modules/@motion-canvas/2d/src/lib/curves/` | 曲线渲染内部数学实现 |
| TEST_SUITE | `node_modules/@motion-canvas/*/src/**/__tests__/` | 测试代码，非 API |
| VENV_DIR | `.venv/` | Python 虚拟环境，非 JS 引擎目录 |
| BUILD_ARTIFACT | `.agent/tmp/` | 中间产物，非源码 |
| DIRECT_EVAL | `eval(` | Arbitrary code execution in browser/Node |
| DIRECT_EVAL_FUNCTION | `new Function(` | Arbitrary code execution in browser/Node |
| FETCH_API | `fetch(` | Network requests break reproducibility |
| FETCH_API_XHR | `XMLHttpRequest` | Network requests break reproducibility |
| WEBSOCKET | `WebSocket` | Raw network socket access |
| DOM_WRITE | `document.write` | DOM access breaks Playwright screenshot consistency |
| DOM_LOCATION | `document.location` | Navigation breaks Playwright screenshot consistency |
| WINDOW_LOCATION | `window.location` | Navigation breaks Playwright screenshot consistency |
| PROCESS_EXIT | `process.exit(` | Premature Node.js termination |
| CHILD_PROCESS | `child_process` | Arbitrary command execution in Node |
| BYPASS_BROWSER_POOL_PUPPETEER | `puppeteer-core` | Bypass managed browser lifecycle |
| BYPASS_BROWSER_POOL_PLAYWRIGHT | `playwright-core` | Bypass managed browser lifecycle |

## EXTENSION: 待补充/可添加

| 标识 | 描述 | 状态 |
|------|------|------|
| HEADLESS_RENDER | 纯 Node.js 无头渲染（canvas + jsdom） | DONE |
| SHADER_NODES | `engines/motion_canvas/src/components/ShaderFrame.tsx` — 自定义 WebGL 着色器节点 | DONE |
| AUDIO_SYNC | 音频波形驱动的动画同步 | DONE |
| LIVE_PREVIEW | WebSocket 热重载实时预览 | WONTFIX |

## REDIRECT: Common Pitfall Corrections

When you find yourself writing the left column, use the right column instead.

| Pitfall | Correct Approach | Reason |
|---------|-----------------|--------|
| Hand-write `gl_Position = ...` | `utils.shader_builder.Shader().node(...)` | GLSL compile errors decoupled from causes |
| Use `fetch()` for external data | Pre-load data into `assets/` and import statically | Network requests in scene code break reproducibility |
| Use `eval()` or `new Function()` | Use static imports and MaCode helper functions | Arbitrary execution bypasses sandbox |
| Direct `document.*` manipulation | Use Motion Canvas Node API (`<Node>`, `<Txt>`, etc.) | DOM access breaks Playwright screenshot consistency |
| Import `puppeteer-core` or `playwright-core` directly | Use `macode mc serve` + `playwright-render.mjs` | Browser pool manages lifecycle and isolation |
