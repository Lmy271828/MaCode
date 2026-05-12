/**
 * WebGL Shader Renderer for Motion Canvas.
 *
 * Compiles desktop GLSL (e.g. #version 330) to WebGL2 GLSL ES 3.0
 * and renders fullscreen quad shaders in the browser.
 */

export interface ShaderUniform {
  name: string;
  type: 'float' | 'vec2' | 'vec3' | 'vec4' | 'int' | 'mat4';
  value: number | number[] | Float32Array;
}

export interface WebGLShaderProgram {
  gl: WebGL2RenderingContext;
  program: WebGLProgram;
  uniforms: Map<string, WebGLUniformLocation>;
  vao: WebGLVertexArrayObject;
  framebuffer: WebGLFramebuffer | null;
  texture: WebGLTexture | null;
  width: number;
  height: number;
}

/**
 * Adapt desktop GLSL (#version 330) to WebGL2 GLSL ES 3.0.
 *
 * Transformations:
 *   - Replace #version 330 with #version 300 es + precision
 *   - If no #version present, prepend #version 300 es
 *   - Keep in/out, gl_FragCoord, uniforms as-is (ES 3.0 compatible)
 */
export function adaptGLSL(source: string, isFragment: boolean): string {
  let out = source;

  // Handle version directive
  if (out.includes('#version 330')) {
    out = out.replace('#version 330', '#version 300 es');
  } else if (!out.includes('#version')) {
    out = '#version 300 es\n' + out;
  }

  // Add precision for fragment shaders
  if (isFragment && !out.includes('precision')) {
    out = out.replace(/(#version 300 es\n)/, '$1precision mediump float;\n');
  }

  return out;
}

/**
 * Compile a shader and return the handle.
 */
function compileShader(
  gl: WebGL2RenderingContext,
  type: number,
  source: string,
): WebGLShader {
  const shader = gl.createShader(type)!;
  gl.shaderSource(shader, source);
  gl.compileShader(shader);

  if (!gl.getShaderParameter(shader, gl.COMPILE_STATUS)) {
    const info = gl.getShaderInfoLog(shader);
    gl.deleteShader(shader);
    throw new Error(`Shader compilation failed: ${info}\n--- Source ---\n${source}`);
  }

  return shader;
}

/**
 * Link vertex + fragment shaders into a program.
 */
function linkProgram(
  gl: WebGL2RenderingContext,
  vertShader: WebGLShader,
  fragShader: WebGLShader,
): WebGLProgram {
  const program = gl.createProgram()!;
  gl.attachShader(program, vertShader);
  gl.attachShader(program, fragShader);
  gl.linkProgram(program);

  if (!gl.getProgramParameter(program, gl.LINK_STATUS)) {
    const info = gl.getProgramInfoLog(program);
    gl.deleteProgram(program);
    throw new Error(`Program linking failed: ${info}`);
  }

  return program;
}

/**
 * Create a fullscreen quad VAO.
 */
function createFullscreenQuad(gl: WebGL2RenderingContext): WebGLVertexArrayObject {
  const vao = gl.createVertexArray()!;
  gl.bindVertexArray(vao);

  const verts = new Float32Array([
    -1, -1,
     1, -1,
    -1,  1,
     1, -1,
     1,  1,
    -1,  1,
  ]);

  const buf = gl.createBuffer();
  gl.bindBuffer(gl.ARRAY_BUFFER, buf);
  gl.bufferData(gl.ARRAY_BUFFER, verts, gl.STATIC_DRAW);

  const posLoc = 0; // location 0 for 'in_pos'
  gl.enableVertexAttribArray(posLoc);
  gl.vertexAttribPointer(posLoc, 2, gl.FLOAT, false, 0, 0);

  gl.bindVertexArray(null);
  return vao;
}

/**
 * Create an offscreen rendering target (texture + framebuffer).
 */
function createOffscreenTarget(
  gl: WebGL2RenderingContext,
  width: number,
  height: number,
): { framebuffer: WebGLFramebuffer; texture: WebGLTexture } {
  const texture = gl.createTexture()!;
  gl.bindTexture(gl.TEXTURE_2D, texture);
  gl.texImage2D(
    gl.TEXTURE_2D, 0, gl.RGBA8,
    width, height, 0,
    gl.RGBA, gl.UNSIGNED_BYTE, null,
  );
  gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MIN_FILTER, gl.LINEAR);
  gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MAG_FILTER, gl.LINEAR);
  gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_S, gl.CLAMP_TO_EDGE);
  gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_T, gl.CLAMP_TO_EDGE);

  const framebuffer = gl.createFramebuffer()!;
  gl.bindFramebuffer(gl.FRAMEBUFFER, framebuffer);
  gl.framebufferTexture2D(
    gl.FRAMEBUFFER, gl.COLOR_ATTACHMENT0,
    gl.TEXTURE_2D, texture, 0,
  );

  const status = gl.checkFramebufferStatus(gl.FRAMEBUFFER);
  if (status !== gl.FRAMEBUFFER_COMPLETE) {
    throw new Error(`Framebuffer incomplete: 0x${status.toString(16)}`);
  }

  gl.bindFramebuffer(gl.FRAMEBUFFER, null);
  return { framebuffer, texture };
}

/**
 * Build a WebGL shader program from vertex/fragment GLSL sources.
 *
 * @param canvas  Offscreen canvas for WebGL context
 * @param vertSrc Vertex shader source (desktop GLSL, will be adapted)
 * @param fragSrc Fragment shader source (desktop GLSL, will be adapted)
 * @param width   Render target width
 * @param height  Render target height
 */
export function buildShaderProgram(
  canvas: HTMLCanvasElement,
  vertSrc: string,
  fragSrc: string,
  width: number,
  height: number,
): WebGLShaderProgram {
  const gl = canvas.getContext('webgl2', {
    alpha: true,
    premultipliedAlpha: false,
    preserveDrawingBuffer: true,
  })!;

  if (!gl) {
    throw new Error('WebGL2 not available in this browser');
  }

  const vertAdapted = adaptGLSL(vertSrc, false);
  const fragAdapted = adaptGLSL(fragSrc, true);

  const vertShader = compileShader(gl, gl.VERTEX_SHADER, vertAdapted);
  const fragShader = compileShader(gl, gl.FRAGMENT_SHADER, fragAdapted);
  const program = linkProgram(gl, vertShader, fragShader);

  // Shaders can be detached after linking
  gl.detachShader(program, vertShader);
  gl.detachShader(program, fragShader);
  gl.deleteShader(vertShader);
  gl.deleteShader(fragShader);

  // Collect uniform locations
  const uniforms = new Map<string, WebGLUniformLocation>();
  const numUniforms = gl.getProgramParameter(program, gl.ACTIVE_UNIFORMS);
  for (let i = 0; i < numUniforms; i++) {
    const info = gl.getActiveUniform(program, i);
    if (info) {
      const loc = gl.getUniformLocation(program, info.name);
      if (loc) {
        uniforms.set(info.name, loc);
      }
    }
  }

  const vao = createFullscreenQuad(gl);
  const { framebuffer, texture } = createOffscreenTarget(gl, width, height);

  // Set viewport
  gl.viewport(0, 0, width, height);

  return {
    gl,
    program,
    uniforms,
    vao,
    framebuffer,
    texture,
    width,
    height,
  };
}

/**
 * Set a uniform value by name.
 */
export function setUniform(
  prog: WebGLShaderProgram,
  name: string,
  type: string,
  value: number | number[] | Float32Array,
): void {
  const gl = prog.gl;
  const loc = prog.uniforms.get(name);
  if (loc === undefined) return; // Uniform optimized out or not present

  gl.useProgram(prog.program);

  switch (type) {
    case 'float':
      gl.uniform1f(loc, value as number);
      break;
    case 'vec2':
      if (Array.isArray(value)) {
        gl.uniform2f(loc, value[0], value[1]);
      }
      break;
    case 'vec3':
      if (Array.isArray(value)) {
        gl.uniform3f(loc, value[0], value[1], value[2]);
      }
      break;
    case 'vec4':
      if (Array.isArray(value)) {
        gl.uniform4f(loc, value[0], value[1], value[2], value[3]);
      }
      break;
    case 'int':
      gl.uniform1i(loc, value as number);
      break;
    case 'mat4':
      gl.uniformMatrix4fv(loc, false, value as Float32Array);
      break;
    default:
      console.warn(`[webgl-shader] Unknown uniform type: ${type}`);
  }
}

/**
 * Render one frame to the offscreen framebuffer.
 *
 * @param prog     Shader program
 * @param uniforms Array of uniform values to set before draw
 * @returns        The rendered result as ImageData (or null if failed)
 */
export function renderFrame(
  prog: WebGLShaderProgram,
  uniforms: ShaderUniform[],
): ImageData | null {
  const gl = prog.gl;

  gl.bindFramebuffer(gl.FRAMEBUFFER, prog.framebuffer);
  gl.viewport(0, 0, prog.width, prog.height);
  gl.useProgram(prog.program);
  gl.bindVertexArray(prog.vao);

  // Set all uniforms
  for (const u of uniforms) {
    setUniform(prog, u.name, u.type, u.value);
  }

  gl.drawArrays(gl.TRIANGLES, 0, 6);

  // Read pixels
  const pixels = new Uint8ClampedArray(prog.width * prog.height * 4);
  gl.readPixels(0, 0, prog.width, prog.height, gl.RGBA, gl.UNSIGNED_BYTE, pixels);

  // Flip Y because WebGL y=0 is bottom-left
  const flipped = new Uint8ClampedArray(prog.width * prog.height * 4);
  for (let y = 0; y < prog.height; y++) {
    const srcRow = (prog.height - 1 - y) * prog.width * 4;
    const dstRow = y * prog.width * 4;
    for (let x = 0; x < prog.width * 4; x++) {
      flipped[dstRow + x] = pixels[srcRow + x];
    }
  }

  return new ImageData(flipped, prog.width, prog.height);
}

/**
 * Dispose all WebGL resources.
 */
export function disposeShaderProgram(prog: WebGLShaderProgram): void {
  const gl = prog.gl;
  gl.deleteProgram(prog.program);
  gl.deleteVertexArray(prog.vao);
  if (prog.framebuffer) gl.deleteFramebuffer(prog.framebuffer);
  if (prog.texture) gl.deleteTexture(prog.texture);
}
