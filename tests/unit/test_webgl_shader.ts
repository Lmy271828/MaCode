/**
 * Unit tests for engines/motion_canvas/src/utils/webgl-shader.ts
 *
 * Tests the pure functions (adaptGLSL) that do not require a browser.
 * Run with: npx tsx tests/unit/test_webgl_shader.ts
 */

import {adaptGLSL} from '../../engines/motion_canvas/src/utils/webgl-shader';

let passed = 0;
let failed = 0;

function assertEqual(actual: string, expected: string, msg: string) {
  if (actual !== expected) {
    console.error(`FAIL: ${msg}`);
    console.error(`  Expected:\n${expected}`);
    console.error(`  Actual:\n${actual}`);
    failed++;
  } else {
    console.log(`PASS: ${msg}`);
    passed++;
  }
}

function assertContains(haystack: string, needle: string, msg: string) {
  if (!haystack.includes(needle)) {
    console.error(`FAIL: ${msg}`);
    console.error(`  Expected to contain: ${needle}`);
    console.error(`  Actual:\n${haystack}`);
    failed++;
  } else {
    console.log(`PASS: ${msg}`);
    passed++;
  }
}

function assertNotContains(haystack: string, needle: string, msg: string) {
  if (haystack.includes(needle)) {
    console.error(`FAIL: ${msg}`);
    console.error(`  Expected NOT to contain: ${needle}`);
    failed++;
  } else {
    console.log(`PASS: ${msg}`);
    passed++;
  }
}

// ── Test: adaptGLSL for vertex shader ──
const vert330 = `#version 330
in vec2 in_pos;
void main() {
  gl_Position = vec4(in_pos, 0.0, 1.0);
}`;

const vertAdapted = adaptGLSL(vert330, false);
assertContains(vertAdapted, '#version 300 es', 'vertex: version replaced');
assertNotContains(vertAdapted, '#version 330', 'vertex: old version removed');
assertContains(vertAdapted, 'in vec2 in_pos', 'vertex: in qualifier preserved');

// ── Test: adaptGLSL for fragment shader ──
const frag330 = `#version 330
uniform float time;
uniform vec2 resolution;
out vec4 fragColor;
void main() {
  fragColor = vec4(1.0, 0.0, 0.0, 1.0);
}`;

const fragAdapted = adaptGLSL(frag330, true);
assertContains(fragAdapted, '#version 300 es', 'fragment: version replaced');
assertContains(fragAdapted, 'precision mediump float;', 'fragment: precision added');
assertNotContains(fragAdapted, '#version 330', 'fragment: old version removed');
assertContains(fragAdapted, 'out vec4 fragColor', 'fragment: out qualifier preserved');
assertContains(fragAdapted, 'uniform float time', 'fragment: uniforms preserved');

// ── Test: adaptGLSL without version directive ──
const fragNoVersion = `uniform float time;
void main() {
  gl_FragColor = vec4(1.0);
}`;

const fragNoVersionAdapted = adaptGLSL(fragNoVersion, true);
assertContains(fragNoVersionAdapted, '#version 300 es', 'fragment no-version: version prepended');
assertContains(fragNoVersionAdapted, 'precision mediump float;', 'fragment no-version: precision added');

// ── Test: adaptGLSL does not double-add precision ──
const fragWithPrecision = `#version 300 es
precision highp float;
void main() {}`;

const fragWithPrecisionAdapted = adaptGLSL(fragWithPrecision, true);
const precisionCount = (fragWithPrecisionAdapted.match(/precision/g) || []).length;
assertEqual(
  String(precisionCount),
  '1',
  'fragment: precision not duplicated when already present'
);

// ── Summary ──
console.log(`\n${passed} passed, ${failed} failed`);
if (failed > 0) {
  process.exit(1);
}
