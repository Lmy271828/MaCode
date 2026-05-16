#!/usr/bin/env node
/**
 * engines/motion_canvas/scripts/render.mjs
 * Motion Canvas 统一入口：Vite dev server + Playwright 抓帧（无 browser-pool）。
 *
 * 用法:
 *   render.mjs <scene_dir> <frames_out_dir> <fps> <duration> <width> <height>   # 批量 PNG
 *   render.mjs --serve-only <scene_dir> [--port N | N]                             # 仅启动 dev server
 *   render.mjs --stop <scene_dir>                                                  # 停止 dev server（读 state）
 *   render.mjs --snapshot <scene.tsx> <out.png> [t_sec] [fps] [w] [h]              # 单帧
 */

import fs from 'fs';
import http from 'http';
import path from 'path';
import { fileURLToPath } from 'url';
import { spawn, spawnSync } from 'child_process';
import { chromium } from 'playwright';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const PROJECT_ROOT = path.resolve(__dirname, '../../..');
const ENGINE_DIR = path.resolve(__dirname, '..');

const SCRIPT = path.basename(fileURLToPath(import.meta.url));
const PORT_RANGE_START = 4567;
const PORT_RANGE_END = 5999;


/** @param {string} sceneDirAbs */
function generateMcCaptureBundle(sceneDirAbs) {
  const relPath = path.relative(ENGINE_DIR, sceneDirAbs).replace(/\\/g, '/');

  const projectTs = `import {makeProject} from '@motion-canvas/core';
import scene from './${relPath}/scene.tsx';
export default makeProject({
  scenes: [scene],
});
`;

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

  fs.writeFileSync(path.join(ENGINE_DIR, 'project.ts'), projectTs);
  fs.writeFileSync(path.join(ENGINE_DIR, 'capture.ts'), captureTs);

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
}

async function findFreePort(start, end) {
  const span = end - start + 1;
  const offset = Math.floor(Math.random() * span);
  for (let i = 0; i < span; i++) {
    const port = start + ((offset + i) % span);
    const free = await new Promise((resolve) => {
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

/**
 * Starts Vite detached; returns ChildProcess with pid (process group leader on Unix).
 * @param {number} port
 */
async function startViteDetached(port, logPath, tmpDir) {
  fs.mkdirSync(tmpDir, { recursive: true });
  const vitePath = path.join(PROJECT_ROOT, 'node_modules', 'vite', 'bin', 'vite.js');
  const logStream = fs.createWriteStream(logPath, { flags: 'a' });

  const child = spawn(
    process.execPath,
    [
      vitePath,
      '--config',
      'engines/motion_canvas/vite.config.ts',
      '--port',
      String(port),
      '--host',
    ],
    {
      cwd: PROJECT_ROOT,
      detached: true,
      stdio: ['ignore', 'pipe', 'pipe'],
    },
  );

  child.stdout.pipe(logStream);
  child.stderr.pipe(logStream);

  await new Promise((resolve, reject) => {
    let settled = false;
    const timeout = setTimeout(() => {
      if (settled) return;
      settled = true;
      try {
        child.kill('SIGKILL');
      } catch (_) {}
      reject(new Error('Dev server failed to start within 30s'));
    }, 30000);

    child.on('exit', (code) => {
      if (settled) return;
      clearTimeout(timeout);
      settled = true;
      reject(new Error(`Vite exited early (code ${code}) — port ${port} likely in use`));
    });

    const check = () => {
      http
        .get(`http://127.0.0.1:${port}/`, { timeout: 2000 }, (_res) => {
          if (settled) return;
          clearTimeout(timeout);
          settled = true;
          resolve(undefined);
        })
        .on('error', () => {
          setTimeout(check, 800);
        });
    };
    setTimeout(check, 500);
  });

  child.unref();
  return child;
}

async function terminatePidBestEffort(pid) {
  if (!pid) return;
  try {
    process.kill(-pid, 'SIGTERM');
  } catch (_) {
    try {
      process.kill(pid, 'SIGTERM');
    } catch (_) {}
  }
  const start = Date.now();
  while (Date.now() - start < 5000) {
    try {
      process.kill(pid, 0);
    } catch {
      return;
    }
    await new Promise((r) => setTimeout(r, 200));
  }
  try {
    process.kill(-pid, 'SIGKILL');
  } catch (_) {
    try {
      process.kill(pid, 'SIGKILL');
    } catch (_) {}
  }
}

/** @returns {Promise<void>} */
async function stopDevServerForScene(sceneDirArg) {
  const sceneDir = path.resolve(PROJECT_ROOT, sceneDirArg);
  const sceneName = path.basename(sceneDir);
  const tmpDir = path.join(PROJECT_ROOT, '.agent', 'tmp', sceneName);
  const statePath = path.join(tmpDir, 'state.json');

  if (!fs.existsSync(statePath)) {
    cleanupDevArtifacts(tmpDir);
    return;
  }

  let state;
  try {
    state = JSON.parse(fs.readFileSync(statePath, 'utf-8'));
  } catch {
    cleanupDevArtifacts(tmpDir);
    return;
  }

  const pid = state.pid;
  if (!pid) {
    cleanupDevArtifacts(tmpDir);
    return;
  }

  try {
    process.kill(pid, 0);
  } catch {
    cleanupDevArtifacts(tmpDir);
    return;
  }

  await terminatePidBestEffort(pid);
  cleanupDevArtifacts(tmpDir);
}

function cleanupDevArtifacts(tmpDir) {
  const files = ['state.json', 'dev.pid', 'dev.ready', 'dev.port'];
  for (const f of files) {
    const p = path.join(tmpDir, f);
    if (fs.existsSync(p)) fs.unlinkSync(p);
  }
}

/**
 * Writes state.json identical shape to legacy serve.mjs for `macode mc stop`.
 */
function writeServeState(tmpDir, sceneDirAbs, port, vitePid) {
  const sceneName = path.basename(sceneDirAbs);
  const captureUrl = `http://localhost:${port}/engines/motion_canvas/capture.html`;
  const state = {
    version: '1.0',
    tool: 'render.mjs',
    status: 'completed',
    pid: vitePid,
    sceneDir: sceneDirAbs,
    sceneName,
    startedAt: new Date().toISOString(),
    lastUsedAt: new Date().toISOString(),
    viteConfig: 'engines/motion_canvas/vite.config.ts',
    outputs: { port, captureUrl },
  };
  fs.mkdirSync(tmpDir, { recursive: true });
  fs.writeFileSync(path.join(tmpDir, 'state.json'), JSON.stringify(state, null, 2));
  fs.writeFileSync(path.join(tmpDir, 'dev.pid'), String(vitePid));
  fs.writeFileSync(path.join(tmpDir, 'dev.port'), String(port));
  fs.writeFileSync(path.join(tmpDir, 'dev.ready'), 'ready');
}

/**
 * Batch Playwright capture; closes browser on exit.
 */
async function captureFramesSequence(captureUrl, outputDir, fps, duration, width, height, options = {}) {
  const totalFrames = Math.ceil(fps * duration);
  fs.mkdirSync(outputDir, { recursive: true });

  let browser;
  let context;
  let exitCode = 0;

  try {
    browser = await chromium.launch({ headless: true });
    context = await browser.newContext({ viewport: { width, height }, deviceScaleFactor: 1 });
    const page = await context.newPage();
    page.on('console', (msg) => {
      const text = msg.text();
      if (text.includes('[capture]') || text.includes('ERROR') || text.includes('error')) {
        console.log(`[browser] ${text}`);
      }
    });
    page.on('pageerror', (err) => console.log(`[browser] PAGE ERROR: ${err.message}`));

    await page.goto(captureUrl, { waitUntil: 'networkidle' });
    console.log('[render.mjs] Waiting for capture function...');
    await page.waitForFunction(() => typeof window.__MCODE_CAPTURE__ === 'function', { timeout: 30000 });
    console.log('[render.mjs] Capture function ready.');
    await page.setViewportSize({ width, height });

    const kfEnv = process.env.MACODE_KEYFRAMES || '';
    const keyframeFrames = kfEnv
      ? kfEnv
          .split(',')
          .map((s) => Math.round(parseFloat(s) * fps))
          .filter((f) => f >= 0 && f < totalFrames)
      : [];
    const snapshotDir = process.env.MACODE_SNAPSHOT_DIR || outputDir;
    const snapshotPath = path.join(snapshotDir, 'layout_snapshots.jsonl');

    for (let frame = 0; frame < totalFrames; frame++) {
      const dataUrl = await page.evaluate((f) => window.__MCODE_CAPTURE__(f), frame);
      const base64 = dataUrl.split(',')[1];
      const fileName = `frame_${String(frame + 1).padStart(4, '0')}.png`;
      fs.writeFileSync(path.join(outputDir, fileName), Buffer.from(base64, 'base64'));

      if (keyframeFrames.includes(frame)) {
        try {
          const snapshot = await page.evaluate(() =>
            typeof window.__MCODE_SNAPSHOT__ === 'function' ? window.__MCODE_SNAPSHOT__() : null,
          );
          if (snapshot) {
            snapshot.timestamp = parseFloat((frame / fps).toFixed(2));
            fs.appendFileSync(snapshotPath, `${JSON.stringify(snapshot)}\n`);
            console.log(`[render.mjs] Layout snapshot at frame ${frame + 1} (t=${snapshot.timestamp}s)`);
          }
        } catch (e) {
          console.error(`[render.mjs] Snapshot failed at frame ${frame + 1}: ${e.message}`);
        }
      }

      if ((frame + 1) % 30 === 0 || frame === totalFrames - 1) {
        console.log(`[render.mjs] Frame ${frame + 1}/${totalFrames}`);
      }
    }

    console.log(`[render.mjs] Done. ${totalFrames} frames in ${outputDir}`);
    if (options.onSuccess) await options.onSuccess(totalFrames);
  } catch (err) {
    console.error(`[render.mjs] Error: ${err.message}`);
    exitCode = 1;
  } finally {
    if (context) await context.close().catch(() => {});
    if (browser) await browser.close().catch(() => {});
  }

  const stateDir = process.env.MACODE_STATE_DIR;
  if (stateDir) {
    const taskState = {
      version: '1.0',
      tool: 'render.mjs',
      status: exitCode === 0 ? 'completed' : 'failed',
      exitCode,
      outputs: {
        framesRendered: exitCode === 0 ? totalFrames : 0,
        outputDir,
      },
    };
    try {
      fs.mkdirSync(stateDir, { recursive: true });
      fs.writeFileSync(path.join(stateDir, 'task.json'), `${JSON.stringify(taskState, null, 2)}\n`);
    } catch (e) {
      console.error(`[render.mjs] Failed to write task.json: ${e.message}`);
    }
  }

  return exitCode;
}

function printHelp() {
  console.log(`Usage:
  node ${SCRIPT} <scene_dir> <frames_out_dir> <fps> <duration> <width> <height>
  node ${SCRIPT} --serve-only <scene_dir> [port|--port N]
  node ${SCRIPT} --stop <scene_dir>
  node ${SCRIPT} --snapshot <scene.tsx> <out.png> [time_sec] [fps] [w] [h]
`);
}

function parseServePort(argv) {
  let requestedPort = null;
  for (let i = 0; i < argv.length; i++) {
    if (argv[i] === '--port' && i + 1 < argv.length) {
      requestedPort = parseInt(argv[++i], 10);
    } else if (requestedPort === null && /^\d+$/.test(argv[i])) {
      requestedPort = parseInt(argv[i], 10);
    }
  }
  return requestedPort;
}

async function cmdServeOnly(sceneDirArg, portArgs) {
  const sceneDir = path.resolve(PROJECT_ROOT, sceneDirArg);
  const sceneName = path.basename(sceneDir);
  const tmpDir = path.join(PROJECT_ROOT, '.agent', 'tmp', sceneName);
  fs.mkdirSync(tmpDir, { recursive: true });
  const logPath = path.join(tmpDir, 'dev.log');
  const statePath = path.join(tmpDir, 'state.json');

  if (fs.existsSync(statePath)) {
    try {
      const st = JSON.parse(fs.readFileSync(statePath, 'utf-8'));
      if (st.pid) {
        try {
          process.kill(st.pid, 0);
          console.log(`[render.mjs] Dev server already running (PID ${st.pid})`);
          console.log(st.outputs?.port ?? st.port);
          return 0;
        } catch {}
      }
    } catch {}
  }

  generateMcCaptureBundle(sceneDir);
  console.log(`[render.mjs] Generated project.ts and capture.ts for ${sceneDir}`);

  let requestedPort = parseServePort(portArgs);
  let vite;
  let port;
  for (let attempt = 0; attempt < 5; attempt++) {
    port = requestedPort || (await findFreePort(PORT_RANGE_START, PORT_RANGE_END));
    console.log(`[render.mjs] Attempt ${attempt + 1}/5: port ${port}`);
    try {
      vite = await startViteDetached(port, logPath, tmpDir);
      break;
    } catch (err) {
      console.error(`[render.mjs] ${err.message}`);
      if (attempt === 4) {
        console.error('[render.mjs] Dev server failed to start');
        return 1;
      }
      await new Promise((r) => setTimeout(r, 200));
    }
  }

  console.log(`[render.mjs] Vite PID ${vite.pid}`);
  writeServeState(tmpDir, sceneDir, port, vite.pid);
  console.log(`[render.mjs] Dev server ready on port ${port}`);
  console.log(port);
  return 0;
}

async function cmdSnapshot(sceneTsxRel, outputPng, timeSec, fps, width, height) {
  const sceneFile = path.resolve(PROJECT_ROOT, sceneTsxRel);
  const sceneDir = path.dirname(sceneFile);

  fs.mkdirSync(path.dirname(path.resolve(PROJECT_ROOT, outputPng)), { recursive: true });

  generateMcCaptureBundle(sceneDir);
  await stopDevServerForScene(path.relative(PROJECT_ROOT, sceneDir));

  const sceneName = path.basename(sceneDir);
  const tmpDir = path.join(PROJECT_ROOT, '.agent', 'tmp', sceneName);
  const logPath = path.join(tmpDir, 'dev.log');

  let port;
  let vite;
  try {
    port = await findFreePort(PORT_RANGE_START, PORT_RANGE_END);
    vite = await startViteDetached(port, logPath, tmpDir);
  } catch (e) {
    console.warn(`[render.mjs:snapshot] Vite failed: ${e.message}`);
    return ffmpegPlaceholder(sceneFile, outputPng, timeSec, width, height, e.message, fps);
  }

  const captureUrl = `http://127.0.0.1:${port}/engines/motion_canvas/capture.html`;
  try {
    const browser = await chromium.launch({ headless: true });
    const context = await browser.newContext({ viewport: { width, height }, deviceScaleFactor: 1 });
    const page = await context.newPage();

    await page.goto(captureUrl, { waitUntil: 'load' });
    await page.waitForFunction(() => typeof window.__MCODE_CAPTURE__ === 'function', { timeout: 30000 });

    const targetFrame = Math.max(0, Math.floor(timeSec * fps));
    const dataUrl = await page.evaluate((f) => window.__MCODE_CAPTURE__(f), targetFrame);
    const base64 = dataUrl.split(',')[1];
    fs.writeFileSync(path.resolve(PROJECT_ROOT, outputPng), Buffer.from(base64, 'base64'));
    console.log(`[snapshot] Frame ${targetFrame} @ ${timeSec}s → ${outputPng}`);

    await context.close();
    await browser.close();

    writeSnapshotMeta(sceneFile, outputPng, timeSec, fps, width, height, true, '');
    return 0;
  } catch (err) {
    console.warn(`[render.mjs:snapshot] Playwright failed: ${err.message}`);
    await terminatePidBestEffort(vite.pid);
    return ffmpegPlaceholder(sceneFile, outputPng, timeSec, width, height, err.message, fps);
  } finally {
    await terminatePidBestEffort(vite.pid);
    cleanupDevArtifacts(tmpDir);
  }
}

function ffmpegPlaceholder(sceneFile, outputPngRel, timeSec, width, height, errMsg = '', fpsMeta = 30) {
  const sceneBase = path.basename(sceneFile, path.extname(sceneFile));
  const safeError = String(errMsg).slice(0, 60).replace(/["']/g, '');
  const label = `DEV PREVIEW PLACEHOLDER|${sceneBase}|t=${timeSec}s|${safeError}`;
  try {
    spawnSync(
      'ffmpeg',
      [
        '-y',
        '-f',
        'lavfi',
        '-i',
        `color=c=darkcyan:s=${width}x${height}:d=1`,
        '-vf',
        `drawtext=text=${label}:fontsize=36:fontcolor=white:x=(w-text_w)/2:y=(h-text_h)/2`,
        '-frames:v',
        '1',
        path.resolve(PROJECT_ROOT, outputPngRel),
      ],
      { stdio: 'pipe' },
    );
  } catch (_) {
    fs.writeFileSync(path.resolve(PROJECT_ROOT, outputPngRel), Buffer.from(''));
  }
  writeSnapshotMeta(sceneFile, outputPngRel, timeSec, fpsMeta, width, height, false, errMsg);
  return 1;
}

function writeSnapshotMeta(sceneFile, outputPngRel, timeSec, fps, width, height, rendered, error) {
  const metaPath = path.resolve(PROJECT_ROOT, outputPngRel.replace(/\.png$/, '.json'));
  const meta = {
    scene: sceneFile,
    time_sec: timeSec,
    fps,
    width,
    height,
    output: outputPngRel,
    rendered,
    error: error || undefined,
    timestamp: new Date().toISOString(),
  };
  fs.writeFileSync(metaPath, `${JSON.stringify(meta, null, 2)}\n`);
  console.log(`[snapshot] Metadata: ${metaPath}`);
}

async function cmdBatch(sceneDirRel, framesOutRel, fps, duration, width, height) {
  const sceneDir = path.resolve(PROJECT_ROOT, sceneDirRel);
  const framesDir = path.resolve(PROJECT_ROOT, framesOutRel);
  const sceneName = path.basename(sceneDir);
  const tmpDir = path.join(PROJECT_ROOT, '.agent', 'tmp', sceneName);
  const logPath = path.join(tmpDir, 'dev.log');

  generateMcCaptureBundle(sceneDir);
  await stopDevServerForScene(path.relative(PROJECT_ROOT, sceneDir));

  let vite;
  let port;
  try {
    port = await findFreePort(PORT_RANGE_START, PORT_RANGE_END);
    console.log(`[render.mjs] Batch using port ${port}`);
    vite = await startViteDetached(port, logPath, tmpDir);
  } catch (e) {
    console.error(`[render.mjs] Failed to start Vite: ${e.message}`);
    return 1;
  }

  const vitePid = vite.pid;
  const onSig = () => {
    terminatePidBestEffort(vitePid);
    cleanupDevArtifacts(tmpDir);
    process.exit(130);
  };
  process.on('SIGTERM', onSig);
  process.on('SIGINT', onSig);

  const captureUrl = `http://127.0.0.1:${port}/engines/motion_canvas/capture.html`;
  console.log(`[render.mjs] Capture URL ${captureUrl}`);

  try {
    const code = await captureFramesSequence(captureUrl, framesDir, fps, duration, width, height);
    return code;
  } finally {
    process.off('SIGTERM', onSig);
    process.off('SIGINT', onSig);
    await terminatePidBestEffort(vitePid);
    cleanupDevArtifacts(tmpDir);
  }
}

const argv = process.argv.slice(2);
if (argv.includes('--help') || argv.includes('-h')) {
  printHelp();
  process.exit(0);
}

async function main() {
  if (argv[0] === '--stop') {
    const sd = argv[1];
    if (!sd) {
      console.error('Usage: render.mjs --stop <scene_dir>');
      process.exit(1);
    }
    console.log('[render.mjs] Stopping dev server...');
    await stopDevServerForScene(sd);
    console.log('[render.mjs] stop complete');
    process.exit(0);
  }

  if (argv[0] === '--serve-only') {
    const sd = argv[1];
    if (!sd) {
      console.error('Usage: render.mjs --serve-only <scene_dir> [port|--port N]');
      process.exit(1);
    }
    process.exit(await cmdServeOnly(sd, argv.slice(2)));
  }

  if (argv[0] === '--snapshot') {
    const a = argv.slice(1);
    const sf = a[0];
    const outp = a[1];
    if (!sf || !outp) {
      console.error('Usage: render.mjs --snapshot <scene.tsx> <out.png> [time_sec] [fps] [w] [h]');
      process.exit(1);
    }
    const tc = parseFloat(a[2] || '0');
    const fps = parseInt(a[3] || '30', 10);
    const w = parseInt(a[4] || '1920', 10);
    const h = parseInt(a[5] || '1080', 10);
    process.exit(
      await cmdSnapshot(sf, outp, tc, fps, w, h),
    );
  }

  const [sd, fod, fpsS, durS, wS, hS] = argv;
  if (!sd || !fod || !fpsS || !durS || !wS || !hS) {
    printHelp();
    process.exit(1);
  }

  const fps = parseInt(fpsS, 10);
  const duration = parseFloat(durS);
  const w = parseInt(wS, 10);
  const h = parseInt(hS, 10);

  process.exit(await cmdBatch(sd, fod, fps, duration, w, h));
}

main().catch((e) => {
  console.error(e);
  process.exit(1);
});
