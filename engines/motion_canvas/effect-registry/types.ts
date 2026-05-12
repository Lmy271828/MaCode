/**
 * Effect Registry types — declarative effect references for ShaderFrame.
 *
 * Effects are thin wrappers around shader assets defined in
 * assets/shaders/_registry.json.  They allow scene code to reference
 * shaders by semantic ID instead of raw directory path.
 */

export interface Effect {
  id: string;
  name: string;
  description?: string;
  /** Reference to an asset ID in assets/shaders/_registry.json */
  shaderAssetId: string;
  defaultUniforms?: Record<string, number | number[]>;
}

export interface ResolvedEffect {
  /** Resolved path to the shader asset directory (relative to Vite root). */
  src: string;
  defaultUniforms?: Record<string, number | number[]>;
}
