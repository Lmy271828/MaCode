#!/usr/bin/env node
/**
 * bin/dashboard-server.mjs
 * MaCode 实时仪表盘服务器 —— 纯文件系统消费，Agent 零感知。
 *
 * 设计原则：
 *   1. 只读文件系统，不写入任何状态
 *   2. 文本流是唯一真相源（.agent/progress/*.jsonl、.agent/log/*.log 等）
 *   3. Agent 不依赖本服务器，崩溃后自动重建视图
 *   4. 兼容 subagents 并发开发（显示多场景并行状态）
 *
 * 用法:
 *   node bin/dashboard-server.mjs [--port 3000] [--root .]
 *
 * 消费端:
 *   浏览器打开 http://localhost:3000/
 *   curl http://localhost:3000/api/state | jq .
 *   curl http://localhost:3000/api/events  # SSE 流
 */

import fs from 'fs';
import path from 'path';
import http from 'http';
import { fileURLToPath } from 'url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const PROJECT_ROOT = path.resolve(__dirname, '..');

if (process.argv.includes('--help') || process.argv.includes('-h')) {
  console.log(`Usage: node dashboard-server.mjs [--port 3000] [--root .]

MaCode real-time dashboard server —— filesystem-only consumption, Agent zero-awareness.

Options:
  --port <n>    HTTP server port (default: 3000)
  --root <dir>  Project root directory (default: current)

Endpoints:
  /              HTML dashboard
  /api/state     Full state JSON
  /api/events    SSE stream`);
  process.exit(0);
}

const args = process.argv.slice(2);
const PORT = parseInt(args.find((_, i) => args[i - 1] === '--port') || '3000', 10);
const ROOT = path.resolve(args.find((_, i) => args[i - 1] === '--root') || PROJECT_ROOT);

const AGENT_DIR = path.join(ROOT, '.agent');
const PROGRESS_DIR = path.join(AGENT_DIR, 'progress');
const TMP_DIR = path.join(AGENT_DIR, 'tmp');
const LOG_DIR = path.join(AGENT_DIR, 'log');
const CHECK_DIR = path.join(AGENT_DIR, 'check_reports');
const SIGNALS_DIR = path.join(AGENT_DIR, 'signals');
const _REPORTS_DIR = path.join(AGENT_DIR, 'reports');

// ── 工具函数 ──────────────────────────────────────────
function readJsonL(filePath) {
  if (!fs.existsSync(filePath)) return [];
  try {
    return fs.readFileSync(filePath, 'utf-8')
      .split('\n')
      .filter(Boolean)
      .map((line) => {
        try { return JSON.parse(line); } catch { return null; }
      })
      .filter(Boolean);
  } catch { return []; }
}

function readJson(filePath) {
  if (!fs.existsSync(filePath)) return null;
  try { return JSON.parse(fs.readFileSync(filePath, 'utf-8')); } catch { return null; }
}

function _tailLog(filePath, n = 20) {
  if (!fs.existsSync(filePath)) return [];
  try {
    const lines = fs.readFileSync(filePath, 'utf-8').split('\n').filter(Boolean);
    return lines.slice(-n);
  } catch { return []; }
}

function listShaderPreviews() {
  const previews = [];
  if (!fs.existsSync(TMP_DIR)) return previews;
  for (const dir of fs.readdirSync(TMP_DIR)) {
    if (!dir.startsWith('shader-preview-')) continue;
    const statePath = path.join(TMP_DIR, dir, 'state.json');
    const progressPath = path.join(PROGRESS_DIR, `${dir}.jsonl`);
    const progress = readJsonL(progressPath);
    const lastProgress = progress[progress.length - 1] || {};

    let hasPreviewServer = false;
    let previewUrl = null;
    if (fs.existsSync(statePath)) {
      try {
        const state = readJson(statePath);
        if (state?.pid) {
          try { process.kill(state.pid, 0); hasPreviewServer = true; } catch {}
        }
        previewUrl = state?.outputs?.url || null;
      } catch {}
    }

    // Check signals
    const sigDir = path.join(SIGNALS_DIR, 'per-scene', dir);
    let reviewNeeded = false;
    let rejected = false;
    if (fs.existsSync(sigDir)) {
      reviewNeeded = fs.existsSync(path.join(sigDir, 'review_needed'));
      rejected = fs.existsSync(path.join(sigDir, 'reject'));
    }

    previews.push({
      name: dir,
      type: 'shader-preview',
      progress: lastProgress.progress ?? 0,
      phase: lastProgress.phase || 'idle',
      status: lastProgress.status || 'idle',
      message: lastProgress.message || '',
      timestamp: lastProgress.timestamp || null,
      hasPreviewServer,
      previewUrl,
      reviewNeeded,
      rejected,
    });
  }
  return previews.sort((a, b) => {
    const aActive = a.hasPreviewServer ? 1 : 0;
    const bActive = b.hasPreviewServer ? 1 : 0;
    if (aActive !== bActive) return bActive - aActive;
    return a.name.localeCompare(b.name);
  });
}

function listScenes() {
  const scenes = [];
  if (!fs.existsSync(TMP_DIR)) return scenes;
  for (const dir of fs.readdirSync(TMP_DIR)) {
    if (dir.startsWith('.') || dir.startsWith('shader-preview-')) continue;
    const statePath = path.join(TMP_DIR, dir, 'state.json');
    const framesDir = path.join(TMP_DIR, dir, 'frames');
    const finalMp4 = path.join(TMP_DIR, dir, 'final.mp4');
    const progressPath = path.join(PROGRESS_DIR, `${dir}.jsonl`);
    const checkStatic = path.join(CHECK_DIR, `${dir}_static.json`);
    const checkFrames = path.join(CHECK_DIR, `${dir}_frames.json`);

    const progress = readJsonL(progressPath);
    const lastProgress = progress[progress.length - 1] || {};
    const checkStaticData = readJson(checkStatic);
    const checkFramesData = readJson(checkFrames);

    // 检查是否有活跃的 dev server（MC）
    let hasDevServer = false;
    let agentId = null;
    if (fs.existsSync(statePath)) {
      try {
        const state = readJson(statePath);
        if (state?.pid) {
          try { process.kill(state.pid, 0); hasDevServer = true; } catch {}
        }
        agentId = state?.agentId || null;
      } catch {}
    }

    // Check claim status
    let claimedBy = null;
    const claimPath = path.join(TMP_DIR, dir, '.claimed_by');
    if (fs.existsSync(claimPath)) {
      try {
        const claim = readJson(claimPath);
        if (claim?.agent_id) claimedBy = claim.agent_id;
      } catch {}
    }

    // 帧数量
    let frameCount = 0;
    if (fs.existsSync(framesDir)) {
      try { frameCount = fs.readdirSync(framesDir).filter((f) => f.endsWith('.png')).length; } catch {}
    }

    // 检查 issues 汇总
    const issues = [];
    for (const data of [checkStaticData, checkFramesData]) {
      if (!data) continue;
      for (const seg of data.segments || []) {
        if (seg.status !== 'pass') {
          issues.push({
            segment: seg.id,
            status: seg.status,
            issues: seg.issues || [],
          });
        }
      }
    }

    scenes.push({
      name: dir,
      progress: lastProgress.progress ?? (fs.existsSync(finalMp4) ? 1.0 : 0.0),
      phase: lastProgress.phase || (fs.existsSync(finalMp4) ? 'completed' : 'idle'),
      status: lastProgress.status || (fs.existsSync(finalMp4) ? 'completed' : 'idle'),
      message: lastProgress.message || '',
      timestamp: lastProgress.timestamp || null,
      frameCount,
      hasFinalMp4: fs.existsSync(finalMp4),
      hasDevServer,
      agentId,
      claimedBy,
      issues: issues.length > 0 ? issues : undefined,
      logPath: path.join(LOG_DIR, `*_${dir}.log`),
    });
  }
  // 活跃渲染优先，然后按名称排序
  return scenes.sort((a, b) => {
    const aActive = a.status === 'running' || a.hasDevServer ? 1 : 0;
    const bActive = b.status === 'running' || b.hasDevServer ? 1 : 0;
    if (aActive !== bActive) return bActive - aActive;
    return a.name.localeCompare(b.name);
  });
}

function getSignals() {
  const signals = {};
  if (!fs.existsSync(SIGNALS_DIR)) return signals;
  for (const file of fs.readdirSync(SIGNALS_DIR)) {
    const filePath = path.join(SIGNALS_DIR, file);
    try {
      const stat = fs.statSync(filePath);
      if (stat.isFile()) {
        signals[file] = {
          exists: true,
          mtime: stat.mtime.toISOString(),
          content: fs.readFileSync(filePath, 'utf-8').slice(0, 500),
        };
      }
    } catch {}
  }
  return signals;
}

function getDiskUsage() {
  try {
    fs.statSync(AGENT_DIR);
    // 粗略估计：遍历 .agent/tmp 下的所有文件
    let bytes = 0;
    function walk(dir) {
      for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
        const p = path.join(dir, entry.name);
        if (entry.isDirectory()) walk(p);
        else if (entry.isFile()) bytes += fs.statSync(p).size;
      }
    }
    if (fs.existsSync(TMP_DIR)) walk(TMP_DIR);
    return { bytes, gb: (bytes / 1024 / 1024 / 1024).toFixed(2) };
  } catch { return { bytes: 0, gb: '0.00' }; }
}

function getQueue() {
  const queueDir = path.join(AGENT_DIR, 'queue');
  const result = { pending: [], claimed: [], done: [] };
  if (!fs.existsSync(queueDir)) return result;
  for (const sub of ['pending', 'claimed', 'done']) {
    const subDir = path.join(queueDir, sub);
    if (!fs.existsSync(subDir)) continue;
    for (const file of fs.readdirSync(subDir)) {
      if (!file.endsWith('.json')) continue;
      const fp = path.join(subDir, file);
      try {
        const data = readJson(fp);
        if (data) result[sub].push({ file, ...data });
      } catch {}
    }
  }
  return result;
}

function buildState() {
  return {
    timestamp: new Date().toISOString(),
    scenes: listScenes(),
    shaderPreviews: listShaderPreviews(),
    signals: getSignals(),
    disk: getDiskUsage(),
    queue: getQueue(),
  };
}

// ── SSE 广播 ──────────────────────────────────────────
const sseClients = new Set();

function broadcast(data) {
  const payload = `data: ${JSON.stringify(data)}\n\n`;
  for (const res of sseClients) {
    try { res.write(payload); } catch { sseClients.delete(res); }
  }
}

// 监听文件系统变更并广播
function watchFilesystem() {
  let lastMtimes = new Map();

  function checkChanges() {
    const changed = [];
    const paths = [PROGRESS_DIR, SIGNALS_DIR, TMP_DIR];
    for (const dir of paths) {
      if (!fs.existsSync(dir)) continue;
      for (const file of fs.readdirSync(dir)) {
        const p = path.join(dir, file);
        try {
          const stat = fs.statSync(p);
          if (!lastMtimes.has(p)) {
            lastMtimes.set(p, stat.mtimeMs);
            changed.push(file);
          } else if (lastMtimes.get(p) !== stat.mtimeMs) {
            lastMtimes.set(p, stat.mtimeMs);
            changed.push(file);
          }
        } catch {}
      }
    }
    if (changed.length > 0) {
      broadcast({ type: 'update', changed, state: buildState() });
    }
  }

  // 轮询检查（避免 inotify 跨平台问题）
  setInterval(checkChanges, 2000);
}

// ── HTTP 路由 ─────────────────────────────────────────
function htmlDashboard() {
  return `<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>MaCode Dashboard</title>
<style>
  :root {
    --bg: #0d1117; --fg: #c9d1d9; --accent: #58a6ff;
    --ok: #3fb950; --warn: #d29922; --err: #f85149;
    --border: #30363d; --card: #161b22;
  }
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body {
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, monospace;
    background: var(--bg); color: var(--fg); font-size: 13px; line-height: 1.5;
    height: 100vh; display: flex; flex-direction: column; overflow: hidden;
  }
  header {
    padding: 12px 20px; border-bottom: 1px solid var(--border);
    display: flex; align-items: center; justify-content: space-between;
  }
  header h1 { font-size: 16px; font-weight: 600; color: var(--accent); }
  .status-bar { display: flex; gap: 16px; align-items: center; }
  .badge { padding: 2px 8px; border-radius: 12px; font-size: 11px; font-weight: 600; }
  .badge.ok { background: rgba(63,185,80,.15); color: var(--ok); }
  .badge.warn { background: rgba(210,153,34,.15); color: var(--warn); }
  .badge.err { background: rgba(248,81,73,.15); color: var(--err); }

  .layout { display: flex; flex: 1; overflow: hidden; }
  .sidebar { width: 260px; border-right: 1px solid var(--border); overflow-y: auto; }
  .scene-item {
    padding: 10px 16px; border-bottom: 1px solid var(--border); cursor: pointer;
    display: flex; align-items: center; justify-content: space-between;
    transition: background .15s;
  }
  .scene-item:hover, .scene-item.active { background: var(--card); }
  .scene-name { font-weight: 500; }
  .scene-meta { font-size: 11px; color: #8b949e; margin-top: 2px; }
  .scene-dot { width: 8px; height: 8px; border-radius: 50%; flex-shrink: 0; }
  .dot-running { background: var(--accent); animation: pulse 1.5s infinite; }
  .dot-completed { background: var(--ok); }
  .dot-idle { background: #484f58; }
  .dot-error { background: var(--err); }
  .dot-warn { background: var(--warn); }
  @keyframes pulse { 0%,100%{opacity:1} 50%{opacity:.4} }

  .main { flex: 1; overflow-y: auto; padding: 20px; }
  .grid { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; }
  .card {
    background: var(--card); border: 1px solid var(--border); border-radius: 8px; padding: 16px;
  }
  .card h3 { font-size: 12px; text-transform: uppercase; letter-spacing: .5px; color: #8b949e; margin-bottom: 12px; }
  .progress-bar { height: 6px; background: #21262d; border-radius: 3px; overflow: hidden; margin-top: 8px; }
  .progress-fill { height: 100%; background: var(--accent); border-radius: 3px; transition: width .3s; }
  .log-lines { font-family: ui-monospace, SFMono-Regular, monospace; font-size: 11px; color: #8b949e; max-height: 200px; overflow-y: auto; }
  .log-lines div { padding: 2px 0; border-bottom: 1px solid #21262d; }
  .issue-item { padding: 8px; background: rgba(248,81,73,.08); border-radius: 6px; margin-bottom: 8px; border-left: 3px solid var(--err); }
  .issue-item.warn { background: rgba(210,153,34,.08); border-left-color: var(--warn); }
  .signal-card { display: flex; align-items: center; gap: 8px; padding: 8px 12px; border-radius: 6px; background: #21262d; margin-bottom: 8px; }
  .signal-card.active { background: rgba(210,153,34,.15); color: var(--warn); }
  .frame-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(80px,1fr)); gap: 8px; }
  .frame-thumb { aspect-ratio: 16/9; background: #21262d; border-radius: 4px; display: flex; align-items: center; justify-content: center; font-size: 10px; color: #484f58; }
  .info-row { display: flex; justify-content: space-between; padding: 6px 0; border-bottom: 1px solid #21262d; }
  .info-row:last-child { border-bottom: none; }
  .info-label { color: #8b949e; }

  .rightbar { width: 280px; border-left: 1px solid var(--border); padding: 16px; overflow-y: auto; }
</style>
</head>
<body>
<header>
  <h1>MaCode Dashboard</h1>
  <div class="status-bar">
    <span id="connStatus" class="badge ok">Connected</span>
    <span id="sceneCount">0 scenes</span>
    <span id="diskUsage">0 GB</span>
    <span style="color:#484f58">|</span>
    <span style="color:#8b949e;font-size:11px">Agent writes filesystem only</span>
  </div>
</header>
<div class="layout">
  <aside class="sidebar" id="sceneList"></aside>
  <main class="main" id="mainPanel">
    <div style="color:#484f58;text-align:center;padding:60px 20px">
      Select a scene from the sidebar to view details.<br>
      <span style="font-size:11px">Agent progress is written to <code>.agent/progress/*.jsonl</code></span>
    </div>
  </main>
  <aside class="rightbar" id="rightPanel"></aside>
</div>

<script>
let state = { scenes: [], shaderPreviews: [], signals: {}, disk: { gb: '0.00' } };
let selectedScene = null;

function renderSceneList() {
  const el = document.getElementById('sceneList');
  const previews = state.shaderPreviews || [];
  const scenes = state.scenes || [];

  let html = '';

  // Shader Previews section
  if (previews.length > 0) {
    html += '<div style="padding:8px 16px;font-size:11px;text-transform:uppercase;letter-spacing:.5px;color:#8b949e;border-bottom:1px solid #21262d">Shader Previews</div>';
    html += previews.map(s => {
      const dotClass = s.hasPreviewServer ? 'dot-running' :
                       s.rejected ? 'dot-error' :
                       s.reviewNeeded ? 'dot-warn' : 'dot-completed';
      const isActive = selectedScene === s.name ? 'active' : '';
      return \`<div class="scene-item \${isActive}" onclick="selectScene('\${s.name}')">
        <div>
          <div class="scene-name">\${s.name.replace('shader-preview-', '')}</div>
          <div class="scene-meta">\${s.phase || 'idle'} · \${s.hasPreviewServer ? '● running' : s.rejected ? '✗ rejected' : s.reviewNeeded ? '⚠ review' : '○ idle'}</div>
        </div>
        <div class="scene-dot \${dotClass}"></div>
      </div>\`;
    }).join('');
  }

  // Scenes section
  if (scenes.length > 0) {
    if (previews.length > 0) {
      html += '<div style="padding:8px 16px;font-size:11px;text-transform:uppercase;letter-spacing:.5px;color:#8b949e;border-bottom:1px solid #21262d;border-top:1px solid #30363d;margin-top:4px">Scenes</div>';
    }
    html += scenes.map(s => {
      const dotClass = s.status === 'running' || s.hasDevServer ? 'dot-running' :
                       s.status === 'error' ? 'dot-error' :
                       s.hasFinalMp4 ? 'dot-completed' : 'dot-idle';
      const isActive = selectedScene === s.name ? 'active' : '';
      return \`<div class="scene-item \${isActive}" onclick="selectScene('\${s.name}')">
        <div>
          <div class="scene-name">\${s.name}</div>
          <div class="scene-meta">\${s.phase || 'idle'} · \${(s.progress * 100).toFixed(0)}% · \${s.frameCount}f</div>
        </div>
        <div class="scene-dot \${dotClass}"></div>
      </div>\`;
    }).join('');
  }

  if (!html) {
    html = '<div style="padding:20px;color:#484f58">No scenes or shader previews found.</div>';
  }

  el.innerHTML = html;
  const total = scenes.length + previews.length;
  document.getElementById('sceneCount').textContent = total + ' items';
  document.getElementById('diskUsage').textContent = state.disk.gb + ' GB';
}

function renderMainPanel() {
  let s = state.scenes.find(x => x.name === selectedScene);
  let isPreview = false;
  if (!s) {
    s = state.shaderPreviews.find(x => x.name === selectedScene);
    isPreview = true;
  }
  const el = document.getElementById('mainPanel');
  if (!s) {
    el.innerHTML = '<div style="color:#484f58;text-align:center;padding:60px 20px">Select a scene or shader preview to view details.</div>';
    return;
  }

  if (isPreview) {
    el.innerHTML = \`
      <div class="grid">
        <div class="card" style="grid-column:1/-1">
          <div style="display:flex;justify-content:space-between;align-items:center">
            <h2>\${s.name}</h2>
            <span class="badge \${s.hasPreviewServer ? 'ok' : s.rejected ? 'err' : s.reviewNeeded ? 'warn' : 'warn'}">\${s.hasPreviewServer ? 'running' : s.rejected ? 'rejected' : s.reviewNeeded ? 'review needed' : 'idle'}</span>
          </div>
          <div style="margin-top:8px;font-size:11px;color:#8b949e">\${s.message || ''} · \${s.timestamp || ''}</div>
        </div>
        <div class="card">
          <h3>Preview Info</h3>
          <div class="info-row"><span class="info-label">Server</span><span>\${s.hasPreviewServer ? '✓ Running' : '—'}</span></div>
          <div class="info-row"><span class="info-label">URL</span><span>\${s.previewUrl ? \`<a href="\${s.previewUrl}" target="_blank" style="color:var(--accent)">Open</a>\` : '—'}</span></div>
          <div class="info-row"><span class="info-label">Review</span><span>\${s.reviewNeeded ? '⚠ needed' : '—'}</span></div>
          <div class="info-row"><span class="info-label">Rejected</span><span>\${s.rejected ? '✗ yes' : '—'}</span></div>
        </div>
        <div class="card">
          <h3>Filesystem</h3>
          <div class="info-row"><span class="info-label">Progress</span><code>.agent/progress/\${s.name}.jsonl</code></div>
          <div class="info-row"><span class="info-label">State</span><code>.agent/tmp/\${s.name}/state.json</code></div>
          <div class="info-row"><span class="info-label">Signal</span><code>.agent/signals/per-scene/\${s.name}/</code></div>
        </div>
      </div>
    \`;
    return;
  }

  const issuesHtml = (s.issues || []).map(iss => {
    const sev = iss.status === 'error' ? 'err' : 'warn';
    return \`<div class="issue-item \${sev}">
      <strong>\${iss.segment}</strong> · \${iss.status}
      \${(iss.issues || []).map(i => '<div style="margin-top:4px;font-size:11px">' + (i.message || i.type) + '</div>').join('')}
    </div>\`;
  }).join('') || '<div style="color:#3fb950">All checks passed</div>';

  el.innerHTML = \`
    <div class="grid">
      <div class="card" style="grid-column:1/-1">
        <div style="display:flex;justify-content:space-between;align-items:center">
          <h2>\${s.name}</h2>
          <span class="badge \${s.status === 'running' ? 'ok' : s.status === 'error' ? 'err' : 'warn'}">\${s.status}</span>
        </div>
        <div class="progress-bar"><div class="progress-fill" style="width:\${(s.progress*100).toFixed(1)}%"></div></div>
        <div style="margin-top:8px;font-size:11px;color:#8b949e">\${s.message || ''} · \${s.timestamp || ''}</div>
      </div>
      <div class="card">
        <h3>Scene Info</h3>
        <div class="info-row"><span class="info-label">Phase</span><span>\${s.phase}</span></div>
        <div class="info-row"><span class="info-label">Frames</span><span>\${s.frameCount}</span></div>
        <div class="info-row"><span class="info-label">Final MP4</span><span>\${s.hasFinalMp4 ? '✓' : '—'}</span></div>
        <div class="info-row"><span class="info-label">Dev Server</span><span>\${s.hasDevServer ? '✓ Running' : '—'}</span></div>
      </div>
      <div class="card">
        <h3>Filesystem</h3>
        <div class="info-row"><span class="info-label">Progress</span><code>.agent/progress/\${s.name}.jsonl</code></div>
        <div class="info-row"><span class="info-label">Frames</span><code>.agent/tmp/\${s.name}/frames/</code></div>
        <div class="info-row"><span class="info-label">Logs</span><code>.agent/log/*_\${s.name}.log</code></div>
      </div>
      <div class="card" style="grid-column:1/-1">
        <h3>Check Results</h3>
        \${issuesHtml}
      </div>
    </div>
  \`;
}

function renderRightPanel() {
  const sigs = Object.entries(state.signals).map(([name, info]) => {
    const active = ['pause', 'abort', 'review_needed'].includes(name);
    return \`<div class="signal-card \${active ? 'active' : ''}">
      <strong>\${name}</strong>
      <span style="margin-left:auto;font-size:11px;color:#8b949e">\${info.mtime.slice(11,19)}</span>
    </div>\`;
  }).join('') || '<div style="color:#484f58">No signals</div>';

  document.getElementById('rightPanel').innerHTML = \`
    <h3 style="font-size:12px;text-transform:uppercase;letter-spacing:.5px;color:#8b949e;margin-bottom:12px">Signals</h3>
    \${sigs}
    <h3 style="font-size:12px;text-transform:uppercase;letter-spacing:.5px;color:#8b949e;margin:20px 0 12px">Resources</h3>
    <div class="info-row"><span class="info-label">Disk</span><span>\${state.disk.gb} GB</span></div>
    <div class="info-row"><span class="info-label">Scenes</span><span>\${state.scenes.length}</span></div>
    <div class="info-row"><span class="info-label">Running</span><span>\${state.scenes.filter(s => s.status === 'running' || s.hasDevServer).length}</span></div>
  \`;
}

function selectScene(name) {
  selectedScene = name;
  renderSceneList();
  renderMainPanel();
}

function update(data) {
  state = data.state || data;
  renderSceneList();
  renderMainPanel();
  renderRightPanel();
}

// 初始化 + SSE
fetch('/api/state').then(r => r.json()).then(update);

const evtSource = new EventSource('/api/events');
evtSource.onmessage = (e) => {
  try { update(JSON.parse(e.data)); } catch {}
};
evtSource.onerror = () => {
  document.getElementById('connStatus').textContent = 'Disconnected';
  document.getElementById('connStatus').className = 'badge err';
};
evtSource.onopen = () => {
  document.getElementById('connStatus').textContent = 'Connected';
  document.getElementById('connStatus').className = 'badge ok';
};
</script>
</body>
</html>`;
}

const server = http.createServer((req, res) => {
  const url = new URL(req.url, `http://localhost:${PORT}`);

  if (url.pathname === '/') {
    res.writeHead(200, { 'Content-Type': 'text/html; charset=utf-8' });
    res.end(htmlDashboard());
  } else if (url.pathname === '/api/state') {
    res.writeHead(200, { 'Content-Type': 'application/json' });
    res.end(JSON.stringify(buildState(), null, 2));
  } else if (url.pathname.startsWith('/api/scene/')) {
    const sceneName = decodeURIComponent(url.pathname.slice('/api/scene/'.length));
    const scene = listScenes().find((s) => s.name === sceneName);
    if (scene) {
      res.writeHead(200, { 'Content-Type': 'application/json' });
      res.end(JSON.stringify(scene, null, 2));
    } else {
      res.writeHead(404, { 'Content-Type': 'application/json' });
      res.end(JSON.stringify({ error: 'Scene not found' }));
    }
  } else if (url.pathname === '/api/queue') {
    res.writeHead(200, { 'Content-Type': 'application/json' });
    res.end(JSON.stringify(getQueue(), null, 2));
  } else if (url.pathname === '/api/events') {
    res.writeHead(200, {
      'Content-Type': 'text/event-stream',
      'Cache-Control': 'no-cache',
      'Connection': 'keep-alive',
    });
    sseClients.add(res);
    res.write(`data: ${JSON.stringify({ type: 'init', state: buildState() })}\n\n`);
    req.on('close', () => sseClients.delete(res));
  } else {
    res.writeHead(404);
    res.end('Not found');
  }
});

server.listen(PORT, () => {
  console.log(`[dashboard] MaCode Dashboard serving at http://localhost:${PORT}/`);
  console.log(`[dashboard] Text stream source: ${AGENT_DIR}`);
  console.log(`[dashboard] Agent is NOT aware of this server.`);
  watchFilesystem();
});
