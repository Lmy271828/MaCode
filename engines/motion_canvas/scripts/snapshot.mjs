#!/usr/bin/env node
/**
 * Thin wrapper: delegates to render.mjs --snapshot (Sprint 3 unified CLI).
 *
 * Usage:
 *   snapshot.mjs <scene.tsx> <output.png> [time_sec] [fps] [width] [height]
 */
import { spawnSync } from 'child_process';
import path from 'path';
import { fileURLToPath } from 'url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const PROJECT_ROOT = path.resolve(__dirname, '../../..');
const renderMjs = path.join(__dirname, 'render.mjs');

const argv = process.argv.slice(2);
if (argv.includes('--help') || argv.includes('-h')) {
  console.log(`Usage: node snapshot.mjs <scene.tsx> <output.png> [time_sec] [fps] [width] [height]

Delegates to render.mjs --snapshot (see render.mjs --help).`);
  process.exit(0);
}

const res = spawnSync(process.execPath, [renderMjs, '--snapshot', ...argv], {
  cwd: PROJECT_ROOT,
  stdio: 'inherit',
  env: process.env,
});
process.exit(res.status === null ? 1 : res.status);
