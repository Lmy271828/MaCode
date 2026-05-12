#!/usr/bin/env node
/**
 * engines/motion_canvas/scripts/browser-pool.mjs
 * Chromium Browser Pool —— 全局复用单个 Browser 实例，通过多 Context 隔离并发渲染。
 *
 * 模式:
 *   --server    作为独立守护进程启动（内部使用，由 client 自动拉起）
 *   默认导出     client API: acquireBrowser(), shutdownServer()
 *
 * 架构:
 *   - Server: chromium.launchServer() → HTTP 状态服务 + 空闲超时自毁
 *   - Client: 发现/等待 state.json → chromium.connect(wsEndpoint) → 创建 Context
 *   - 多进程安全: state.json + pid 存活检测 + 端口冲突规避
 *
 * 内存收益:
 *   4 幕并发: 4×150MB Chromium → 1×200MB Browser + 4×~20MB Context ≈ 280MB
 */

import fs from 'fs';
import path from 'path';
import http from 'http';
import {fileURLToPath} from 'url';
import {spawn} from 'child_process';
import {chromium} from 'playwright';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const PROJECT_ROOT = path.resolve(__dirname, '../../..');
const POOL_TMP = path.join(PROJECT_ROOT, '.agent', 'tmp', 'browser-pool');
const STATE_PATH = path.join(POOL_TMP, 'state.json');
const PORT_PATH = path.join(POOL_TMP, 'port.txt');
const IDLE_TIMEOUT_MS = 5 * 60 * 1000;   // 5 分钟无请求则自毁
const CHECK_INTERVAL_MS = 30 * 1000;      // 每 30s 检查一次
const STARTUP_TIMEOUT_MS = 30000;         // 等待 server 启动最多 30s

// ═══════════════════════════════════════════════════════════════
//  Server Mode
// ═══════════════════════════════════════════════════════════════

async function runServer() {
  fs.mkdirSync(POOL_TMP, {recursive: true});

  const browserServer = await chromium.launchServer({
    headless: true,
    args: [
      '--no-sandbox',
      '--disable-setuid-sandbox',
      '--disable-dev-shm-usage',
      '--disable-gpu',
    ],
  });

  const wsEndpoint = browserServer.wsEndpoint();
  const pid = process.pid;
  const startedAt = Date.now();
  let lastActive = startedAt;

  function writeState(port) {
    const state = {pid, wsEndpoint, startedAt, lastActive, port};
    fs.writeFileSync(STATE_PATH, JSON.stringify(state, null, 2));
  }

  const httpServer = http.createServer((req, res) => {
    // CORS
    res.setHeader('Access-Control-Allow-Origin', '*');
    res.setHeader('Access-Control-Allow-Methods', 'GET, POST, OPTIONS');
    if (req.method === 'OPTIONS') {
      res.writeHead(204);
      res.end();
      return;
    }

    if (req.url === '/status') {
      lastActive = Date.now();
      writeState(httpServer.address()?.port);
      res.writeHead(200, {'Content-Type': 'application/json'});
      res.end(JSON.stringify({
        status: 'ok',
        wsEndpoint,
        pid,
        uptime: Date.now() - startedAt,
        lastActive,
      }));
      return;
    }

    if (req.url === '/shutdown') {
      res.writeHead(200, {'Content-Type': 'application/json'});
      res.end(JSON.stringify({status: 'shutting_down'}));
      console.log('[browser-pool] Shutdown requested');
      setTimeout(() => {
        browserServer.close().then(() => process.exit(0));
      }, 100);
      return;
    }

    res.writeHead(404);
    res.end();
  });

  await new Promise((resolve, reject) => {
    httpServer.listen(0, '127.0.0.1', () => {
      const port = httpServer.address().port;
      fs.writeFileSync(PORT_PATH, String(port));
      writeState(port);
      console.log(`[browser-pool] Server pid=${pid} port=${port} ws=${wsEndpoint}`);
      resolve();
    });
    httpServer.once('error', reject);
  });

  // 空闲自毁
  const idleTimer = setInterval(() => {
    const idle = Date.now() - lastActive;
    if (idle > IDLE_TIMEOUT_MS) {
      console.log(`[browser-pool] Idle ${Math.round(idle / 1000)}s, shutting down`);
      clearInterval(idleTimer);
      browserServer.close().then(() => process.exit(0));
    }
  }, CHECK_INTERVAL_MS);

  // 信号清理
  function cleanup() {
    clearInterval(idleTimer);
    try { fs.unlinkSync(STATE_PATH); } catch {}
    try { fs.unlinkSync(PORT_PATH); } catch {}
    browserServer.close().then(() => process.exit(0));
  }
  process.on('SIGTERM', cleanup);
  process.on('SIGINT', cleanup);
  process.on('exit', () => {
    try { fs.unlinkSync(STATE_PATH); } catch {}
    try { fs.unlinkSync(PORT_PATH); } catch {}
  });
}

// ═══════════════════════════════════════════════════════════════
//  Client API
// ═══════════════════════════════════════════════════════════════

/**
 * 获取一个已连接到 Browser Pool 的 Playwright Browser 实例。
 * 调用方需负责创建/关闭 Context；禁止调用 browser.close()（会关闭全局 Browser）。
 * 使用完毕后直接让进程退出即可，ws 连接会自动断开。
 */
export async function acquireBrowser() {
  const state = await ensureServerRunning();
  await pingServer(state.port);
  const browser = await chromium.connect({wsEndpoint: state.wsEndpoint});
  return browser;
}

/**
 * 显式请求关闭 Browser Pool Server（通常不需要，server 会空闲自毁）。
 */
export async function shutdownServer() {
  if (!fs.existsSync(PORT_PATH)) return false;
  const port = parseInt(fs.readFileSync(PORT_PATH, 'utf-8'), 10);
  return new Promise((resolve) => {
    http.get(`http://127.0.0.1:${port}/shutdown`, (res) => {
      resolve(res.statusCode === 200);
    }).on('error', () => resolve(false));
  });
}

// ── 内部 ──────────────────────────────────────────────────────

async function ensureServerRunning() {
  // 1. 读取现有状态
  let state = readState();

  // 2. 验证 pid 存活
  if (state && state.pid) {
    const alive = isPidAlive(state.pid);
    if (!alive) {
      console.log(`[browser-pool] Stale server pid=${state.pid}, removing`);
      cleanupState();
      state = null;
    }
  }

  // 3. 尝试 ping 现有 server
  if (state?.port) {
    const ok = await pingServer(state.port);
    if (ok) return state;
    cleanupState();
    state = null;
  }

  // 4. 启动新 server
  console.log('[browser-pool] Starting pool server...');
  const scriptPath = fileURLToPath(import.meta.url);
  const child = spawn(process.execPath, [scriptPath, '--server'], {
    detached: true,
    stdio: ['ignore', 'ignore', 'ignore'],
  });
  child.unref();

  // 5. 轮询等待 state 文件
  const deadline = Date.now() + STARTUP_TIMEOUT_MS;
  while (Date.now() < deadline) {
    await sleep(500);
    state = readState();
    if (state?.wsEndpoint && isPidAlive(state.pid)) {
      // 再 ping 一次确认 HTTP 服务就绪
      const ok = await pingServer(state.port);
      if (ok) {
        console.log(`[browser-pool] Server ready at ${state.wsEndpoint}`);
        return state;
      }
    }
  }

  throw new Error('Browser pool server failed to start within 30s');
}

function readState() {
  if (!fs.existsSync(STATE_PATH)) return null;
  try {
    return JSON.parse(fs.readFileSync(STATE_PATH, 'utf-8'));
  } catch {
    return null;
  }
}

function cleanupState() {
  try { fs.unlinkSync(STATE_PATH); } catch {}
  try { fs.unlinkSync(PORT_PATH); } catch {}
}

function isPidAlive(pid) {
  try {
    process.kill(pid, 0);
    return true;
  } catch {
    return false;
  }
}

function pingServer(port) {
  return new Promise((resolve) => {
    const req = http.get(`http://127.0.0.1:${port}/status`, {timeout: 2000}, (res) => {
      resolve(res.statusCode === 200);
    });
    req.on('error', () => resolve(false));
    req.on('timeout', () => { req.destroy(); resolve(false); });
  });
}

function sleep(ms) {
  return new Promise(r => setTimeout(r, ms));
}

// ═══════════════════════════════════════════════════════════════
//  CLI Entry
// ═══════════════════════════════════════════════════════════════

if (process.argv.includes('--help') || process.argv.includes('-h')) {
  console.log(`Usage: node browser-pool.mjs [--server]

Chromium Browser Pool —— global reusable Browser instance via multi-Context isolation.

Options:
  --server    Start as standalone daemon (auto-spawned by client normally)

Client API (import in other modules):
  acquireBrowser()   → Promise<Browser>
  shutdownServer()   → Promise<boolean>`);
  process.exit(0);
}

if (process.argv.includes('--server')) {
  runServer().catch(err => {
    console.error('[browser-pool] Server error:', err);
    process.exit(1);
  });
}
