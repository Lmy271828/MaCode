/**
 * ShaderFrame – Motion Canvas node for real-time WebGL shader rendering.
 *
 * Loads a shader asset directory (shader.json + vert.glsl + frag.glsl),
 * compiles the GLSL to WebGL2, and renders each frame in real time.
 *
 * Usage:
 *   import {ShaderFrame} from '../../engines/motion_canvas/src/components/ShaderFrame';
 *   // ...
 *   view.add(
 *     <ShaderFrame
 *       src="/assets/shaders/lygia_circle_heatmap"
 *       width={1920}
 *       height={1080}
 *     />
 *   );
 */

import {
  DependencyContext,
  SerializedVector2,
  SignalValue,
  SimpleSignal,
} from '@motion-canvas/core';
import {
  Rect,
  RectProps,
  initial,
  signal,
  nodeName,
} from '@motion-canvas/2d';
import type {DesiredLength} from '@motion-canvas/2d/lib/partials';
import {
  buildShaderProgram,
  renderFrame,
  disposeShaderProgram,
  type WebGLShaderProgram,
  type ShaderUniform,
} from '../utils/webgl-shader';
import {resolveEffect, EffectNotFoundError} from '../../effect-registry';

interface ShaderManifest {
  schema_version?: string;
  metadata?: { name?: string; description?: string };
  backend?: { target?: string; glsl_version?: string };
  glsl?: { vertex?: string; fragment?: string; geometry?: string | null };
  uniforms?: Array<{
    name: string;
    type: string;
    default: number | number[];
    animation?: { enabled?: boolean; from?: number; to?: number; easing?: string };
  }>;
  render?: { fps?: number; duration?: number; resolution?: number[] };
}

export interface ShaderFrameProps extends RectProps {
  /**
   * Path to the shader asset directory (relative to Vite root).
   * Must contain `shader.json`, `vert.glsl`, and `frag.glsl`.
   *
   * @example
   * ```tsx
   * src="/assets/shaders/lygia_circle_heatmap"
   * ```
   */
  src?: SignalValue<string | null>;

  /**
   * Semantic effect ID referencing an entry in
   * `assets/shaders/_registry.json`.  Mutually exclusive with `src`;
   * if both are provided `src` takes precedence and a console error
   * is emitted.
   *
   * @example
   * ```tsx
   * effect="lygia_circle_heatmap"
   * ```
   */
  effect?: SignalValue<string>;

  /**
   * Explicit time override in seconds. When negative (default) the node's
   * time is driven by `view.globalTime`.
   */
  time?: SignalValue<number>;
}

@nodeName('ShaderFrame')
export class ShaderFrame extends Rect {
  /**
   * {@inheritDoc ShaderFrameProps.src}
   */
  @initial(null)
  @signal()
  public readonly src: SimpleSignal<string | null, this>;

  /**
   * {@inheritDoc ShaderFrameProps.effect}
   */
  @initial('')
  @signal()
  public readonly effect: SimpleSignal<string, this>;

  /**
   * Internal time signal. Negative means "auto-sync with view.globalTime".
   */
  @initial(-1)
  @signal()
  protected readonly time: SimpleSignal<number, this>;

  private shaderProgram: WebGLShaderProgram | null = null;
  private resolvedEffectSrc: string | null = null;
  private shaderManifest: ShaderManifest | null = null;
  private canvas: HTMLCanvasElement | null = null;
  private frameData: ImageData | null = null;
  private outputCanvas: HTMLCanvasElement | null = null;
  private outputCtx: CanvasRenderingContext2D | null = null;
  private manifestLoaded = false;
  private widthOverride = 1920;
  private heightOverride = 1080;

  constructor(props: ShaderFrameProps) {
    super(props);
  }

  protected desiredSize(): SerializedVector2<DesiredLength> {
    const custom = super.desiredSize();
    if (custom.x === null && custom.y === null) {
      return {x: this.widthOverride, y: this.heightOverride};
    }
    return custom;
  }

  /**
   * Resolve the current playback time in seconds.
   */
  private getCurrentTime(): number {
    const explicit = this.time();
    if (explicit >= 0) {
      return explicit;
    }
    return this.view().globalTime();
  }

  /**
   * Resolve the effective src, handling effect → src translation.
   * Caches resolved effect paths to avoid redundant registry lookups.
   */
  private async resolveSrc(): Promise<string | null> {
    const srcVal = this.src();
    const effectVal = this.effect();

    if (srcVal && effectVal) {
      console.error(
        `[ShaderFrame] Both 'src' and 'effect' provided. Using 'src' (${srcVal}).`
      );
    }

    if (srcVal) {
      return srcVal;
    }

    if (effectVal) {
      if (!this.resolvedEffectSrc) {
        try {
          const resolved = await resolveEffect(effectVal);
          this.resolvedEffectSrc = resolved.src;
        } catch (err) {
          if (err instanceof EffectNotFoundError) {
            console.error(`[ShaderFrame] ${err.message}`);
          } else {
            console.error(`[ShaderFrame] Failed to resolve effect '${effectVal}': ${err}`);
          }
          return null;
        }
      }
      return this.resolvedEffectSrc;
    }

    return null;
  }

  /**
   * Load shader.json manifest.
   */
  private async loadManifest(): Promise<void> {
    if (this.manifestLoaded) return;

    const src = await this.resolveSrc();
    if (!src) {
      this.manifestLoaded = true;
      return;
    }

    try {
      const response = await fetch(`${src}/shader.json`);
      if (response.ok) {
        this.shaderManifest = await response.json() as ShaderManifest;
        const renderCfg = this.shaderManifest.render;
        if (renderCfg?.resolution) {
          this.widthOverride = renderCfg.resolution[0];
          this.heightOverride = renderCfg.resolution[1];
        }
      }
    } catch {
      // shader.json is optional
    }
    this.manifestLoaded = true;
  }

  /**
   * Initialize WebGL shader program (lazy, on first draw).
   */
  private async initShader(): Promise<void> {
    if (this.shaderProgram) return;

    const src = await this.resolveSrc();
    if (!src) return;

    // Load GLSL sources
    let vertSrc: string;
    let fragSrc: string;
    try {
      const vertFile = this.shaderManifest?.glsl?.vertex ?? 'vert.glsl';
      const fragFile = this.shaderManifest?.glsl?.fragment ?? 'frag.glsl';

      const [vertResp, fragResp] = await Promise.all([
        fetch(`${src}/${vertFile}`),
        fetch(`${src}/${fragFile}`),
      ]);

      if (!vertResp.ok) {
        console.error(`[ShaderFrame] Failed to load vertex shader: ${src}/${vertFile}`);
        return;
      }
      if (!fragResp.ok) {
        console.error(`[ShaderFrame] Failed to load fragment shader: ${src}/${fragFile}`);
        return;
      }

      vertSrc = await vertResp.text();
      fragSrc = await fragResp.text();
    } catch (err) {
      console.error(`[ShaderFrame] Error loading shader sources: ${err}`);
      return;
    }

    // Create offscreen canvas for WebGL
    this.canvas = document.createElement('canvas');
    this.canvas.width = this.widthOverride;
    this.canvas.height = this.heightOverride;

    // Create output canvas for drawImage
    this.outputCanvas = document.createElement('canvas');
    this.outputCanvas.width = this.widthOverride;
    this.outputCanvas.height = this.heightOverride;
    this.outputCtx = this.outputCanvas.getContext('2d')!;

    try {
      this.shaderProgram = buildShaderProgram(
        this.canvas,
        vertSrc,
        fragSrc,
        this.widthOverride,
        this.heightOverride,
      );
    } catch (err) {
      console.error(`[ShaderFrame] WebGL shader compilation failed: ${err}`);
      this.shaderProgram = null;
    }
  }

  /**
   * Build uniforms array from shader manifest + current time.
   */
  private buildUniforms(): ShaderUniform[] {
    const uniforms: ShaderUniform[] = [];
    const t = this.getCurrentTime();

    // Always add resolution
    uniforms.push({
      name: 'resolution',
      type: 'vec2',
      value: [this.widthOverride, this.heightOverride],
    });

    // Add time uniform
    uniforms.push({
      name: 'time',
      type: 'float',
      value: t,
    });

    // Add custom uniforms from manifest
    if (this.shaderManifest?.uniforms) {
      for (const u of this.shaderManifest.uniforms) {
        if (u.name === 'time' || u.name === 'resolution') continue;

        let value: number | number[] = u.default;

        // Handle animated uniforms
        if (u.animation?.enabled && u.animation.from !== undefined && u.animation.to !== undefined) {
          const progress = (t - (u.animation.from ?? 0)) / ((u.animation.to ?? 1) - (u.animation.from ?? 0));
          const clamped = Math.max(0, Math.min(1, progress));
          if (typeof value === 'number') {
            value = (u.animation.from ?? 0) + clamped * ((u.animation.to ?? 1) - (u.animation.from ?? 0));
          }
        }

        uniforms.push({
          name: u.name,
          type: this.mapUniformType(u.type),
          value,
        });
      }
    }

    return uniforms;
  }

  private mapUniformType(type: string): ShaderUniform['type'] {
    switch (type) {
      case 'float': return 'float';
      case 'vec2': return 'vec2';
      case 'vec3': return 'vec3';
      case 'vec4': return 'vec4';
      case 'int': return 'int';
      case 'mat4': return 'mat4';
      default: return 'float';
    }
  }

  /**
   * Render current frame to internal output canvas (called from draw).
   */
  private renderCurrentFrame(): void {
    if (!this.shaderProgram) return;

    const uniforms = this.buildUniforms();
    try {
      const data = renderFrame(this.shaderProgram, uniforms);
      this.frameData = data;

      if (data && this.outputCanvas && this.outputCtx) {
        this.outputCtx.putImageData(data, 0, 0);
      }
    } catch (err) {
      console.error(`[ShaderFrame] Render failed: ${err}`);
    }
  }

  protected draw(context: CanvasRenderingContext2D): void {
    // Lazy init + render
    if (!this.shaderProgram) {
      // Queue async init; this frame will be skipped
      DependencyContext.collectPromise(
        this.initShader().then(() => this.renderCurrentFrame()),
      );
    } else {
      this.renderCurrentFrame();
    }

    if (this.outputCanvas) {
      const size = this.computedSize();
      context.drawImage(this.outputCanvas, 0, 0, size.x, size.y);
    }

    super.draw(context);
  }

  protected async collectAsyncResources(): Promise<void> {
    await super.collectAsyncResources();
    await this.loadManifest();
    if (!this.shaderProgram) {
      await this.initShader();
    }
  }

  dispose(): void {
    if (this.shaderProgram) {
      disposeShaderProgram(this.shaderProgram);
      this.shaderProgram = null;
    }
    super.dispose();
  }
}
