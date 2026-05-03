import {makeScene2D} from '@motion-canvas/2d';
import {Circle} from '@motion-canvas/2d';
import {createRef} from '@motion-canvas/core';

/**
 * Phase 2 迁移示例：与 scenes/01_test/scene.py 等价的 Motion Canvas 场景。
 *
 * 原 Manim 场景：画一个圆，持续 3 秒。
 * 迁移改动：
 *   1. manifest.json 中 engine 改为 "motion_canvas"
 *   2. scene.py 改为 scene.tsx，使用 Motion Canvas API
 */
export default makeScene2D(function* (view) {
  const circle = createRef<Circle>();

  view.add(
    <Circle
      ref={circle}
      width={400}
      height={400}
      fill="#58c4dc"
      x={0}
      y={0}
    />
  );

  // 3 秒的缩放动画，与 Manim 版本的 Create(Circle, run_time=3) 等价
  yield* circle().scale(1, 3);
});
