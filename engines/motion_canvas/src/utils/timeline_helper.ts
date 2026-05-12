/**
 * engines/motion_canvas/src/utils/timeline_helper.ts
 * MaCode keyframe / timeline builder — TypeScript version.
 *
 * Provides interpolation and export for animation parameters.
 *
 * Usage:
 *   import {Timeline, Keyframe} from '../utils/timeline_helper';
 *
 *   const timeline = new Timeline();
 *   timeline.add(new Keyframe({t: 0.0, value: 0, ease: 'linear'}));
 *   timeline.add(new Keyframe({t: 1.0, value: 1, ease: 'ease_in_out'}));
 *   timeline.add(new Keyframe({t: 3.0, value: 0.5, ease: 'ease_out'}));
 *
 *   const v = timeline.at(1.5);   // interpolated result
 *
 *   // Export CSV (for external tools like ffmpeg)
 *   timeline.toCsv('keyframes.csv', 30);
 */

import * as fs from 'fs';

// ------------------------------------------------------------------
// 1. Easing functions
// ------------------------------------------------------------------

function easeLinear(t: number): number {
  return t;
}

function easeIn(t: number): number {
  return t * t;
}

function easeOut(t: number): number {
  return 1 - (1 - t) * (1 - t);
}

function easeInOut(t: number): number {
  if (t < 0.5) {
    return 2 * t * t;
  }
  return 1 - Math.pow(-2 * t + 2, 2) / 2;
}

function easeStep(t: number): number {
  return t < 1.0 ? 0.0 : 1.0;
}

const EASING_MAP: Record<string, (t: number) => number> = {
  linear: easeLinear,
  ease_in: easeIn,
  ease_out: easeOut,
  ease_in_out: easeInOut,
  step: easeStep,
};

function interpolate(a: number, b: number, t: number): number {
  return a + (b - a) * t;
}

// ------------------------------------------------------------------
// 2. Keyframe
// ------------------------------------------------------------------

export interface KeyframeOptions {
  t: number;
  value: number;
  ease?: string;
}

export class Keyframe {
  readonly t: number;
  readonly value: number;
  readonly ease: string;

  constructor(options: KeyframeOptions) {
    this.t = options.t;
    this.value = options.value;
    this.ease = options.ease ?? 'linear';
    if (!EASING_MAP[this.ease]) {
      throw new Error(
        `Unknown ease '${this.ease}'. Supported: ${Object.keys(EASING_MAP).join(', ')}`
      );
    }
  }
}

// ------------------------------------------------------------------
// 3. Timeline
// ------------------------------------------------------------------

export class Timeline {
  private frames: Keyframe[] = [];

  /** Add keyframe and auto-sort by time. Supports chaining. */
  add(keyframe: Keyframe): Timeline {
    this.frames.push(keyframe);
    this.frames.sort((a, b) => a.t - b.t);
    return this;
  }

  /** Clear all keyframes. */
  clear(): Timeline {
    this.frames = [];
    return this;
  }

  /**
   * Sample interpolated value at time t.
   *
   * - If t is before the first frame, returns first frame's value.
   * - If t is after the last frame, returns last frame's value.
   * - Otherwise interpolates between two frames using easing function.
   */
  at(t: number): number {
    if (this.frames.length === 0) {
      return 0.0;
    }

    if (t <= this.frames[0].t) {
      return this.frames[0].value;
    }
    if (t >= this.frames[this.frames.length - 1].t) {
      return this.frames[this.frames.length - 1].value;
    }

    for (let i = 0; i < this.frames.length - 1; i++) {
      const k0 = this.frames[i];
      const k1 = this.frames[i + 1];
      if (k0.t <= t && t <= k1.t) {
        if (k1.t === k0.t) {
          return k1.value;
        }
        const localT = (t - k0.t) / (k1.t - k0.t);
        const easedT = EASING_MAP[k0.ease](localT);
        return interpolate(k0.value, k1.value, easedT);
      }
    }

    // Fallback
    return this.frames[this.frames.length - 1].value;
  }

  /**
   * Sample timeline into CSV file.
   *
   * @param path - Output file path
   * @param fps - Sample frame rate
   * @param endT - End time; defaults to last keyframe's time
   */
  toCsv(path: string, fps = 30, endT?: number): void {
    if (this.frames.length === 0) {
      return;
    }

    const duration = endT ?? this.frames[this.frames.length - 1].t;
    const frameCount = Math.max(1, Math.ceil(duration * fps) + 1);

    const lines: string[] = ['frame,time,value'];
    for (let i = 0; i < frameCount; i++) {
      const t = i / fps;
      lines.push(`${i},${t.toFixed(6)},${this.at(t).toFixed(6)}`);
    }

    fs.writeFileSync(path, lines.join('\n'), 'utf-8');
  }

  get length(): number {
    return this.frames.length;
  }

  toString(): string {
    const frames = this.frames
      .map((k) => `(${k.t}, ${k.value}, ${k.ease})`)
      .join(', ');
    return `Timeline([${frames}])`;
  }
}
