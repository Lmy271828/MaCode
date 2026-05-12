import {makeScene2D, Txt, Layout} from '@motion-canvas/2d';
import {createRef, waitFor} from '@motion-canvas/core';

/**
 * Motion Canvas Intro Segment
 */
// @segment:intro
// @time:0.0-2.5s
// @keyframes:[0.0, 1.5, 2.5]
// @description:Pythagorean theorem title card
// @description:Motion Canvas shot
export default makeScene2D(function* (view) {
  const title = createRef<Txt>();
  const formula = createRef<Txt>();

  view.add(
    <Layout direction="column" gap={40} layout>
      <Txt
        ref={title}
        text="Pythagorean Theorem"
        fontSize={80}
        fill="white"
        opacity={0}
        scale={0.8}
      />
      <Txt
        ref={formula}
        text="a² + b² = c²"
        fontSize={64}
        fill="white"
        opacity={0}
      />
    </Layout>
  );

  // Title fades in and scales up
  yield* title().opacity(1, 0.6);
  yield* title().scale(1, 0.5);

  // Formula fades in
  yield* formula().opacity(1, 0.8);

  // Hold before end
  yield* waitFor(0.6);
});
