import {makeScene2D} from '@motion-canvas/2d';
import {Txt} from '@motion-canvas/2d';
import {createRef} from '@motion-canvas/core';

// @segment:formula
// @time:0.0-4.0s
// @keyframes:[0.0, 2.0, 4.0]
// @description:Formula derivation step by step
// @description:Motion Canvas shot
export default makeScene2D(function* (view) {
  const formula1 = createRef<Txt>();
  const formula2 = createRef<Txt>();
  const edgeLabel = createRef<Txt>();

  view.fill('#1a1a1a');

  view.add(
    <>
      <Txt
        ref={formula1}
        text="a² + b² = c²"
        fontSize={72}
        fill="white"
        x={0}
        y={-80}
        opacity={0}
      />
      <Txt
        ref={formula2}
        text="c = √(a² + b²)"
        fontSize={72}
        fill="white"
        x={0}
        y={50}
        opacity={0}
      />
      <Txt
        ref={edgeLabel}
        text="Pythagorean Theorem"
        fontSize={48}
        fill="yellow"
        x={600}
        y={200}
        opacity={0}
      />
    </>,
  );

  // Step 1: show original formula
  yield* formula1().opacity(1, 1.0);

  // Step 2: show derived formula (B1: only 20px gap from formula1)
  yield* formula2().opacity(1, 1.0);

  // Step 3: show edge label (B2: x=900 near right edge)
  yield* edgeLabel().opacity(1, 2.0);
});
