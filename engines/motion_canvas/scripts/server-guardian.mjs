#!/usr/bin/env node
/**
 * engines/motion_canvas/scripts/server-guardian.mjs
 * Dev Server 懒回收守护进程。
 *
 * 用法:
 *   server-guardian.mjs [--daemon] [--ttl <minutes>]
 *
 * 模式:
 *   默认        单次扫描，stop 所有超时的 dev server，然后退出
 *   --daemon    后台常驻，每 60s 扫描一次；无存活 server 时自毁
 *
 * 扫描逻辑:
 *   1. 遍历 .agent/tmp/*\/state.json
 *   2. 检查 pid 是否存活
 *   3. 检查 lastUsedAt 是否超过 TTL（默认 5min）
 *   4. 超时则调用 stop.mjs 停止并清理状态
 *   5. daemon 模式下：若连续 10min 无存活 server，guardian 自毁
 */

import fs from 'fs';
import path from 'path';
import {fileURLToPath} from 'url';
import {spawn} from 'child_process';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const PROJECT_ROOT = path.resolve(__dirname, '../../..');
const GUARDIAN_TMP = path.join(PROJECT_ROOT, '.agent', 'tmp', 'dev-guardian');
const GUARDIAN_STATE = path.join(GUARDIAN_TMP, 'state.json');
const DEFAULT_TTL_MS = parseInt(process.env.MCODE_GUARDIAN_TTL_MS, 10) || 5 * 60 * 1000;       // 5 分钟
const SCAN_INTERVAL_MS = parseInt(process.env.MCODE_GUARDIAN_INTERVAL_MS, 10) || 60 * 1000;          // 60 秒
const GUARDIAN_IDLE_TTL_MS = 10 * 60 * 1000; // 10 分钟无 server 则自毁

if (process.argv.includes('--help') || process.argv.includes('-h')) {
  console.log(`Usage: node server-guardian.mjs [--daemon] [--ttl <minutes>]

Dev Server lazy-reclaim guardian.

Options:
  --daemon         Run as background daemon, scan every 60s
  --ttl <min>      Idle TTL in minutes (default: 5)

Environment:
  MCODE_GUARDIAN_TTL_MS      Override TTL in milliseconds
  MCODE_GUARDIAN_INTERVAL_MS Override scan interval in milliseconds

Modes:
  Default   Single scan, stop idle servers, then exit
  --daemon  Keep running; self-destruct if no servers for 10min`);
  process.exit(0);
}

const isDaemon = process.argv.includes('--daemon');
const ttlArg = process.argv.indexOf('--ttl');
const TTL_MS = ttlArg >= 0 ? parseInt(process.argv[ttlArg + 1], 10) * 60 * 1000 : DEFAULT_TTL_MS;

fs.mkdirSync(GUARDIAN_TMP, {recursive: true});

// ── 单次扫描 ─────────────────────────────────────────

async function scanOnce() {
  const tmpRoot = path.join(PROJECT_ROOT, '.agent', 'tmp');
  let activeCount = 0;
  let stoppedCount = 0;

  let entries = [];
  try {
    entries = fs.readdirSync(tmpRoot, {withFileTypes: true});
  } catch {
    return {activeCount: 0, stoppedCount: 0};
  }

  for (const entry of entries) {
    if (!entry.isDirectory()) continue;
    if (entry.name === 'browser-pool' || entry.name === 'dev-guardian') continue;

    const statePath = path.join(tmpRoot, entry.name, 'state.json');
    if (!fs.existsSync(statePath)) continue;

    let state;
    try {
      state = JSON.parse(fs.readFileSync(statePath, 'utf-8'));
    } catch {
      continue;
    }

    if (!state.pid || !state.lastUsedAt) continue;

    // 检查进程是否存活
    const alive = isPidAlive(state.pid);
    if (!alive) {
      // 已死，清理孤儿状态
      cleanupState(tmpRoot, entry.name);
      continue;
    }

    activeCount++;

    // 检查是否超时
    const lastUsed = new Date(state.lastUsedAt).getTime();
    const idle = Date.now() - lastUsed;
    if (idle > TTL_MS) {
      console.log(`[guardian] ${entry.name}: idle ${Math.round(idle / 1000)}s > ${Math.round(TTL_MS / 1000)}s, stopping...`);
      const sceneDir = state.sceneDir || path.join(PROJECT_ROOT, 'scenes', entry.name);
      await stopServer(sceneDir);
      stoppedCount++;
    } else {
      console.log(`[guardian] ${entry.name}: active, idle ${Math.round(idle / 1000)}s`);
    }
  }

  return {activeCount, stoppedCount};
}

// ── Daemon 模式 ──────────────────────────────────────

async function runDaemon() {
  writeGuardianState(process.pid);
  console.log(`[guardian] Daemon started (pid=${process.pid}, ttl=${Math.round(TTL_MS / 1000)}s)`);

  let lastHadServers = Date.now();

  // 立即执行一次扫描
  let {activeCount} = await scanOnce();
  if (activeCount > 0) lastHadServers = Date.now();

  const timer = setInterval(async () => {
    const {activeCount: ac, stoppedCount: sc} = await scanOnce();
    if (ac > 0) {
      lastHadServers = Date.now();
    }
    if (sc > 0) {
      console.log(`[guardian] Stopped ${sc} idle server(s)`);
    }

    // 自毁检查：10 分钟无存活 server
    const guardianIdle = Date.now() - lastHadServers;
    if (ac === 0 && guardianIdle > GUARDIAN_IDLE_TTL_MS) {
      console.log(`[guardian] No servers for ${Math.round(guardianIdle / 1000)}s, shutting down`);
      clearInterval(timer);
      cleanupGuardianState();
      process.exit(0);
    }
  }, SCAN_INTERVAL_MS);

  // 信号处理
  function shutdown() {
    clearInterval(timer);
    cleanupGuardianState();
    process.exit(0);
  }
  process.on('SIGTERM', shutdown);
  process.on('SIGINT', shutdown);
}

// ── 工具函数 ─────────────────────────────────────────

function isPidAlive(pid) {
  try {
    process.kill(pid, 0);
    return true;
  } catch {
    return false;
  }
}

function cleanupState(tmpRoot, sceneName) {
  const dir = path.join(tmpRoot, sceneName);
  for (const f of ['state.json', 'dev.pid', 'dev.ready', 'dev.port']) {
    try { fs.unlinkSync(path.join(dir, f)); } catch {}
  }
}

function stopServer(sceneDir) {
  return new Promise((resolve) => {
    const child = spawn(process.execPath, [
      path.join(__dirname, 'stop.mjs'),
      sceneDir,
    ], {
      cwd: PROJECT_ROOT,
      stdio: ['ignore', 'ignore', 'ignore'],
    });
    child.on('close', () => resolve());
    child.on('error', () => resolve());
    // 10s 超时
    setTimeout(() => {
      try { child.kill(); } catch {}
      resolve();
    }, 10000);
  });
}

function writeGuardianState(pid) {
  fs.writeFileSync(GUARDIAN_STATE, JSON.stringify({
    pid,
    startedAt: new Date().toISOString(),
    ttlMinutes: Math.round(TTL_MS / 60000),
  }, null, 2));
}

function cleanupGuardianState() {
  try { fs.unlinkSync(GUARDIAN_STATE); } catch {}
}

// ── CLI ──────────────────────────────────────────────

if (isDaemon) {
  // 检查是否已有 guardian 在运行
  if (fs.existsSync(GUARDIAN_STATE)) {
    try {
      const st = JSON.parse(fs.readFileSync(GUARDIAN_STATE, 'utf-8'));
      if (st.pid && isPidAlive(st.pid)) {
        console.log(`[guardian] Already running (pid=${st.pid}), exiting`);
        process.exit(0);
      }
    } catch {}
  }
  runDaemon();
} else {
  scanOnce().then(({activeCount, stoppedCount}) => {
    console.log(`[guardian] Scan complete: ${activeCount} active, ${stoppedCount} stopped`);
    process.exit(0);
  });
}
