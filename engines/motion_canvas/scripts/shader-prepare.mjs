#!/usr/bin/env node
/**
 * engines/motion_canvas/scripts/shader-prepare.mjs
 * Pre-render shader dependencies for a Motion Canvas scene.
 *
 * Usage:
 *   shader-prepare.mjs <scene_dir> --fps <n> --duration <sec> --width <n> --height <n>
 *
 * Design:
 *   - Pure execution tool: reads manifest, checks cache, invokes shader-render.py
 *   - No dev-server lifecycle, no orchestration decisions
 *   - Writes progress.jsonl entries for observability
 */

import fs from 'fs';
import path from 'path';
import {fileURLToPath} from 'url';
import {spawn} from 'child_process';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const PROJECT_ROOT = path.resolve(__dirname, '../../..');

const scriptName = path.basename(fileURLToPath(import.meta.url));

function usage() {
  console.log(`Usage: node ${scriptName} <scene_dir> [options]

Pre-render shader dependencies declared in manifest.json.

Options:
  --fps <n>         Frame rate (default: 30)
  --duration <sec>  Duration in seconds (default: 3)
  --width <n>       Resolution width (default: 1920)
  --height <n>      Resolution height (default: 1080)`);
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

const args = process.argv.slice(3);
let fps = 30, duration = 3, width = 1920, height = 1080;
for (let i = 0; i < args.length; i++) {
  switch (args[i]) {
    case '--fps': fps = parseInt(args[++i], 10); break;
    case '--duration': duration = parseFloat(args[++i]); break;
    case '--width': width = parseInt(args[++i], 10); break;
    case '--height': height = parseInt(args[++i], 10); break;
  }
}

// ── Progress logging ────────────────────────────────
const progressDir = path.join(PROJECT_ROOT, '.agent', 'progress');
fs.mkdirSync(progressDir, {recursive: true});
const progressPath = path.join(progressDir, `${sceneName}.jsonl`);

function writeProgress(phase, status, extra = {}) {
  const entry = JSON.stringify({
    timestamp: new Date().toISOString(),
    phase,
    status,
    ...extra,
  }) + '\n';
  fs.appendFileSync(progressPath, entry);
}

// ── Read manifest ───────────────────────────────────
const manifestPath = path.join(sceneDir, 'manifest.json');
if (!fs.existsSync(manifestPath)) {
  console.log('[shader-prepare] No manifest.json, skipping');
  process.exit(0);
}

let manifest = {};
try {
  manifest = JSON.parse(fs.readFileSync(manifestPath, 'utf-8'));
} catch (err) {
  console.error(`[shader-prepare] Failed to parse manifest.json: ${err.message}`);
  process.exit(1);
}

if (!manifest.shaders || !Array.isArray(manifest.shaders) || manifest.shaders.length === 0) {
  console.log('[shader-prepare] No shaders in manifest, skipping');
  process.exit(0);
}

const expectedFrames = Math.ceil(fps * duration);
let allOk = true;

writeProgress('shader', 'running', {
  shaders: manifest.shaders,
  expectedFrames,
  message: `Pre-rendering ${manifest.shaders.length} shader(s)`,
});

for (const shaderId of manifest.shaders) {
  const shaderAssetDir = path.join(PROJECT_ROOT, 'assets', 'shaders', shaderId);
  const shaderFramesDir = path.join(shaderAssetDir, 'frames');

  let needsRender = true;
  if (fs.existsSync(shaderFramesDir)) {
    const existing = fs.readdirSync(shaderFramesDir)
      .filter(f => f.startsWith('frame_') && f.endsWith('.png'));
    if (existing.length >= expectedFrames) {
      needsRender = false;
      console.log(`[shader-prepare] Shader ${shaderId}: ${existing.length} frames cached, skipping`);
    }
  }

  if (needsRender) {
    console.log(`[shader-prepare] Shader ${shaderId}: pre-rendering ${expectedFrames} frames...`);
    const result = await runCommand('python3', [
      path.join(PROJECT_ROOT, 'bin', 'shader-render.py'),
      shaderAssetDir,
      '--fps', String(fps),
      '--duration', String(duration),
      '--resolution', `${width}x${height}`,
    ]);
    if (result.code !== 0) {
      console.error(`[shader-prepare] Shader pre-render failed for ${shaderId}: ${result.stderr}`);
      allOk = false;
    }
  }
}

writeProgress('shader', 'completed', {
  ok: allOk,
  message: allOk ? 'All shaders ready' : 'Some shaders failed',
});

process.exit(allOk ? 0 : 1);

function runCommand(cmd, args, options = {}) {
  return new Promise((resolve) => {
    const child = spawn(cmd, args, {
      cwd: PROJECT_ROOT,
      stdio: ['ignore', 'pipe', 'pipe'],
      ...options,
    });
    let stdout = '';
    let stderr = '';
    child.stdout.on('data', d => stdout += d);
    child.stderr.on('data', d => stderr += d);
    child.on('close', code => resolve({code, stdout, stderr}));
  });
}
