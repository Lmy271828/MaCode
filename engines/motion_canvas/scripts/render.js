#!/usr/bin/env node
/**
 * Motion Canvas headless renderer.
 *
 * Uses jsdom + node-canvas to provide a browser-like environment,
 * then drives the Motion Canvas Scene/PlaybackManager directly.
 */

const fs = require('fs');
const path = require('path');

// 1. Setup jsdom before importing Motion Canvas
const { JSDOM } = require('jsdom');
const dom = new JSDOM('<!DOCTYPE html><html><body></body></html>', {
  pretendToBeVisual: true,
  resources: 'usable',
});

global.window = dom.window;
global.document = dom.window.document;
global.navigator = dom.window.navigator;
global.HTMLCanvasElement = dom.window.HTMLCanvasElement;
global.HTMLImageElement = dom.window.HTMLImageElement;
global.Image = dom.window.Image;
global.Event = dom.window.Event;
global.requestAnimationFrame = (cb) => setTimeout(cb, 16);
global.cancelAnimationFrame = (id) => clearTimeout(id);

// 2. Setup node-canvas
const nodeCanvas = require('canvas');

// Monkey-patch jsdom's canvas with node-canvas implementation
// so Motion Canvas can use it for 2D rendering.
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

// 3. Register tsx for TypeScript/TSX imports
require('tsx/dist/loader.cjs');

// 4. Parse arguments
const sceneFile = process.argv[2];
const outputDir = process.argv[3];
const fps = parseInt(process.argv[4] || '30', 10);
const duration = parseFloat(process.argv[5] || '3');
const width = parseInt(process.argv[6] || '1920', 10);
const height = parseInt(process.argv[7] || '1080', 10);

if (!sceneFile || !outputDir) {
  console.error('Usage: render.js <scene.tsx> <output_dir> [fps] [duration] [width] [height]');
  process.exit(1);
}

// 5. Import Motion Canvas
const { Scene2D } = require('@motion-canvas/2d');
const { PlaybackStatus, Logger, SceneMetadata, TimeEvents, SharedWebGLContext, Vector2 } = require('@motion-canvas/core');

// 6. Load the scene module
const sceneModule = require(path.resolve(sceneFile));
const sceneDescription = sceneModule.default || sceneModule;

// 7. Build a FullSceneDescription
const logger = new Logger();
const playback = new PlaybackStatus();
playback.fps = fps;

// Simple mock classes
class MockTimeEvents extends TimeEvents {
  constructor(scene) { super(scene); }
}
class MockSharedWebGLContext extends SharedWebGLContext {
  constructor() { super(); }
}

const { ValueDispatcher } = require('@motion-canvas/core');

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

// 8. Create the scene
const scene = new Scene2D(fullDescription);

// 9. Render frames
const totalFrames = Math.ceil(fps * duration);
const canvas = nodeCanvas.createCanvas(width, height);
const ctx = canvas.getContext('2d');

fs.mkdirSync(outputDir, { recursive: true });

async function render() {
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
}

render().catch(err => {
  console.error('[motion_canvas] Render error:', err);
  process.exit(1);
});
