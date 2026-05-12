/**
 * Effect Registry — resolve semantic effect IDs to shader asset paths.
 *
 * Loads assets/shaders/_registry.json at runtime and provides lookup
 * by asset ID.  This keeps scene code decoupled from filesystem paths.
 */

import type {ResolvedEffect} from './types';

let registryCache: {assets: Array<{id: string; path: string}>} | null = null;

export class EffectNotFoundError extends Error {
  constructor(id: string) {
    super(`Effect '${id}' not found in shader asset registry.`);
    this.name = 'EffectNotFoundError';
  }
}

async function loadRegistry(): Promise<{assets: Array<{id: string; path: string}>}> {
  if (registryCache) {
    return registryCache;
  }

  const response = await fetch('/assets/shaders/_registry.json');
  if (!response.ok) {
    throw new Error(
      `Failed to load shader registry: ${response.status} ${response.statusText}`
    );
  }

  const data = (await response.json()) as {assets?: Array<{id: string; path: string}>};
  if (!data.assets || !Array.isArray(data.assets)) {
    throw new Error('Shader registry missing "assets" array.');
  }

  registryCache = data as {assets: Array<{id: string; path: string}>};
  return registryCache;
}

/**
 * Resolve an effect ID to a shader asset path.
 *
 * @param id — Asset ID as defined in assets/shaders/_registry.json
 * @returns ResolvedEffect with src pointing to the asset directory
 * @throws EffectNotFoundError if the ID is not in the registry
 */
export async function resolveEffect(id: string): Promise<ResolvedEffect> {
  const registry = await loadRegistry();
  const asset = registry.assets.find((a) => a.id === id);
  if (!asset) {
    throw new EffectNotFoundError(id);
  }
  return {
    src: '/' + asset.path,
  };
}

/**
 * List all registered shader asset IDs.
 */
export async function listEffects(): Promise<string[]> {
  const registry = await loadRegistry();
  return registry.assets.map((a) => a.id);
}
