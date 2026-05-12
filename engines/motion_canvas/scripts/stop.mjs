#!/usr/bin/env node
/**
 * engines/motion_canvas/scripts/stop.mjs
 * Motion Canvas dev server 停止器。
 *
 * 用法:
 *   stop.mjs <scene_dir>
 *
 * 职责:
 *   1. 读取 .agent/tmp/{scene_name}/state.json
 *   2. 向 PID 发送 SIGTERM
 *   3. 等待最多 5s，未退出则发送 SIGKILL
 *   4. 清理状态文件
 */

import fs from 'fs';
import path from 'path';
import {fileURLToPath} from 'url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const PROJECT_ROOT = path.resolve(__dirname, '../../..');

const scriptName = path.basename(fileURLToPath(import.meta.url));

function usage() {
  console.log(`Usage: node ${scriptName} <scene_dir>

停止 Motion Canvas Vite dev server。

Arguments:
  <scene_dir>    场景目录路径，如 scenes/01_test_mc/`);
  process.exit(0);
}

if (process.argv.includes('--help') || process.argv.includes('-h')) usage();

const sceneDirArg = process.argv[2];
if (!sceneDirArg) {
  console.error('Error: scene_dir required');
  usage();
}

const sceneDir = path.resolve(PROJECT_ROOT, sceneDirArg);
const sceneName = path.basename(sceneDir);
const tmpDir = path.join(PROJECT_ROOT, '.agent', 'tmp', sceneName);
const statePath = path.join(tmpDir, 'state.json');

if (!fs.existsSync(statePath)) {
  console.log(`[stop] No state file found for ${sceneName}. Server may not be running.`);
  process.exit(0);
}

let state;
try {
  state = JSON.parse(fs.readFileSync(statePath, 'utf-8'));
} catch (err) {
  console.error(`[stop] Failed to parse state file: ${err.message}`);
  process.exit(1);
}

const pid = state.pid;
if (!pid) {
  console.log(`[stop] No PID in state file. Cleaning up stale state.`);
  cleanup(tmpDir);
  process.exit(0);
}

// 检查进程是否存在
try {
  process.kill(pid, 0);
} catch {
  console.log(`[stop] Process ${pid} already dead. Cleaning up state.`);
  cleanup(tmpDir);
  process.exit(0);
}

console.log(`[stop] Stopping dev server (PID ${pid})...`);

// 发送 SIGTERM 到进程组（确保子进程也被终止）
try {
  process.kill(-pid, 'SIGTERM');
} catch {
  // 进程组信号失败，尝试直接信号
  try {
    process.kill(pid, 'SIGTERM');
  } catch (err) {
    console.error(`[stop] SIGTERM failed: ${err.message}`);
  }
}

// 等待最多 5 秒
const exited = await new Promise(resolve => {
  const start = Date.now();
  const interval = setInterval(() => {
    try {
      process.kill(pid, 0);
      if (Date.now() - start > 5000) {
        clearInterval(interval);
        resolve(false);
      }
    } catch {
      clearInterval(interval);
      resolve(true);
    }
  }, 200);
});

if (!exited) {
  console.log(`[stop] Process did not exit within 5s, sending SIGKILL...`);
  try {
    process.kill(-pid, 'SIGKILL');
  } catch {
    try {
      process.kill(pid, 'SIGKILL');
    } catch (err) {
      console.error(`[stop] SIGKILL failed: ${err.message}`);
    }
  }
}

cleanup(tmpDir);
console.log(`[stop] Dev server stopped.`);

function cleanup(dir) {
  const files = ['state.json', 'dev.pid', 'dev.ready', 'dev.port'];
  for (const f of files) {
    const p = path.join(dir, f);
    if (fs.existsSync(p)) fs.unlinkSync(p);
  }
}
