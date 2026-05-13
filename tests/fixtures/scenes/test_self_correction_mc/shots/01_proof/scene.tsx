import {makeScene2D} from '@motion-canvas/2d';
import {Rect, Txt, Line} from '@motion-canvas/2d';
import {createRef} from '@motion-canvas/core';

// @segment:proof
// @time:0.0-3.0s
// @keyframes:[0.0, 2.0, 3.0]
// @description:Geometric proof with squares and triangles
// @description:Motion Canvas shot
export default makeScene2D(function* (view) {
  // Triangle vertices (right triangle)
  const A = [-200, 100];
  const B = [100, 100];
  const C = [-200, -200];

  // Refs
  const triangle = createRef<Line>();
  const squareA = createRef<Rect>();
  const squareB = createRef<Rect>();
  const squareC = createRef<Rect>();
  const labelA = createRef<Txt>();
  const labelB = createRef<Txt>();
  const labelC = createRef<Txt>();
  const title = createRef<Txt>();

  // Title
  view.add(
    <Txt
      ref={title}
      text="Pythagorean Theorem"
      fill="#ffffff"
      fontSize={48}
      y={-400}
      opacity={0}
    />
  );

  // Right triangle
  view.add(
    <Line
      ref={triangle}
      points={[A, B, C, A]}
      stroke="#ffffff"
      lineWidth={6}
      end={0}
    />
  );

  // Square on horizontal leg (a)
  view.add(
    <Rect
      ref={squareA}
      width={300}
      height={300}
      fill="#58c4dc"
      opacity={0.6}
      x={-50}
      y={250}
      scale={0}
    />
  );

  // Square on vertical leg (b)
  view.add(
    <Rect
      ref={squareB}
      width={300}
      height={300}
      fill="#e06c75"
      opacity={0.6}
      x={-350}
      y={-50}
      scale={0}
    />
  );

  // Square on hypotenuse (c)
  view.add(
    <Rect
      ref={squareC}
      width={424}
      height={424}
      fill="#98c379"
      opacity={0.6}
      x={150}
      y={-150}
      scale={0}
      rotation={45}
    />
  );

  // Labels
  view.add(
    <Txt ref={labelA} text="a²" fill="#58c4dc" fontSize={64} x={-50} y={250} opacity={0} />
  );
  view.add(
    <Txt ref={labelB} text="b²" fill="#e06c75" fontSize={64} x={-350} y={-50} opacity={0} />
  );
  view.add(
    <Txt ref={labelC} text="c²" fill="#98c379" fontSize={64} x={150} y={-150} opacity={0} />
  );

  // INJECT A1: total yield* durations ~5.0s while manifest says 3.0s
  yield* title().opacity(1, 0.8);
  yield* waitFor(0.5);

  yield* triangle().end(1, 1.0);
  yield* waitFor(0.5);

  yield* squareA().scale(1, 1.0);
  yield* labelA().opacity(1, 0.5);
  yield* waitFor(0.5);

  yield* squareB().scale(1, 1.0);
  yield* labelB().opacity(1, 0.5);
  yield* waitFor(0.5);

  yield* squareC().scale(1, 1.0);
  yield* labelC().opacity(1, 0.5);
  yield* waitFor(1.0);
});
