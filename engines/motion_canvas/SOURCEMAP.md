# MaCode Engine Source Map: Motion Canvas

> 生成日期: 2026-05-04
> 引擎版本: 3.17.2 (via npm ls @motion-canvas/core)
> 适配层版本: 1.0.0

## WHITELIST: 推荐探索路径

| 标识 | 路径/命令 | 用途 | 优先级 |
|------|-----------|------|--------|
| CORE_SCENE2D | `node_modules/@motion-canvas/2d/lib/scenes/Scene2D.js` | 2D 场景基类 | P0 |
| CORE_MAKESCENE2D | `node_modules/@motion-canvas/2d/lib/scenes/makeScene2D.js` | makeScene2D 工厂函数，generator 入口 | P0 |
| CORE_NODE | `node_modules/@motion-canvas/2d/lib/components/Node.js` | 所有节点的基类 | P0 |
| CORE_SHAPE | `node_modules/@motion-canvas/2d/lib/components/Shape.js` | 形状抽象基类 | P0 |
| CORE_LAYOUT | `node_modules/@motion-canvas/2d/lib/components/Layout.js` | Flexbox 布局容器 | P0 |
| CORE_CIRCLE | `node_modules/@motion-canvas/2d/lib/components/Circle.js` | 圆形节点 | P0 |
| CORE_LINE | `node_modules/@motion-canvas/2d/lib/components/Line.js` | 线段节点 | P0 |
| CORE_RECT | `node_modules/@motion-canvas/2d/lib/components/Rect.js` | 矩形节点（@motion-canvas/2d） | P0 |
| CORE_TXT | `node_modules/@motion-canvas/2d/lib/components/Txt.js` | 带样式的文本节点 | P1 |
| CORE_LATEX | `node_modules/@motion-canvas/2d/lib/components/Latex.js` | LaTeX 公式节点 | P1 |
| CORE_IMG | `node_modules/@motion-canvas/2d/lib/components/Img.js` | 图片节点 | P1 |
| CORE_VIDEO | `node_modules/@motion-canvas/2d/lib/components/Video.js` | 视频节点 | P1 |
| CORE_SVG | `node_modules/@motion-canvas/2d/lib/components/SVG.js` | SVG 矢量节点 | P1 |
| CORE_CAMERA | `node_modules/@motion-canvas/2d/lib/components/Camera.js` | 2D 相机控制 | P1 |
| CORE_GRID | `node_modules/@motion-canvas/2d/lib/components/Grid.js` | 网格参考线 | P1 |
| FLOW_SEQUENCE | `node_modules/@motion-canvas/core/lib/flow/sequence.js` | 顺序执行动画 | P0 |
| FLOW_LOOP | `node_modules/@motion-canvas/core/lib/flow/loop.js` | 循环控制流 | P1 |
| FLOW_DELAY | `node_modules/@motion-canvas/core/lib/flow/delay.js` | 延迟与等待 | P1 |
| ADAPTER_TEMPLATE | `engines/motion_canvas/src/templates/scene_base.tsx` | MaCode 场景基类模板 | P0 |

## BLACKLIST: 禁止/不建议探索

| 标识 | 路径/命令 | 原因 |
|------|-----------|------|
| INTERNAL_RENDERER | `node_modules/@motion-canvas/core/lib/app/` | 内部渲染管线，非公开 API |
| INTERNAL_PLUGIN | `node_modules/@motion-canvas/core/lib/plugin/` | 插件系统内部实现 |
| INTERNAL_META | `node_modules/@motion-canvas/core/lib/meta/` | 元数据序列化，非 API 表面 |
| NODE_MODULES_CACHE | `node_modules/.cache/` | 构建缓存，非源码 |
| BUILD_OUTPUT | `node_modules/@motion-canvas/*/lib/` | 编译产物（通过 types 查阅即可） |
| TEST_SUITE | `node_modules/@motion-canvas/*/__tests__/` | 测试代码，非 API |
| VENV_DIR | `.venv/` | Python 虚拟环境，非 JS 引擎目录 |
| BUILD_ARTIFACT | `.agent/tmp/` | 中间产物，非源码 |

## EXTENSION: 待补充/可添加

| 标识 | 描述 | 状态 |
|------|------|------|
| HEADLESS_RENDER | 纯 Node.js 无头渲染（canvas + jsdom） | TODO |
| SHADER_NODES | 自定义 WebGL 着色器节点 | TODO |
| AUDIO_SYNC | 音频波形驱动的动画同步 | TODO |
| LIVE_PREVIEW | WebSocket 热重载实时预览 | WONTFIX |
