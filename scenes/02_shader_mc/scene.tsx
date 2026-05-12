import {makeScene2D} from '@motion-canvas/2d';
import {Circle, Txt} from '@motion-canvas/2d';
import {createRef, waitFor} from '@motion-canvas/core';
import {ShaderFrame} from '../../engines/motion_canvas/src/components/ShaderFrame';

/**
 * Motion Canvas + Shader Pipeline bridge test.
 *
 * Background: LYGIA circle + heatmap shader (pre-rendered Layer 1 frames)
 * Foreground: Motion Canvas native Circle + Txt
 */
export default makeScene2D(function* (view) {
  const circle = createRef<Circle>();
  const label = createRef<Txt>();

  view.add(
    <ShaderFrame
      effect="lygia_circle_heatmap"
      width={1920}
      height={1080}
      fps={30}
    />
  );

  view.add(
    <Circle
      ref={circle}
      width={200}
      height={200}
      fill="#e13238"
      x={0}
      y={0}
    />
  );

  view.add(
    <Txt
      ref={label}
      text="Motion Canvas + LYGIA Shader"
      fill="#ffffff"
      fontSize={64}
      y={300}
    />
  );

  yield* circle().scale(2, 1.5);
  yield* waitFor(1.5);
});
