import {makeScene2D} from '@motion-canvas/2d';
import {Txt, Circle} from '@motion-canvas/2d';
import {createRef} from '@motion-canvas/core';

/**
 * Motion Canvas Intro Segment
 */
export default makeScene2D(function* (view) {
  const title = createRef<Txt>();
  const circle = createRef<Circle>();

  // Read injected params from window (set by render.mjs from MACODE_PARAMS_JSON)
  const params = (typeof window !== 'undefined' && (window as any).__MACODE_PARAMS) || {};
  const titleText = params.title_text || 'Motion Canvas';
  const themeColor = params.theme_color || '#58c4dc';

  view.add(
    <>
      <Circle
        ref={circle}
        width={200}
        height={200}
        fill={themeColor}
        x={0}
        y={-100}
      />
      <Txt
        ref={title}
        text={titleText}
        fontSize={64}
        fill="white"
        y={120}
      />
    </>
  );

  yield* circle().scale(1.5, 0.8);
  yield* circle().scale(1, 0.7);
});
