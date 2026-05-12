from manim import *
from templates.scene_base import MaCodeScene
from utils.shader_bridge import ShaderMobject


class ShaderProductionScene(MaCodeScene):
    """Production validation for ShaderMobject — embed shader assets in ManimCE."""

    def construct(self):
        # Title
        title = Text("Shader Pipeline P1 Validation", font_size=36)
        title.to_edge(UP)
        self.play(Write(title))
        self.wait(0.5)

        # Embed a shader asset (Layer 2 → Layer 1 auto-render)
        # render=True triggers headless compilation if frames/ are missing
        shader = ShaderMobject(
            "assets/shaders/noise_heatmap/",
            render=True,
            duration=3,
            fps=30,
        )
        shader.scale(0.4)
        shader.next_to(title, DOWN, buff=0.5)

        self.play(FadeIn(shader))
        self.wait(3)  # Let the shader animation play

        # Mix with a regular Mobject
        circle = Circle(radius=1.5, color=YELLOW, fill_opacity=0.3)
        circle.next_to(shader, DOWN, buff=0.5)
        self.play(Create(circle))
        self.wait(1)

        # Fade everything out
        self.play(FadeOut(title), FadeOut(shader), FadeOut(circle))
        self.wait(0.5)
