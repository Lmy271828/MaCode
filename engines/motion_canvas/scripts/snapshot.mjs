#!/usr/bin/env node
/**
 * engines/motion_canvas/scripts/snapshot.mjs
 * Motion Canvas 单帧抓取工具（Harness 2.0）。
 *
 * 用法:
 *   snapshot.mjs <scene.tsx> <output_png> [time_sec] [fps] [width] [height]
 */

import fs from 'fs';
import path from 'path';
import { spawnSync } from 'child_process';
import { fileURLToPath } from 'url';
import { acquireBrowser } from './browser-pool.mjs';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const PROJECT_ROOT = path.resolve(__dirname, '../../..');

const scriptName = path.basename(fileURLToPath(import.meta.url));
if (process.argv.includes('--help') || process.argv.includes('-h')) {
  console.log(`Usage: node ${scriptName} <scene.tsx> <output.png> [time_sec] [fps] [width] [height]

Motion Canvas 单帧抓取工具（Playwright + Vite dev server + Browser Pool）。

Arguments:
  <scene.tsx>    场景源码路径（TSX 文件）
  <output.png>   输出 PNG 文件路径
  [time_sec]     抓取时间点（秒）(default: 0)
  [fps]          帧率 (default: 30)
  [width]        宽度 (default: 1920)
  [height]       高度 (default: 1080)`);
  process.exit(0);
}

const sceneFile = process.argv[2];
const outputPng = process.argv[3];
const timeSec = parseFloat(process.argv[4] || '0');
const fps = parseInt(process.argv[5] || '30', 10);
const width = parseInt(process.argv[6] || '1920', 10);
const height = parseInt(process.argv[7] || '1080', 10);

if (!sceneFile || !outputPng) {
  console.error('Usage: snapshot.mjs <scene.tsx> <output.png> [time_sec] [fps] [width] [height]');
  process.exit(1);
}

fs.mkdirSync(path.dirname(outputPng), { recursive: true });

const sceneDir = path.dirname(sceneFile);
const sceneName = path.basename(sceneDir);
const tmpDir = path.join(PROJECT_ROOT, '.agent/tmp', sceneName);
const statePath = path.join(tmpDir, 'state.json');

let devPort = null;
let startedDevServer = false;
let rendered = false;
let errorMsg = '';

// ── Attempt 1: Playwright + Vite dev server ──────────
try {
  // 检查是否已有 dev server
  if (fs.existsSync(statePath)) {
    try {
      const state = JSON.parse(fs.readFileSync(statePath, 'utf-8'));
      if (state.port) {
        devPort = state.port;
        console.log(`[snapshot] Reusing dev server on port ${devPort}`);
      }
    } catch { /* ignore broken state */ }
  }

  // 没有则启动临时 dev server
  if (!devPort) {
    console.log('[snapshot] Starting temporary dev server...');
    const result = spawnSync('node', [
      path.join(__dirname, 'serve.mjs'),
      sceneDir,
    ], { encoding: 'utf-8', cwd: PROJECT_ROOT });

    if (result.status !== 0) {
      throw new Error(`serve.mjs failed: ${result.stderr || result.stdout}`);
    }
    const lines = result.stdout.trim().split('\n');
    devPort = parseInt(lines[lines.length - 1], 10);
    if (!devPort || isNaN(devPort)) {
      throw new Error(`Could not parse port from serve.mjs output: ${result.stdout}`);
    }
    startedDevServer = true;
    console.log(`[snapshot] Dev server started on port ${devPort}`);
  }

  const captureUrl = `http://127.0.0.1:${devPort}/engines/motion_canvas/capture.html`;
  console.log(`[snapshot] Capturing via Playwright: ${captureUrl}`);

  const browser = await acquireBrowser();
  const context = await browser.newContext({
    viewport: { width, height },
    deviceScaleFactor: 1,
  });
  try {
    const page = await context.newPage();
    page.on('console', msg => {
      const text = msg.text();
      if (text.includes('[capture]') || text.includes('ERROR')) {
        console.log(`[browser] ${text}`);
      }
    });
    page.on('pageerror', err => console.log(`[browser] PAGE ERROR: ${err.message}`));

    await page.goto(captureUrl, { waitUntil: 'load' });
    await page.waitForFunction(
      () => typeof window.__MCODE_CAPTURE__ === 'function',
      { timeout: 30000 }
    );

    const targetFrame = Math.max(0, Math.floor(timeSec * fps));
    const dataUrl = await page.evaluate((f) => window.__MCODE_CAPTURE__(f), targetFrame);

    const base64 = dataUrl.split(',')[1];
    fs.writeFileSync(outputPng, Buffer.from(base64, 'base64'));

    rendered = true;
    console.log(`[snapshot] Frame ${targetFrame} @ ${timeSec}s rendered: ${outputPng}`);
  } finally {
    await context.close();
  }
} catch (err) {
  errorMsg = err.message || String(err);
  console.warn(`[snapshot] Playwright failed: ${errorMsg}`);
} finally {
  if (startedDevServer) {
    console.log('[snapshot] Stopping temporary dev server...');
    spawnSync('node', [path.join(__dirname, 'stop.mjs'), sceneDir], { cwd: PROJECT_ROOT });
  }
}

// ── Fallback: placeholder PNG ───────────────────────
if (!rendered) {
  const sceneBase = path.basename(sceneFile, path.extname(sceneFile));
  const safeError = errorMsg.slice(0, 60).replace(/["']/g, '');
  const label = `DEV PREVIEW PLACEHOLDER|${sceneBase}|t=${timeSec}s|${safeError}`;
  try {
    spawnSync('ffmpeg', [
      '-y', '-f', 'lavfi',
      '-i', `color=c=darkcyan:s=${width}x${height}:d=1`,
      '-vf', `drawtext=text=${label}:fontsize=36:fontcolor=white:x=(w-text_w)/2:y=(h-text_h)/2`,
      '-frames:v', '1', outputPng,
    ], { stdio: 'pipe' });
    console.log(`[snapshot] Placeholder saved: ${outputPng}`);
  } catch (ffmpegErr) {
    fs.writeFileSync(outputPng, Buffer.from(''));
    console.error(`[snapshot] ffmpeg placeholder also failed: ${ffmpegErr.message}`);
  }
}

// ── Write metadata JSON ─────────────────────────────
const metaPath = outputPng.replace(/\.png$/, '.json');
const meta = {
  scene: sceneFile,
  time_sec: timeSec,
  fps: fps,
  width: width,
  height: height,
  output: outputPng,
  rendered: rendered,
  error: errorMsg || undefined,
  timestamp: new Date().toISOString(),
};
fs.writeFileSync(metaPath, JSON.stringify(meta, null, 2) + '\n');
console.log(`[snapshot] Metadata: ${metaPath}`);
process.exit(rendered ? 0 : 1);
