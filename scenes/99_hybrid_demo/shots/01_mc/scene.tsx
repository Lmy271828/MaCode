import {makeScene2D} from '@motion-canvas/2d';
import {Circle, Txt} from '@motion-canvas/2d';
import {createRef} from '@motion-canvas/core';

export default makeScene2D(function* (view) {
  const circle = createRef<Circle>();
  const text = createRef<Txt>();

  view.add(
    <>
      <Circle
        ref={circle}
        width={300}
        height={300}
        fill="#e74c3c"
        x={200}
        y={-100}
      />
      <Txt
        ref={text}
        text="MC Hybrid"
        fill="#ffffff"
        fontSize={64}
        x={-200}
        y={100}
      />
    </>
  );

  yield* circle().scale(1.2, 2);
});
