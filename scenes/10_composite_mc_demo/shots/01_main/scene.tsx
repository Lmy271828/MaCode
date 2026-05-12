import {makeScene2D} from '@motion-canvas/2d';
import {Rect, Txt} from '@motion-canvas/2d';
import {createRef} from '@motion-canvas/core';

/**
 * Motion Canvas Main Segment
 */
export default makeScene2D(function* (view) {
  const rect = createRef<Rect>();
  const label = createRef<Txt>();

  view.add(
    <>
      <Rect
        ref={rect}
        width={400}
        height={200}
        fill="#e76f51"
        radius={20}
        x={-300}
      />
      <Txt
        ref={label}
        text="Main Content"
        fontSize={48}
        fill="white"
        x={200}
      />
    </>
  );

  yield* rect().position.x(300, 1.5);
  yield* label().scale(1.2, 0.5);
  yield* label().scale(1, 0.5);
});
