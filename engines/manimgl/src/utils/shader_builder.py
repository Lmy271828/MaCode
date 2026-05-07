"""engines/manimgl/src/utils/shader_builder.py
MaCode Shader Builder -- ManimGL version.

Provides a node-graph API for generating GLSL shaders without
hand-writing raw `void main() { ... }` or `uniform` declarations.

The builder is backend-aware: it adapts GLSL version and algorithm
choices based on the detected hardware (GPU vs CPU software rasteriser).

Usage::

    from utils.shader_builder import Shader

    s = Shader() \
        .uniform("time", "float") \
        .input("uv", "vec2") \
        .node("noise", frequency=2.0, octaves=4) \
        .node("colorize", palette="heatmap") \
        .output("frag_color")

    vert, frag = s.generate()
    # vert -> vertex shader string
    # frag -> fragment shader string
"""

from typing import Any

from utils.shader_backend import Backend


class ShaderNode:
    """Base class for shader nodes."""

    def __init__(self, name: str, **params: Any):
        self.name = name
        self.params = params

    def glsl(self) -> str:
        """Return GLSL code snippet for this node."""
        raise NotImplementedError


class NoiseNode(ShaderNode):
    """Simplex/Perlin-like noise node.

    Automatically selects the noise algorithm based on the backend:

    * **GPU** – Classic simplex noise (higher quality, better GPU performance).
    * **CPU** – Fast hash-based noise (lighter on software rasterisers).
    """

    def glsl(self) -> str:
        freq = self.params.get("frequency", 1.0)
        octaves = self.params.get("octaves", 4)
        backend = self.params.get("backend", Backend.CPU)

        if backend.noise_impl == "simplex":
            return f"""
    // Noise node: {self.name} (backend={backend.name}, impl=simplex)
    vec3 mod289_{self.name}(vec3 x) {{ return x - floor(x * (1.0 / 289.0)) * 289.0; }}
    vec2 mod289_{self.name}(vec2 x) {{ return x - floor(x * (1.0 / 289.0)) * 289.0; }}
    vec3 permute_{self.name}(vec3 x) {{ return mod289_{self.name}(((x*34.0)+1.0)*x); }}
    float snoise_{self.name}(vec2 v) {{
        const vec4 C = vec4(0.211324865405187, 0.366025403784439, -0.577350269189626, 0.024390243902439);
        vec2 i  = floor(v + dot(v, C.yy));
        vec2 x0 = v - i + dot(i, C.xx);
        vec2 i1;
        i1 = (x0.x > x0.y) ? vec2(1.0, 0.0) : vec2(0.0, 1.0);
        vec4 x12 = x0.xyxy + C.xxzz;
        x12.xy -= i1;
        i = mod289_{self.name}(i);
        vec3 p = permute_{self.name}(permute_{self.name}(i.y + vec3(0.0, i1.y, 1.0)) + i.x + vec3(0.0, i1.x, 1.0));
        vec3 m = max(0.5 - vec3(dot(x0,x0), dot(x12.xy,x12.xy), dot(x12.zw,x12.zw)), 0.0);
        m = m*m; m = m*m;
        vec3 x = 2.0 * fract(p * C.www) - 1.0;
        vec3 h = abs(x) - 0.5;
        vec3 ox = floor(x + 0.5);
        vec3 a0 = x - ox;
        m *= 1.79284291400159 - 0.85373472095314 * (a0*a0 + h*h);
        vec3 g;
        g.x = a0.x * x0.x + h.x * x0.y;
        g.yz = a0.yz * x12.xz + h.yz * x12.yw;
        return 130.0 * dot(m, g);
    }}
    float {self.name}_value = 0.0;
    {{
        float freq = {freq:.3f};
        int octaves = {octaves};
        vec2 p = uv * freq;
        float amp = 1.0;
        for(int i = 0; i < octaves; i++){{
            {self.name}_value += amp * snoise_{self.name}(p);
            p *= 2.0;
            amp *= 0.5;
        }}
    }}
"""
        else:
            return f"""
    // Noise node: {self.name} (backend={backend.name}, impl=hash)
    float {self.name}_value = 0.0;
    {{
        float freq = {freq:.3f};
        int octaves = {octaves};
        vec2 p = uv * freq;
        float amp = 1.0;
        for(int i = 0; i < octaves; i++){{
            {self.name}_value += amp * (sin(p.x * 12.9898 + p.y * 78.233) * 43758.5453 - floor(sin(p.x * 12.9898 + p.y * 78.233) * 43758.5453));
            p *= 2.0;
            amp *= 0.5;
        }}
    }}
"""


class GradientNode(ShaderNode):
    """Linear gradient node."""

    def glsl(self) -> str:
        direction = self.params.get("direction", "horizontal")
        colors = self.params.get("colors", [(0.0, 0.0, 0.0, 1.0), (1.0, 1.0, 1.0, 1.0)])
        c0 = f"vec4({colors[0][0]}, {colors[0][1]}, {colors[0][2]}, {colors[0][3]})"
        c1 = f"vec4({colors[1][0]}, {colors[1][1]}, {colors[1][2]}, {colors[1][3]})"
        t = "uv.x" if direction == "horizontal" else "uv.y"
        return f"""
    // Gradient node: {self.name}
    vec4 {self.name}_color = mix({c0}, {c1}, {t});
"""


class ColorizeNode(ShaderNode):
    """Map scalar value to color palette."""

    def glsl(self) -> str:
        palette = self.params.get("palette", "heatmap")
        src = self.params.get("source", "noise_value")
        if palette == "heatmap":
            palette_glsl = f"""
    vec3 {self.name}_rgb = vec3(
        smoothstep(0.0, 0.33, {src}) * (1.0 - smoothstep(0.33, 0.66, {src})) + smoothstep(0.66, 1.0, {src}),
        smoothstep(0.0, 0.5, {src}),
        1.0 - smoothstep(0.33, 0.66, {src})
    );"""
        elif palette == "grayscale":
            palette_glsl = f"vec3 {self.name}_rgb = vec3({src});"
        elif palette == "neon":
            palette_glsl = f"""
    vec3 {self.name}_rgb = vec3(
        sin({src} * 6.28318) * 0.5 + 0.5,
        sin({src} * 6.28318 + 2.094) * 0.5 + 0.5,
        sin({src} * 6.28318 + 4.189) * 0.5 + 0.5
    );"""
        else:
            palette_glsl = f"vec3 {self.name}_rgb = vec3({src});"
        return f"""
    // Colorize node: {self.name} (palette={palette})
    {palette_glsl}
    vec4 {self.name}_color = vec4({self.name}_rgb, 1.0);
"""


class TimeOscillateNode(ShaderNode):
    """Oscillate a value over time."""

    def glsl(self) -> str:
        speed = self.params.get("speed", 1.0)
        min_val = self.params.get("min", 0.0)
        max_val = self.params.get("max", 1.0)
        return f"""
    // TimeOscillate node: {self.name}
    float {self.name}_value = mix({min_val}, {max_val}, sin(time * {speed:.3f}) * 0.5 + 0.5);
"""


NODE_REGISTRY = {
    "noise": NoiseNode,
    "gradient": GradientNode,
    "colorize": ColorizeNode,
    "oscillate": TimeOscillateNode,
}


class Shader:
    """Node-graph shader builder for ManimGL.

    Generates complete vertex + fragment GLSL from a chain of nodes.
    Adapts output to the detected rendering backend (GPU, CPU, HEADLESS).
    """

    def __init__(self, backend: Backend | None = None):
        """Create a new Shader builder.

        Args:
            backend: Target backend.  When ``None`` the backend is auto-detected
                from ``.agent/hardware_profile.json`` (falls back to ``CPU``).
        """
        self._backend = backend if backend is not None else Backend.from_hardware_profile()
        self._uniforms: list[tuple[str, str]] = []
        self._inputs: list[tuple[str, str]] = []
        self._nodes: list[ShaderNode] = []
        self._output: str = "frag_color"

    # ------------------------------------------------------------------
    # Declarations
    # ------------------------------------------------------------------
    def uniform(self, name: str, glsl_type: str):
        """Declare a uniform variable.

        Args:
            name: variable name (e.g. "time")
            glsl_type: GLSL type (e.g. "float", "vec2", "vec4")
        """
        self._uniforms.append((name, glsl_type))
        return self

    def input(self, name: str, glsl_type: str):
        """Declare an input/varying variable (fragment shader receives from vertex)."""
        self._inputs.append((name, glsl_type))
        return self

    # ------------------------------------------------------------------
    # Nodes
    # ------------------------------------------------------------------
    def node(self, node_type: str, **params: Any):
        """Add a processing node.

        Available node types:
            - ``noise`` (frequency, octaves)
            - ``gradient`` (direction, colors)
            - ``colorize`` (palette, source)
            - ``oscillate`` (speed, min, max)

        The current backend is forwarded to the node so that algorithm
        choices (e.g. simplex vs hash noise) can be made automatically.
        """
        cls = NODE_REGISTRY.get(node_type)
        if cls is None:
            raise ValueError(f"Unknown node type: {node_type}. Available: {list(NODE_REGISTRY.keys())}")
        name = params.pop("name", f"node_{len(self._nodes)}")
        params.setdefault("backend", self._backend)
        self._nodes.append(cls(name, **params))
        return self

    def output(self, name: str = "frag_color"):
        """Set the output variable name (default ``frag_color``)."""
        self._output = name
        return self

    # ------------------------------------------------------------------
    # Code generation
    # ------------------------------------------------------------------
    def _generate_vertex(self) -> str:
        """Generate vertex shader using the backend's GLSL version."""
        # ManimGL simple vertex shader: pass through point + emit varying inputs
        varyings = "\n".join(f"out {t} {n};" for n, t in self._inputs)
        pass_varyings = "\n".join(f"    {n} = uv;" for n, t in self._inputs if n == "uv")
        return f"""{self._backend.glsl_version}

in vec3 point;
{varyings}

#INSERT emit_gl_Position.glsl

void main(){{
    emit_gl_Position(point);
{pass_varyings}
}}
"""

    def _generate_fragment(self) -> str:
        """Generate fragment shader using the backend's GLSL version."""
        uniforms = "\n".join(f"uniform {t} {n};" for n, t in self._uniforms)
        varyings = "\n".join(f"in {t} {n};" for n, t in self._inputs)

        body = "\n".join(node.glsl() for node in self._nodes)

        # Determine final color: use the last node's _color or _rgb output
        final = f"vec4(1.0, 1.0, 1.0, 1.0)"
        if self._nodes:
            last = self._nodes[-1]
            if hasattr(last, 'name'):
                final = f"{last.name}_color"

        return f"""{self._backend.glsl_version}

{uniforms}
{varyings}

out vec4 {self._output};

void main(){{
{body}
    {self._output} = {final};
}}
"""

    def generate(self) -> tuple[str, str]:
        """Generate (vertex_shader, fragment_shader) pair.

        Returns:
            tuple of GLSL source strings
        """
        return self._generate_vertex(), self._generate_fragment()

    def save(self, directory: str, prefix: str = "custom"):
        """Save generated shaders to files.

        Args:
            directory: output directory path
            prefix: filename prefix
        """
        import os
        os.makedirs(directory, exist_ok=True)
        vert, frag = self.generate()
        with open(os.path.join(directory, f"{prefix}_vert.glsl"), "w") as f:
            f.write(vert)
        with open(os.path.join(directory, f"{prefix}_frag.glsl"), "w") as f:
            f.write(frag)
        return directory
