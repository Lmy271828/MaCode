#!/usr/bin/env node
/**
 * engines/motion_canvas/scripts/serve.mjs
 * Motion Canvas dev server launcher.
 *
 * Usage:
 *   serve.mjs <scene_dir> [port]
 *   serve.mjs <scene_dir> --port <port>
 *
 * Design (Harness 2.0 execution layer):
 *   - Generates project.ts / capture.ts / capture.html
 *   - Accepts explicit --port or positional [port]; falls back to port probing
 *   - Starts Vite dev server, waits for HTTP readiness
 *   - Writes state.json with captureUrl for orchestrator consumption
 *   - NO global port coordination, NO guardian spawning, NO orchestration
 */

import fs from 'fs';
import path from 'path';
import {fileURLToPath} from 'url';
import http from 'http';
import {spawn} from 'child_process';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const PROJECT_ROOT = path.resolve(__dirname, '../../..');
const ENGINE_DIR = path.resolve(__dirname, '..');

const scriptName = path.basename(fileURLToPath(import.meta.url));

function usage() {
  console.log(`Usage: node ${scriptName} <scene_dir> [port]
       node ${scriptName} <scene_dir> --port <port>

Launch Motion Canvas Vite dev server. Generate project.ts / capture.ts.

Arguments:
  <scene_dir>    Scene directory, e.g. scenes/01_test_mc/
  [port]         Server port (default: auto-detect 4567-5999)
  --port <port>  Explicit port (same as positional)`);
  process.exit(0);
}

if (process.argv.includes('--help') || process.argv.includes('-h')) usage();

const sceneDirArg = process.argv[2];
if (!sceneDirArg) {
  console.error('Error: scene_dir required');
  usage();
}

// Parse port from --port flag or positional arg
let requestedPort = null;
for (let i = 3; i < process.argv.length; i++) {
  if (process.argv[i] === '--port' && i + 1 < process.argv.length) {
    requestedPort = parseInt(process.argv[++i], 10);
  } else if (requestedPort === null && /^\d+$/.test(process.argv[i])) {
    requestedPort = parseInt(process.argv[i], 10);
  }
}

const sceneDir = path.resolve(PROJECT_ROOT, sceneDirArg);
const sceneName = path.basename(sceneDir);
const tmpDir = path.join(PROJECT_ROOT, '.agent', 'tmp', sceneName);
fs.mkdirSync(tmpDir, {recursive: true});

const statePath = path.join(tmpDir, 'state.json');
const pidPath = path.join(tmpDir, 'dev.pid');
const readyPath = path.join(tmpDir, 'dev.ready');
const portPath = path.join(tmpDir, 'dev.port');
const logPath = path.join(tmpDir, 'dev.log');

// ── 1. Reuse check (for direct "macode mc serve" usage) ──
if (fs.existsSync(statePath)) {
  try {
    const state = JSON.parse(fs.readFileSync(statePath, 'utf-8'));
    if (state.pid) {
      try {
        process.kill(state.pid, 0);
        console.log(`[serve] Dev server already running (PID ${state.pid}) on port ${state.port}`);
        console.log(port);
        process.exit(0);
      } catch {
        console.log(`[serve] Stale state found (PID ${state.pid} dead), restarting...`);
      }
    }
  } catch {
    // ignore corrupt state
  }
}

// ── 2. Generate project.ts ──────────────────────────
const relPath = path.relative(ENGINE_DIR, sceneDir).replace(/\\/g, '/');

const projectTs = `import {makeProject} from '@motion-canvas/core';
import scene from './${relPath}/scene.tsx';
export default makeProject({
  scenes: [scene],
});
`;

fs.writeFileSync(path.join(ENGINE_DIR, 'project.ts'), projectTs);

// ── 3. Generate capture.ts ──────────────────────────
const captureTs = `import {PlaybackManager, PlaybackStatus, Stage, Vector2, ValueDispatcher} from '@motion-canvas/core';
import {Scene2D} from '@motion-canvas/2d';
import {createSceneMetadata} from '@motion-canvas/core/lib/scenes/SceneMetadata';
import {EditableTimeEvents} from '@motion-canvas/core/lib/scenes/timeEvents/EditableTimeEvents';
import {SharedWebGLContext} from '@motion-canvas/core/lib/app/SharedWebGLContext';
import projectModule from './project';
const project = (projectModule as any).default || projectModule;
const sceneDesc = project.scenes?.[0] || project;
const config = sceneDesc.config || sceneDesc;

const playback = new PlaybackManager();
const playbackStatus = new PlaybackStatus(playback);
const stage = new Stage();

const fullDescription = {
  name: 'scene',
  size: new Vector2(1920, 1080),
  resolutionScale: 1,
  variables: {},
  playback: playbackStatus,
  logger: console as any,
  onReplaced: new ValueDispatcher(null),
  timeEventsClass: EditableTimeEvents,
  sharedWebGLContext: new SharedWebGLContext(),
  klass: Scene2D,
  config: config,
  meta: createSceneMetadata(),
  stack: '',
};

const scene = new Scene2D(fullDescription as any);

stage.configure({
  size: new Vector2(1920, 1080),
  resolutionScale: 1,
  colorSpace: 'srgb',
  background: null,
});

playback.setup([scene]);

(window as any).__MCODE_CAPTURE__ = async (frame: number) => {
  await playback.reset();
  await playback.recalculate();
  await playback.seek(frame);
  await stage.render(playback.currentScene, playback.previousScene);
  return stage.finalBuffer.toDataURL('image/png');
};

(window as any).__MCODE_GET_DURATION__ = () => playback.duration;
(window as any).__MCODE_GET_FPS__ = () => playback.fps;

// Layout snapshot for runtime text-overlap detection
(window as any).__MCODE_SNAPSHOT__ = () => {
  const currentScene = playback.currentScene;
  if (!currentScene || !currentScene.view) {
    return null;
  }
  const view = currentScene.view;
  const canvas = currentScene.settings?.size || new Vector2(1920, 1080);
  const [cw, ch] = [canvas.x, canvas.y];
  const objects = [];

  function traverse(node, depth = 0) {
    if (!node || depth > 20) return;

    const w = node.width?.() || node.size?.().x || 0;
    const h = node.height?.() || node.size?.().y || 0;
    const pos = node.position?.() || { x: 0, y: 0 };
    const cx = pos.x;
    const cy = pos.y;

    const normX = (cx - w / 2 + cw / 2) / cw;
    const normY = (ch / 2 - (cy + h / 2)) / ch;

    const className = node.constructor?.name;
    let type = 'unknown';
    if (className === 'Txt') type = 'text';
    if (className === 'Latex') type = 'formula';

    objects.push({
      id: node.key || className || 'obj_' + depth,
      type,
      bbox: {
        x: Math.max(0, Math.min(1, normX)),
        y: Math.max(0, Math.min(1, normY)),
        w: Math.min(1, w / cw),
        h: Math.min(1, h / ch),
      },
    });

    const children = node.children?.();
    if (children && Array.isArray(children)) {
      children.forEach((c) => traverse(c, depth + 1));
    }
  }

  traverse(view);
  return {
    timestamp: playback.currentScene?.time ?? 0,
    engine: 'motion_canvas',
    canvas: [cw, ch],
    objects,
  };
};
`;

fs.writeFileSync(path.join(ENGINE_DIR, 'capture.ts'), captureTs);

// ── 4. Ensure capture.html exists ───────────────────
const captureHtmlPath = path.join(ENGINE_DIR, 'capture.html');
if (!fs.existsSync(captureHtmlPath)) {
  const captureHtml = `<!DOCTYPE html>
<html lang="en">
<head><meta charset="UTF-8"><title>MaCode Capture</title></head>
<body><script type="module" src="./capture.ts"></script></body>
</html>
`;
  fs.writeFileSync(captureHtmlPath, captureHtml);
}

console.log(`[serve] Generated project.ts and capture.ts for ${sceneDir}`);

// ── 5. Port probing ─────────────────────────────────
const PORT_RANGE_START = 4567;
const PORT_RANGE_END   = 5999;

async function findPort(start, end) {
  const span = end - start + 1;
  const offset = Math.floor(Math.random() * span);
  for (let i = 0; i < span; i++) {
    const port = start + ((offset + i) % span);
    const free = await new Promise(resolve => {
      const server = http.createServer();
      server.once('error', () => resolve(false));
      server.once('listening', () => {
        server.close(() => resolve(true));
      });
      server.listen(port, '127.0.0.1');
    });
    if (free) return port;
  }
  throw new Error(`No free port in range ${start}-${end}`);
}

async function startViteOnce(port) {
  const logStream = fs.createWriteStream(logPath, {flags: 'a'});
  const vitePath = path.join(PROJECT_ROOT, 'node_modules', 'vite', 'bin', 'vite.js');
  const child = spawn('node', [
    vitePath,
    '--config', 'engines/motion_canvas/vite.config.ts',
    '--port', String(port),
    '--host',
  ], {
    cwd: PROJECT_ROOT,
    detached: true,
    stdio: ['ignore', 'pipe', 'pipe'],
  });

  child.stdout.pipe(logStream);
  child.stderr.pipe(logStream);

  return new Promise((resolve, reject) => {
    let settled = false;

    const timeout = setTimeout(() => {
      if (settled) return;
      settled = true;
      child.kill();
      reject(new Error('Dev server failed to start within 30s'));
    }, 30000);

    const earlyExit = setTimeout(() => {
      if (settled) return;
      // Process survived 3s, port likely bound OK
    }, 3000);

    child.on('exit', (code) => {
      if (settled) return;
      clearTimeout(timeout);
      clearTimeout(earlyExit);
      settled = true;
      reject(new Error(`Vite exited early (code ${code}) — port ${port} likely in use`));
    });

    const check = () => {
      http.get(`http://127.0.0.1:${port}/`, {timeout: 2000}, (_res) => {
        if (settled) return;
        clearTimeout(timeout);
        clearTimeout(earlyExit);
        settled = true;
        resolve(child);
      }).on('error', () => {
        setTimeout(check, 800);
      });
    };
    setTimeout(check, 500);
  });
}

// ── 6. Allocate port and start Vite (with retry) ────
let vite;
let port;
const maxRetries = 5;

for (let attempt = 0; attempt < maxRetries; attempt++) {
  port = requestedPort || await findPort(PORT_RANGE_START, PORT_RANGE_END);
  console.log(`[serve] Attempt ${attempt + 1}/${maxRetries}: using port ${port}`);
  try {
    vite = await startViteOnce(port);
    break;
  } catch (err) {
    console.error(`[serve] ${err.message}`);
    if (vite) { try { vite.kill(); } catch {} }
    if (attempt === maxRetries - 1) {
      console.error('[serve] ERROR: Dev server failed to start after all retries');
      process.exit(1);
    }
    await new Promise(r => setTimeout(r, 200));
  }
}

console.log(`[serve] Starting Vite (PID ${vite.pid})...`);

// ── 7. Write state files ────────────────────────────
const captureUrl = `http://localhost:${port}/engines/motion_canvas/capture.html`;
const state = {
  version: '1.0',
  tool: 'serve.mjs',
  status: 'completed',
  pid: vite.pid,
  sceneDir,
  sceneName,
  startedAt: new Date().toISOString(),
  lastUsedAt: new Date().toISOString(),
  viteConfig: 'engines/motion_canvas/vite.config.ts',
  outputs: {
    port,
    captureUrl,
  },
};

fs.writeFileSync(statePath, JSON.stringify(state, null, 2));
fs.writeFileSync(pidPath, String(vite.pid));
fs.writeFileSync(portPath, String(port));
fs.writeFileSync(readyPath, 'ready');

console.log(`[serve] Dev server ready on port ${port} (PID ${vite.pid})`);
console.log(port);

// Detach and exit — Vite continues as orphan process
vite.unref();
process.exit(0);
