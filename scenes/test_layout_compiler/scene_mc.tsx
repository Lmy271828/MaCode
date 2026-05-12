/**
 * Auto-generated scene from layout_config.yaml.
 * Layout: lecture_3zones | Narrative: definition_reveal
 */

import {makeScene2D} from '@motion-canvas/2d';
import {Txt, Circle, Rect, Line, Latex} from '@motion-canvas/2d';
import {createRef, waitFor} from '@motion-canvas/core';

export default makeScene2D(function* (view) {
  // Stage: statement (zone: title, type: text)
  const statement_0_ref = createRef<Txt>();
  const statement_1_ref = createRef<Latex>();
  view.add(<Txt ref={statement_0_ref} text="极限的定义" fontSize={48} fill="white" />);
  view.add(<Latex ref={statement_1_ref} tex="\lim_{x \to a} f(x) = L" fontSize={36} fill="white" />);
  yield* waitFor(2.0);

  // Stage: visual (zone: main_visual, type: visual)
  const visual_ref = createRef<Line>();
  view.add(<Line ref={visual_ref} points={[[-400, 0], [400, 0]]} stroke="white" lineWidth={4} />);
  yield* waitFor(4.0);

  // Stage: annotation (zone: annotation, type: text)
  const annotation_ref = createRef<Txt>();
  view.add(<Txt ref={annotation_ref} text="对于任意 \\epsilon > 0，存在 \\delta > 0..." fontSize={48} fill="white" />);
  yield* waitFor(3.0);

  // Stage: example (zone: main_visual, type: visual)
  // TODO: No content allocated for stage 'example'
  yield* waitFor(3.0);
});
