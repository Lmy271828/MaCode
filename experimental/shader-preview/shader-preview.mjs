#!/usr/bin/env node
/**
 * experimental/shader-preview/shader-preview.mjs
 * MaCode Shader Preview — NOT part of the supported CLI surface; for local experiments only.
 *
 * Design (Harness 2.0):
 *   - Pure Node.js http server, zero framework dependency
 *   - Reads shader.json + GLSL, serves WebGL 2 preview page
 *   - State externalized to .agent/tmp/shader-preview-{asset}/state.json
 *   - Progress streamed to .agent/progress/shader-preview-{asset}.jsonl
 *   - Signals written to .agent/signals/per-scene/shader-preview-{asset}/
 *   - Agent zero-awareness: humans use browser, Agents use shader-render.py
 *
 * Usage (from repo root):
 *   node experimental/shader-preview/shader-preview.mjs <asset_id> [--port <n>]
 */

import fs from 'fs';
import path from 'path';
import http from 'http';
import {fileURLToPath} from 'url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const PROJECT_ROOT = path.resolve(__dirname, '../..');

const args = process.argv.slice(2);
const assetId = args[0];
const portArg = args.indexOf('--port');
let PORT = portArg >= 0 ? parseInt(args[portArg + 1], 10) : 0;

if (!assetId || assetId === '--help' || assetId === '-h') {
  console.log(`Usage: node experimental/shader-preview/shader-preview.mjs <asset_id> [--port <n>]

Start a WebGL 2 shader preview server for a Layer 2 asset (experimental; not macode routing).

Arguments:
  <asset_id>     Shader asset ID from assets/shaders/_registry.json
  --port <n>     HTTP port (default: auto-detect 8765-8999)

Examples:
  node experimental/shader-preview/shader-preview.mjs lygia_circle_heatmap
  node experimental/shader-preview/shader-preview.mjs lygia_circle_heatmap --port 8765`);
  process.exit(0);
}

// ── 1. Resolve asset ──────────────────────────────────
const REGISTRY_PATH = path.join(PROJECT_ROOT, 'assets', 'shaders', '_registry.json');
let registry = {assets: []};
try {
  registry = JSON.parse(fs.readFileSync(REGISTRY_PATH, 'utf-8'));
} catch (e) {
  console.error(`[shader-preview] Cannot read registry: ${e.message}`);
  process.exit(1);
}

const asset = registry.assets.find(a => a.id === assetId);
if (!asset) {
  console.error(`[shader-preview] Asset '${assetId}' not found in registry.`);
  console.error(`  Run: macode shader list`);
  process.exit(1);
}

const shaderDir = path.resolve(PROJECT_ROOT, asset.path);
const shaderJsonPath = path.join(shaderDir, 'shader.json');
if (!fs.existsSync(shaderJsonPath)) {
  console.error(`[shader-preview] shader.json not found: ${shaderJsonPath}`);
  process.exit(1);
}

const spec = JSON.parse(fs.readFileSync(shaderJsonPath, 'utf-8'));

// ── 2. Read GLSL ──────────────────────────────────────
const glslCfg = spec.glsl || {};
const vertPath = path.join(shaderDir, glslCfg.vertex || 'vert.glsl');
const fragPath = path.join(shaderDir, glslCfg.fragment || 'frag.glsl');

let vertSrc = fs.readFileSync(vertPath, 'utf-8');
let fragSrc = fs.readFileSync(fragPath, 'utf-8');

// ── 3. GLSL transpile (desktop → WebGL 2) ─────────────
function transpileToWebGL2(src, isFrag = false) {
  let out = src;
  // Version
  out = out.replace(/#version\s+330/, '#version 300 es');
  // Precision for fragment
  if (isFrag && !out.includes('precision')) {
    out = 'precision highp float;\n' + out;
  }
  // texture2D / textureCube → texture
  out = out.replace(/\btexture2D\b/g, 'texture');
  out = out.replace(/\btextureCube\b/g, 'texture');
  // desktop GLSL uses 'in'/'out' in 330, WebGL 2 ES uses same
  // but fragment output must be 'out vec4 fragColor;' and we use it
  // Some shaders use 'gl_FragColor' directly — redirect
  out = out.replace(/\bgl_FragColor\b/g, 'fragColor');
  // Vertex: attribute → in (330 already uses in/out)
  // Ensure frag has an output declaration if missing
  if (isFrag && !out.includes('out vec4 fragColor')) {
    out = 'out vec4 fragColor;\n' + out;
  }
  return out;
}

const vertWebGL = transpileToWebGL2(vertSrc, false);
const fragWebGL = transpileToWebGL2(fragSrc, true);

// ── 4. Prepare directories ────────────────────────────
const taskName = `shader-preview-${assetId}`;
const tmpDir = path.join(PROJECT_ROOT, '.agent', 'tmp', taskName);
const progressPath = path.join(PROJECT_ROOT, '.agent', 'progress', `${taskName}.jsonl`);
const statePath = path.join(tmpDir, 'state.json');
const logPath = path.join(tmpDir, 'shader-preview.log');
const signalDir = path.join(PROJECT_ROOT, '.agent', 'signals', 'per-scene', taskName);
fs.mkdirSync(tmpDir, {recursive: true});
fs.mkdirSync(signalDir, {recursive: true});

// ── 5. Progress helper ────────────────────────────────
function writeProgress(phase, status, message = '') {
  const record = {
    timestamp: new Date().toISOString(),
    phase,
    status,
  };
  if (message) record.message = message;
  fs.appendFileSync(progressPath, JSON.stringify(record) + '\n');
}

// ── 6. State helper ───────────────────────────────────
function writeState(status, outputs = {}) {
  const state = {
    version: '1.0',
    tool: 'shader-preview.mjs',
    status,
    outputs,
    durationSec: Math.round((Date.now() - startedAt) / 1000),
    pid: process.pid,
    lastUsedAt: new Date().toISOString(),
  };
  fs.writeFileSync(statePath, JSON.stringify(state, null, 2));
}

const startedAt = Date.now();
writeProgress('init', 'running', `Starting preview for ${assetId}`);
writeState('running');

// ── 7. HTTP Server ────────────────────────────────────
function buildPreviewPage() {
  const uniforms = spec.uniforms || [];
  const uniformsJson = JSON.stringify(uniforms);
  const vertEscaped = JSON.stringify(vertWebGL);
  const fragEscaped = JSON.stringify(fragWebGL);

  return `<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Shader Preview: ${assetId}</title>
<style>
  :root { --bg:#0d1117; --fg:#c9d1d9; --accent:#58a6ff; --ok:#3fb950; --warn:#d29922; --err:#f85149; --border:#30363d; --card:#161b22; }
  * { box-sizing:border-box; margin:0; padding:0; }
  body { font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,monospace; background:var(--bg); color:var(--fg); font-size:13px; line-height:1.5; height:100vh; display:flex; overflow:hidden; }
  .left { flex:1; display:flex; flex-direction:column; }
  header { padding:12px 20px; border-bottom:1px solid var(--border); display:flex; align-items:center; justify-content:space-between; }
  header h1 { font-size:16px; font-weight:600; color:var(--accent); }
  .canvas-wrap { flex:1; display:flex; align-items:center; justify-content:center; background:#000; position:relative; }
  canvas { max-width:100%; max-height:100%; }
  .right { width:320px; border-left:1px solid var(--border); overflow-y:auto; padding:16px; }
  .section { margin-bottom:20px; }
  .section h3 { font-size:12px; text-transform:uppercase; letter-spacing:.5px; color:#8b949e; margin-bottom:12px; }
  .control { margin-bottom:12px; }
  .control label { display:block; font-size:12px; margin-bottom:4px; color:#8b949e; }
  .control input[type=range] { width:100%; }
  .control .val { font-size:11px; color:var(--accent); margin-top:2px; }
  .btn { padding:6px 12px; border:1px solid var(--border); background:var(--card); color:var(--fg); border-radius:6px; cursor:pointer; font-size:12px; margin-right:6px; }
  .btn:hover { border-color:var(--accent); }
  .btn.signal { border-color:var(--warn); color:var(--warn); }
  .btn.reject { border-color:var(--err); color:var(--err); }
  .btn.approve { border-color:var(--ok); color:var(--ok); }
  .signal-reason { width:100%; margin-top:8px; padding:6px; background:var(--bg); border:1px solid var(--border); color:var(--fg); border-radius:4px; font-size:12px; }
  .info { font-size:11px; color:#8b949e; margin-top:4px; }
  .status { padding:2px 8px; border-radius:12px; font-size:11px; font-weight:600; background:rgba(88,166,255,.15); color:var(--accent); }
</style>
</head>
<body>
<div class="left">
  <header>
    <h1>🔮 ${assetId}</h1>
    <span class="status" id="statusBadge">Running</span>
  </header>
  <div class="canvas-wrap">
    <canvas id="glcanvas" width="960" height="540"></canvas>
  </div>
</div>
<div class="right">
  <div class="section">
    <h3>Uniforms</h3>
    <div id="controls"></div>
  </div>
  <div class="section">
    <h3>Playback</h3>
    <button class="btn" id="btnPlay">▶ Play</button>
    <button class="btn" id="btnPause">⏸ Pause</button>
    <button class="btn" id="btnExport">💾 Export PNG</button>
  </div>
  <div class="section">
    <h3>Human Signal</h3>
    <button class="btn signal" onclick="sendSignal('review_needed')">🟡 Review</button>
    <button class="btn reject" onclick="sendSignal('reject')">🔴 Reject</button>
    <button class="btn approve" onclick="sendSignal('approve')">🟢 Approve</button>
    <textarea class="signal-reason" id="signalReason" placeholder="Reason / override / suggested fix (optional)"></textarea>
    <div class="info" id="signalResult"></div>
  </div>
  <div class="section">
    <h3>Info</h3>
    <div class="info">Resolution: ${(spec.render?.resolution||[960,540]).join('x')}</div>
    <div class="info">Duration: ${spec.render?.duration||3}s</div>
    <div class="info">FPS: ${spec.render?.fps||30}</div>
    <div class="info">State: <code>.agent/tmp/${taskName}/state.json</code></div>
    <div class="info">Signal: <code>.agent/signals/per-scene/${taskName}/</code></div>
  </div>
</div>

<script>
const canvas = document.getElementById('glcanvas');
const gl = canvas.getContext('webgl2');
if (!gl) { alert('WebGL 2 not supported'); }

const uniformsSpec = ${uniformsJson};
const vertSrc = ${vertEscaped};
const fragSrc = ${fragEscaped};
let uniformValues = {};
let isPlaying = false;
let startTime = performance.now();
let pausedTime = 0;

function createShader(type, src) {
  const s = gl.createShader(type);
  gl.shaderSource(s, src);
  gl.compileShader(s);
  if (!gl.getShaderParameter(s, gl.COMPILE_STATUS)) {
    console.error('Shader compile error:', gl.getShaderInfoLog(s));
    return null;
  }
  return s;
}

const prog = gl.createProgram();
const vs = createShader(gl.VERTEX_SHADER, vertSrc);
const fs = createShader(gl.FRAGMENT_SHADER, fragSrc);
gl.attachShader(prog, vs);
gl.attachShader(prog, fs);
gl.linkProgram(prog);
if (!gl.getProgramParameter(prog, gl.LINK_STATUS)) {
  console.error('Link error:', gl.getProgramInfoLog(prog));
}
gl.useProgram(prog);

// Full-screen quad
const buf = gl.createBuffer();
gl.bindBuffer(gl.ARRAY_BUFFER, buf);
gl.bufferData(gl.ARRAY_BUFFER, new Float32Array([-1,-1, 1,-1, -1,1, 1,1]), gl.STATIC_DRAW);
const posLoc = gl.getAttribLocation(prog, 'in_pos');
gl.enableVertexAttribArray(posLoc);
gl.vertexAttribPointer(posLoc, 2, gl.FLOAT, false, 0, 0);

// Uniform locations
const uLocs = {};
uniformsSpec.forEach(u => { uLocs[u.name] = gl.getUniformLocation(prog, u.name); });

// Build controls
const ctrlDiv = document.getElementById('controls');
uniformsSpec.forEach(u => {
  const div = document.createElement('div');
  div.className = 'control';
  let ctrlHtml = '<label>' + u.name + ' <span class="val" id="val-' + u.name + '"></span></label>';
  if (u.type === 'float' && u.animation?.enabled) {
    ctrlHtml += '<input type="range" id="ctrl-' + u.name + '" min="0" max="10" step="0.01">';
    uniformValues[u.name] = u.default || 0;
  } else if (u.type === 'float') {
    ctrlHtml += '<input type="range" id="ctrl-' + u.name + '" min="0" max="1" step="0.01">';
    uniformValues[u.name] = u.default || 0;
  } else if (u.type === 'vec3') {
    ctrlHtml += '<input type="color" id="ctrl-' + u.name + '">';
    uniformValues[u.name] = u.default || [0,0,0];
  } else {
    ctrlHtml += '<div class="info">' + JSON.stringify(u.default) + ' (read-only)</div>';
    uniformValues[u.name] = u.default;
  }
  div.innerHTML = ctrlHtml;
  ctrlDiv.appendChild(div);

  const el = document.getElementById('ctrl-' + u.name);
  if (!el) return;
  el.addEventListener('input', () => {
    if (u.type === 'vec3') {
      const hex = el.value;
      const r = parseInt(hex.slice(1,3),16)/255;
      const g = parseInt(hex.slice(3,5),16)/255;
      const b = parseInt(hex.slice(5,7),16)/255;
      uniformValues[u.name] = [r,g,b];
    } else {
      uniformValues[u.name] = parseFloat(el.value);
    }
    updateValLabel(u.name);
  });
  if (u.type === 'vec3' && Array.isArray(u.default)) {
    const toHex = (v) => { const c = Math.round(v*255).toString(16).padStart(2,'0'); return c; };
    el.value = '#' + toHex(u.default[0]) + toHex(u.default[1]) + toHex(u.default[2]);
  } else if (el.type === 'range') {
    el.value = u.default || 0;
  }
  updateValLabel(u.name);
});

function updateValLabel(name) {
  const el = document.getElementById('val-' + name);
  if (el) el.textContent = JSON.stringify(uniformValues[name]);
}

function setUniforms(time) {
  uniformsSpec.forEach(u => {
    const loc = uLocs[u.name];
    if (!loc) return;
    let val = uniformValues[u.name];
    if (u.name === 'time' && u.animation?.enabled && isPlaying) {
      val = time;
    }
    if (u.name === 'resolution') {
      gl.uniform2f(loc, canvas.width, canvas.height);
    } else if (u.type === 'float') {
      gl.uniform1f(loc, val);
    } else if (u.type === 'vec2') {
      gl.uniform2f(loc, val[0], val[1]);
    } else if (u.type === 'vec3') {
      gl.uniform3f(loc, val[0], val[1], val[2]);
    } else if (u.type === 'vec4') {
      gl.uniform4f(loc, val[0], val[1], val[2], val[3]);
    }
  });
}

function render(now) {
  let t = 0;
  if (isPlaying) {
    t = (now - startTime) / 1000;
    if (t > ${spec.render?.duration || 3}) { startTime = now; t = 0; }
  } else {
    t = pausedTime;
  }
  gl.viewport(0, 0, canvas.width, canvas.height);
  setUniforms(t);
  gl.drawArrays(gl.TRIANGLE_STRIP, 0, 4);
  if (isPlaying) requestAnimationFrame(render);
}
requestAnimationFrame(render);

document.getElementById('btnPlay').onclick = () => {
  if (!isPlaying) { startTime = performance.now() - pausedTime * 1000; isPlaying = true; requestAnimationFrame(render); }
};
document.getElementById('btnPause').onclick = () => {
  if (isPlaying) { pausedTime = (performance.now() - startTime) / 1000; isPlaying = false; }
};
document.getElementById('btnExport').onclick = () => {
  const link = document.createElement('a');
  link.download = '${assetId}_' + Date.now() + '.png';
  link.href = canvas.toDataURL();
  link.click();
};

function sendSignal(type) {
  const reason = document.getElementById('signalReason').value;
  fetch('/api/signal', {
    method: 'POST',
    headers: {'Content-Type':'application/json'},
    body: JSON.stringify({scene:'${taskName}', type, reason})
  }).then(r => r.json()).then(d => {
    document.getElementById('signalResult').textContent = 'Signal ' + type + ' sent at ' + new Date().toLocaleTimeString();
    document.getElementById('statusBadge').textContent = type === 'approve' ? 'Approved' : type === 'reject' ? 'Rejected' : 'Review Needed';
    document.getElementById('statusBadge').style.background = type === 'approve' ? 'rgba(63,185,80,.15)' : type === 'reject' ? 'rgba(248,81,73,.15)' : 'rgba(210,153,34,.15)';
    document.getElementById('statusBadge').style.color = type === 'approve' ? 'var(--ok)' : type === 'reject' ? 'var(--err)' : 'var(--warn)';
  });
}
</script>
</body>
</html>`;
}

// ── 8. Port probing ───────────────────────────────────
function findPort(start, end) {
  return new Promise((resolve) => {
    const s = http.createServer();
    s.listen(start, () => { s.close(() => resolve(start)); });
    s.on('error', () => {
      if (start < end) resolve(findPort(start + 1, end));
      else resolve(0);
    });
  });
}

async function main() {
  if (!PORT) PORT = await findPort(8765, 8999);
  if (!PORT) {
    console.error('[shader-preview] No available port in 8765-8999');
    process.exit(1);
  }

  const server = http.createServer((req, res) => {
    const url = new URL(req.url, `http://localhost:${PORT}`);

    if (url.pathname === '/' || url.pathname === '/preview') {
      res.writeHead(200, {'Content-Type': 'text/html; charset=utf-8'});
      res.end(buildPreviewPage());
    } else if (url.pathname === '/api/asset') {
      res.writeHead(200, {'Content-Type': 'application/json'});
      res.end(JSON.stringify({
        assetId,
        spec,
        glsl: { vertex: vertWebGL, fragment: fragWebGL },
      }, null, 2));
    } else if (url.pathname === '/api/registry') {
      res.writeHead(200, {'Content-Type': 'application/json'});
      res.end(JSON.stringify(registry, null, 2));
    } else if (url.pathname === '/api/signal' && req.method === 'POST') {
      let body = '';
      req.on('data', chunk => body += chunk);
      req.on('end', () => {
        try {
          const data = JSON.parse(body);
          const sceneDir = path.join(PROJECT_ROOT, '.agent', 'signals', 'per-scene', data.scene);
          fs.mkdirSync(sceneDir, {recursive: true});

          if (data.type === 'review_needed') {
            fs.writeFileSync(path.join(sceneDir, 'review_needed'), '');
          } else if (data.type === 'reject') {
            fs.writeFileSync(path.join(sceneDir, 'reject'), '');
            try { fs.unlinkSync(path.join(sceneDir, 'review_needed')); } catch {}
            const override = {
              action: 'reject',
              reason: data.reason || '',
              author: 'human',
              timestamp: new Date().toISOString(),
            };
            fs.writeFileSync(path.join(sceneDir, 'human_override.json'), JSON.stringify(override, null, 2));
          } else if (data.type === 'approve') {
            try { fs.unlinkSync(path.join(sceneDir, 'review_needed')); } catch {}
            try { fs.unlinkSync(path.join(sceneDir, 'reject')); } catch {}
          }

          res.writeHead(200, {'Content-Type': 'application/json'});
          res.end(JSON.stringify({ok: true, type: data.type}));
        } catch (e) {
          res.writeHead(400, {'Content-Type': 'application/json'});
          res.end(JSON.stringify({error: e.message}));
        }
      });
    } else {
      res.writeHead(404);
      res.end('Not found');
    }
  });

  server.listen(PORT, () => {
    const url = `http://localhost:${PORT}/preview`;
    console.log(JSON.stringify({
      asset: assetId,
      url,
      api: `http://localhost:${PORT}/api/asset`,
      port: PORT,
      pid: process.pid,
      stateFile: statePath,
      progressFile: progressPath,
    }, null, 2));
    writeProgress('preview', 'running', `Server listening on port ${PORT}`);
    writeState('running', {url, port: PORT});
  });

  // Graceful shutdown
  function shutdown() {
    writeProgress('preview', 'completed', 'Server stopped');
    writeState('stopped');
    server.close(() => process.exit(0));
  }
  process.on('SIGTERM', shutdown);
  process.on('SIGINT', shutdown);
}

main().catch(e => {
  console.error('[shader-preview] Fatal:', e);
  writeProgress('preview', 'failed', e.message);
  writeState('failed');
  process.exit(1);
});
