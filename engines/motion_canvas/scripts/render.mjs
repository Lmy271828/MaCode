#!/usr/bin/env node
/**
 * Motion Canvas headless renderer (ESM).
 *
 * Uses jsdom + node-canvas to provide a browser-like environment,
 * then drives the Motion Canvas Scene directly.
 */

import fs from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));

// 1. Setup jsdom before importing Motion Canvas
const { JSDOM } = await import('jsdom');
const dom = new JSDOM('<!DOCTYPE html><html><body></body></html>', {
  pretendToBeVisual: true,
  resources: 'usable',
});

Object.defineProperty(global, 'window', { value: dom.window, writable: true, configurable: true });
Object.defineProperty(global, 'document', { value: dom.window.document, writable: true, configurable: true });
Object.defineProperty(global, 'navigator', { value: dom.window.navigator, writable: true, configurable: true });
Object.defineProperty(global, 'HTMLCanvasElement', { value: dom.window.HTMLCanvasElement, writable: true, configurable: true });
Object.defineProperty(global, 'HTMLImageElement', { value: dom.window.HTMLImageElement, writable: true, configurable: true });
Object.defineProperty(global, 'Image', { value: dom.window.Image, writable: true, configurable: true });
Object.defineProperty(global, 'Event', { value: dom.window.Event, writable: true, configurable: true });
global.requestAnimationFrame = (cb) => setTimeout(cb, 16);
global.cancelAnimationFrame = (id) => clearTimeout(id);

// 2. Setup node-canvas
const nodeCanvas = await import('canvas');

// Monkey-patch jsdom's canvas with node-canvas
const OriginalHTMLCanvasElement = dom.window.HTMLCanvasElement;
class PatchedCanvasElement extends OriginalHTMLCanvasElement {
  constructor(width, height) {
    super();
    this._nodeCanvas = nodeCanvas.createCanvas(width || 1920, height || 1080);
  }
  getContext(type, attrs) {
    if (type === '2d') {
      return this._nodeCanvas.getContext('2d', attrs);
    }
    return super.getContext(type, attrs);
  }
  toDataURL(mimeType, quality) {
    if (mimeType === 'image/png') {
      const buf = this._nodeCanvas.toBuffer('image/png');
      return 'data:image/png;base64,' + buf.toString('base64');
    }
    return super.toDataURL(mimeType, quality);
  }
}

dom.window.HTMLCanvasElement = PatchedCanvasElement;
global.HTMLCanvasElement = PatchedCanvasElement;

// 3. Parse arguments
const sceneFile = process.argv[2];
const outputDir = process.argv[3];
const fps = parseInt(process.argv[4] || '30', 10);
const duration = parseFloat(process.argv[5] || '3');
const width = parseInt(process.argv[6] || '1920', 10);
const height = parseInt(process.argv[7] || '1080', 10);

if (!sceneFile || !outputDir) {
  console.error('Usage: render.mjs <scene.tsx> <output_dir> [fps] [duration] [width] [height]');
  process.exit(1);
}

// 4. Import Motion Canvas (dynamic import for ESM)
const core = await import('@motion-canvas/core');
const mc2d = await import('@motion-canvas/2d');

const { Scene2D } = mc2d;
const { Logger, SceneMetadata, TimeEvents, SharedWebGLContext, Vector2, ValueDispatcher } = core;

// PlaybackStatus may be in a submodule
let PlaybackStatus;
try {
  const playbackModule = await import('@motion-canvas/core/lib/app/PlaybackStatus.js');
  PlaybackStatus = playbackModule.PlaybackStatus;
} catch {
  PlaybackStatus = core.PlaybackStatus;
}

// 5. Load the scene module using tsx
// tsx handles TSX transpilation on the fly
await import('tsx/dist/loader.mjs');

const scenePath = path.resolve(sceneFile);
const sceneModule = await import(scenePath);
const sceneDescription = sceneModule.default || sceneModule;

// 6. Build a FullSceneDescription
const logger = new Logger();
const playback = new PlaybackStatus();
playback.fps = fps;

class MockTimeEvents extends TimeEvents {
  constructor(scene) { super(scene); }
}
class MockSharedWebGLContext extends SharedWebGLContext {
  constructor() { super(); }
}

const fullDescription = {
  name: path.basename(sceneFile, path.extname(sceneFile)),
  size: new Vector2(width, height),
  resolutionScale: 1,
  variables: {},
  playback: playback,
  logger: logger,
  onReplaced: new ValueDispatcher(null),
  timeEventsClass: MockTimeEvents,
  sharedWebGLContext: new MockSharedWebGLContext(),
  klass: Scene2D,
  config: sceneDescription.config || sceneDescription,
  meta: new SceneMetadata(),
  stack: '',
};

// 7. Create the scene
const scene = new Scene2D(fullDescription);

// 8. Render frames
const totalFrames = Math.ceil(fps * duration);
const canvas = nodeCanvas.createCanvas(width, height);
const ctx = canvas.getContext('2d');

fs.mkdirSync(outputDir, { recursive: true });

console.log(`[motion_canvas] Rendering ${totalFrames} frames @ ${fps}fps, ${width}x${height}`);

await scene.reset(null);
await scene.enterInitial();

for (let frame = 0; frame < totalFrames; frame++) {
  playback.frame = frame;
  await scene.next();
  ctx.clearRect(0, 0, width, height);
  await scene.render(ctx);

  const fileName = `frame_${String(frame + 1).padStart(4, '0')}.png`;
  const filePath = path.join(outputDir, fileName);
  const buffer = canvas.toBuffer('image/png');
  fs.writeFileSync(filePath, buffer);

  if ((frame + 1) % 30 === 0 || frame === totalFrames - 1) {
    console.log(`[motion_canvas] Frame ${frame + 1}/${totalFrames}`);
  }
}

console.log(`[motion_canvas] Done. ${totalFrames} frames in ${outputDir}`);
