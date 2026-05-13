#!/usr/bin/env node
/**
 * engines/motion_canvas/scripts/playwright-render.mjs
 * Playwright 帧抓取工具 —— 连接 Vite dev server，逐帧捕获。
 *
 * 用法:
 *   playwright-render.mjs <capture_url> <output_dir> [fps] [duration] [width] [height]
 *
 * 约束:
 *   - 不启动/停止 dev server（由调用方管理）
 *   - 输出 frame_%04d.png 到指定目录
 *   - 通过 Browser Pool 复用全局 Chromium 实例（每个任务独立 Context 隔离）
 */

import fs from 'fs';
import path from 'path';
import {acquireBrowser} from './browser-pool.mjs';

const scriptName = path.basename(process.argv[1] || 'playwright-render.mjs');
if (process.argv.includes('--help') || process.argv.includes('-h')) {
  console.log(`Usage: node ${scriptName} <capture_url> <output_dir> [fps] [duration] [width] [height]

连接 Vite dev server，使用 Playwright 逐帧捕获输出 PNG 序列。
复用全局 Browser Pool 以降低并发内存开销。

Arguments:
  <capture_url>   抓取页面 URL，如 http://localhost:4567/engines/motion_canvas/capture.html
  <output_dir>    帧序列输出目录
  [fps]           帧率 (default: 30)
  [duration]      时长（秒）(default: 3)
  [width]         宽度 (default: 1920)
  [height]        高度 (default: 1080)

Examples:
  node ${scriptName} http://localhost:4567/capture.html .agent/tmp/frames`);
  process.exit(0);
}

const captureUrl = process.argv[2];
const outputDir = process.argv[3];
const fps = parseInt(process.argv[4] || '30', 10);
const duration = parseFloat(process.argv[5] || '3');
const width = parseInt(process.argv[6] || '1920', 10);
const height = parseInt(process.argv[7] || '1080', 10);

if (!captureUrl || !outputDir) {
  console.error('Usage: playwright-render.mjs <capture_url> <output_dir> [fps] [duration] [width] [height]');
  process.exit(1);
}

fs.mkdirSync(outputDir, { recursive: true });

const totalFrames = Math.ceil(fps * duration);
console.log(`[playwright] Connecting to ${captureUrl}`);
console.log(`[playwright] Rendering ${totalFrames} frames @ ${fps}fps, ${width}x${height}`);

let exitCode = 0;
let browser;

try {
  browser = await acquireBrowser();
} catch (err) {
  console.error(`[playwright] Failed to acquire browser from pool: ${err.message}`);
  process.exit(1);
}

const context = await browser.newContext();

try {
  const page = await context.newPage();

  // Collect console logs for debugging
  page.on('console', msg => {
    const text = msg.text();
    if (text.includes('[capture]') || text.includes('ERROR') || text.includes('error')) {
      console.log(`[browser] ${text}`);
    }
  });
  page.on('pageerror', err => console.log(`[browser] PAGE ERROR: ${err.message}`));

  await page.goto(captureUrl, { waitUntil: 'networkidle' });

  console.log('[playwright] Waiting for capture function...');
  await page.waitForFunction(
    () => typeof window.__MCODE_CAPTURE__ === 'function',
    { timeout: 30000 }
  );
  console.log('[playwright] Capture function ready.');

  // Optionally set viewport size (may help with HiDPI consistency)
  await page.setViewportSize({ width: 960, height: 540 });

  // Layout snapshot keyframes
  const kfEnv = process.env.MACODE_KEYFRAMES || '';
  const keyframeFrames = kfEnv
    ? kfEnv.split(',').map(s => Math.round(parseFloat(s) * fps)).filter(f => f >= 0 && f < totalFrames)
    : [];
  const snapshotDir = process.env.MACODE_SNAPSHOT_DIR || outputDir;
  const snapshotPath = path.join(snapshotDir, 'layout_snapshots.jsonl');

  for (let frame = 0; frame < totalFrames; frame++) {
    const dataUrl = await page.evaluate(
      (f) => window.__MCODE_CAPTURE__(f),
      frame
    );

    const base64 = dataUrl.split(',')[1];
    const buffer = Buffer.from(base64, 'base64');
    const fileName = `frame_${String(frame + 1).padStart(4, '0')}.png`;
    const filePath = path.join(outputDir, fileName);
    fs.writeFileSync(filePath, buffer);

    // Capture layout snapshot at keyframe frames
    if (keyframeFrames.includes(frame)) {
      try {
        const snapshot = await page.evaluate(() => {
          if (typeof window.__MCODE_SNAPSHOT__ === 'function') {
            return window.__MCODE_SNAPSHOT__();
          }
          return null;
        });
        if (snapshot) {
          snapshot.timestamp = parseFloat((frame / fps).toFixed(2));
          fs.appendFileSync(snapshotPath, JSON.stringify(snapshot) + '\n');
          console.log(`[playwright] Layout snapshot at frame ${frame + 1} (t=${snapshot.timestamp}s)`);
        }
      } catch (e) {
        console.error(`[playwright] Snapshot failed at frame ${frame + 1}: ${e.message}`);
      }
    }

    if ((frame + 1) % 30 === 0 || frame === totalFrames - 1) {
      console.log(`[playwright] Frame ${frame + 1}/${totalFrames}`);
    }
  }

  console.log(`[playwright] Done. ${totalFrames} frames in ${outputDir}`);
} catch (err) {
  console.error(`[playwright] Error: ${err.message}`);
  exitCode = 1;
} finally {
  // 只关闭 Context，不关闭 Browser（Browser 由全局 Pool 管理）
  await context.close().catch(() => {});

  // Write MaCode Task State v1 if MACODE_STATE_DIR is set
  const stateDir = process.env.MACODE_STATE_DIR;
  if (stateDir) {
    const taskState = {
      version: '1.0',
      tool: 'playwright-render.mjs',
      status: exitCode === 0 ? 'completed' : 'failed',
      exitCode,
      outputs: {
        framesRendered: totalFrames,
        outputDir,
      },
    };
    try {
      fs.mkdirSync(stateDir, {recursive: true});
      fs.writeFileSync(path.join(stateDir, 'task.json'), JSON.stringify(taskState, null, 2));
    } catch (e) {
      console.error(`[playwright] Failed to write task.json: ${e.message}`);
    }
  }

  // 强制退出：远程 ws 连接会阻止 Node 自然退出
  process.exit(exitCode);
}
