/**
 * engines/motion_canvas/src/utils/audio_sync.ts
 * MaCode AudioSync 适配层 — Motion Canvas 版本。
 *
 * 读取 pipeline/audio-analyze.sh 生成的 timeline.csv，
 * 提供时间查询接口，让场景动画与音乐节拍同步。
 *
 * 用法:
 *   import {AudioSync} from '../utils/audio_sync';
 *
 *   export default makeScene2D(function* (view) {
 *     const sync = new AudioSync('assets/bgm_timeline.csv');
 *     const circle = createRef<Circle>();
 *     view.add(<Circle ref={circle} width={200} height={200} fill="red" />);
 *
 *     for (let frame = 0; frame < 300; frame++) {
 *       const t = frame / 30;
 *       const intensity = sync.loudness(t);
 *       circle().scale(intensity * 2);
 *       yield;
 *     }
 *   });
 */

import * as fs from 'fs';

interface AudioFeature {
  time: number;
  beat: number;
  loudness: number;
  low: number;
  mid: number;
  high: number;
}

export class AudioSync {
  private data: AudioFeature[];
  readonly fps: number;

  constructor(csvPath: string) {
    const text = fs.readFileSync(csvPath, 'utf-8');
    const lines = text.trim().split('\n');
    if (lines.length < 2) {
      this.data = [];
      this.fps = 30;
      return;
    }

    // skip header
    this.data = lines.slice(1).map((line) => {
      const cols = line.split(',');
      return {
        time: parseFloat(cols[0]),
        beat: parseInt(cols[1], 10),
        loudness: parseFloat(cols[2]),
        low: parseFloat(cols[3]),
        mid: parseFloat(cols[4]),
        high: parseFloat(cols[5]),
      };
    });

    this.fps = this._inferFps();
  }

  private _inferFps(): number {
    if (this.data.length < 2) return 30;
    const dt = this.data[1].time - this.data[0].time;
    return dt > 0 ? Math.round(1.0 / dt) : 30;
  }

  private _index(t: number): number {
    const idx = Math.floor(t * this.fps);
    return Math.max(0, Math.min(idx, this.data.length - 1));
  }

  at(t: number): AudioFeature {
    return { ...this.data[this._index(t)] };
  }

  loudness(t: number): number {
    return this.data[this._index(t)].loudness;
  }

  low(t: number): number {
    return this.data[this._index(t)].low;
  }

  mid(t: number): number {
    return this.data[this._index(t)].mid;
  }

  high(t: number): number {
    return this.data[this._index(t)].high;
  }

  isBeat(t: number): boolean {
    return this.data[this._index(t)].beat === 1;
  }

  beatTime(n: number): number | null {
    let count = 0;
    for (const row of this.data) {
      if (row.beat) {
        if (count === n) return row.time;
        count++;
      }
    }
    return null;
  }

  beatCount(): number {
    return this.data.filter((r) => r.beat).length;
  }

  tempo(t: number, window = 1.0): number {
    const t0 = Math.max(0, t - window / 2);
    const t1 = t + window / 2;
    const beatsInWindow = this.data.filter(
      (r) => r.time >= t0 && r.time <= t1 && r.beat
    ).length;
    const expected = window * 2.0;
    const ratio = expected > 0 ? beatsInWindow / expected : 1.0;
    return Math.max(0.5, Math.min(2.0, ratio));
  }
}
