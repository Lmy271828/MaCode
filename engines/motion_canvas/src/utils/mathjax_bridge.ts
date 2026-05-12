/**
 * engines/motion_canvas/src/utils/mathjax_bridge.ts
 * MaCode MathJax bridge — render MathJax formulas for Motion Canvas scenes.
 *
 * Provides async `renderMath(formula: string): Promise<HTMLImageElement>` that
 * calls mathjax-node-cli or similar to produce an image usable in Motion Canvas.
 *
 * Usage:
 *   import {renderMath} from '../utils/mathjax_bridge';
 *
 *   export default makeScene2D(function* (view) {
 *     const img = yield* renderMath("E = mc^2");
 *     view.add(<Image src={img.src} width={400} height={100} />);
 *   });
 */

import {exec} from 'child_process';
import * as fs from 'fs';
import * as os from 'os';
import * as path from 'path';
import {promisify} from 'util';

const execAsync = promisify(exec);

const CACHE_DIR = path.join(os.tmpdir(), 'mancode_mathjax_cache');

function ensureCacheDir(): void {
  if (!fs.existsSync(CACHE_DIR)) {
    fs.mkdirSync(CACHE_DIR, {recursive: true});
  }
}

function formulaHash(formula: string): string {
  let hash = 0;
  for (let i = 0; i < formula.length; i++) {
    const char = formula.charCodeAt(i);
    hash = (hash << 5) - hash + char;
    hash |= 0;
  }
  return `mj_${Math.abs(hash).toString(36)}`;
}

/**
 * Render a MathJax formula to an image.
 *
 * Tries mathjax-node-cli first, then falls back to writing the formula as text
 * in a data URL so the scene can still build even if MathJax is unavailable.
 *
 * @param formula - LaTeX formula string, e.g. "E = mc^2"
 * @param options - Optional rendering config
 * @returns Promise resolving to an HTMLImageElement
 */
export async function renderMath(
  formula: string,
  options: {width?: number; height?: number; format?: 'svg' | 'png'} = {},
): Promise<HTMLImageElement> {
  ensureCacheDir();
  const fmt = options.format ?? 'svg';
  const hash = formulaHash(formula);
  const outPath = path.join(CACHE_DIR, `${hash}.${fmt}`);

  // Return cached image if available
  if (fs.existsSync(outPath)) {
    return loadImage(outPath);
  }

  // Try mathjax-node-cli
  try {
    if (fmt === 'svg') {
      await execAsync(
        `npx mathjax-node-cli --inline --speech=false --format=TeX '${formula.replace(/'/g, "'\\''")}' > '${outPath}'`,
      );
    } else {
      await execAsync(
        `npx mathjax-node-cli --inline --speech=false --format=TeX --output=${outPath} '${formula.replace(/'/g, "'\\''")}'`,
      );
    }
    return loadImage(outPath);
  } catch {
    // Fallback: write a placeholder SVG
    const fallbackSvg = `<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" width="400" height="60">
  <rect width="100%" height="100%" fill="#f0f0f0"/>
  <text x="50%" y="50%" dominant-baseline="middle" text-anchor="middle"
        font-family="serif" font-size="20" fill="#333">
    ${formula.replace(/</g, '&lt;').replace(/&/g, '&amp;')}
  </text>
</svg>`;
    fs.writeFileSync(outPath, fallbackSvg, 'utf-8');
    return loadImage(outPath);
  }
}

/** Load an image file into an HTMLImageElement. */
function loadImage(filePath: string): Promise<HTMLImageElement> {
  return new Promise((resolve, reject) => {
    const img = new Image();
    img.onload = () => resolve(img);
    img.onerror = (err) => reject(err);
    img.src = filePath;
  });
}

/**
 * Batch pre-render multiple formulas.
 *
 * @param formulas - Array of LaTeX formula strings
 * @returns Promise resolving to an array of HTMLImageElement
 */
export async function precompileFormulas(
  formulas: string[],
): Promise<HTMLImageElement[]> {
  return Promise.all(formulas.map((f) => renderMath(f)));
}
