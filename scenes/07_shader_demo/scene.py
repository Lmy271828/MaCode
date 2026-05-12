from manimlib import *
from utils.shader_backend import Backend
from utils.shader_builder import Shader


class ShaderDemoScene(Scene):
    def construct(self):
        backend = Backend.from_hardware_profile()
        shader = Shader(backend=backend) \
            .uniform("time", "float") \
            .input("uv", "vec2") \
            .node("noise", frequency=3.0, octaves=4) \
            .node("colorize", palette="heatmap")

        vert, frag = shader.generate()

        # Save for inspection
        shader.save(".agent/tmp/07_shader_demo/shaders/")

        # Use a simple FullScreenRectangle with the shader
        # In ManimGL, we can apply shaders to mobjects
        # Note: ManimGL shader application varies by version
        # If direct shader setting is complex, just display the generated code as text

        # Fallback: display generated shader code
        vert_text = Text("Vertex Shader (" + backend.name + ")", font_size=24).to_edge(UP)
        frag_preview = Text(frag[:200].replace("\n", " ") + "...", font_size=14)
        frag_preview.next_to(vert_text, DOWN)

        self.add(vert_text, frag_preview)
        self.wait(3)
