import {makeScene2D} from '@motion-canvas/2d';
import {waitFor} from '@motion-canvas/core';

/**
 * Motion Canvas 基础场景模板。
 *
 * 使用方式：
 *   1. 复制此文件到 scenes/{your_scene}/scene.tsx
 *   2. 修改场景逻辑
 *   3. 确保 manifest.json 中 engine 为 "motion_canvas"
 */
export default makeScene2D(function* (view) {
  // TODO: 在 view 中添加节点并编写动画
  // 示例：
  // const circle = createRef<Circle>();
  // view.add(<Circle ref={circle} width={100} height={100} fill="#e13238" />);
  // yield* circle().scale(2, 1);
  // yield* waitFor(1);
});
