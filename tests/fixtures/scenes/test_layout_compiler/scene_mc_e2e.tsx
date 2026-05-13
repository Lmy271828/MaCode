/**
 * Auto-generated scene from layout_config.yaml.
 * Layout: lecture_3zones | Narrative: definition_reveal
 */

import {makeScene2D} from '@motion-canvas/2d';
import {Txt, Circle, Rect, Line, Latex} from '@motion-canvas/2d';
import {createRef, waitFor} from '@motion-canvas/core';

export default makeScene2D(function* (view) {
  // Stage: statement (zone: title, type: text)
  const statement_ref = createRef<Txt>();
  view.add(<Txt ref={statement_ref} text="Hi" fontSize={48} fill="white" />);
  yield* waitFor(2.0);

  // Stage: visual (zone: main_visual, type: visual)
  const visual_0_ref = createRef<Circle>();
  const visual_1_ref = createRef<Rect>();
  const visual_2_ref = createRef<Circle>();
  const visual_3_ref = createRef<Circle>();
  const visual_4_ref = createRef<Line>();
  view.add(<Circle ref={visual_0_ref} width={50.0} height={50.0} fill="white" lineWidth={2} />);
  view.add(<Rect ref={visual_1_ref} width={100} height={100} fill="white" lineWidth={2} />);
  view.add(<Circle ref={visual_2_ref} width={50.0} height={50.0} fill="white" lineWidth={2} />);
  view.add(<Circle ref={visual_3_ref} width={50.0} height={50.0} fill="white" lineWidth={2} />);
  view.add(<Line ref={visual_4_ref} points={[[-100, 0], [100, 0]]} stroke="white" lineWidth={{4}} />);
  yield* waitFor(4.0);

  // Stage: annotation (zone: annotation, type: text)
  // TODO: No content allocated for stage 'annotation'
  yield* waitFor(3.0);

  // Stage: example (zone: main_visual, type: visual)
  // TODO: No content allocated for stage 'example'
  yield* waitFor(3.0);
});
