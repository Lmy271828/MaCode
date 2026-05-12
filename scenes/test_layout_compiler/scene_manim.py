"""Auto-generated scene from layout_config.yaml.
Layout: lecture_3zones | Narrative: definition_reveal
"""

from manim import *
from templates.scene_base import MaCodeScene
from components.narrative_scene import NarrativeScene


class AutoScene(NarrativeScene):
    LAYOUT_PROFILE = "lecture_3zones"
    NARRATIVE_PROFILE = "definition_reveal"

    def construct(self):
        # Stage: statement (zone: title, type: text)
        self.stage("statement",
            Text("极限的定义"),
            MathTex(r"\lim_{x \to a} f(x) = L"),
        )

        # Stage: visual (zone: main_visual, type: visual)
        self.stage("visual",
            NumberLine(x_range=[-5, 5]),
        )

        # Stage: annotation (zone: annotation, type: text)
        self.stage("annotation",
            Text("对于任意 \\epsilon > 0，存在 \\delta > 0..."),
        )

        # Stage: example (zone: main_visual, type: visual)
        # TODO: No content allocated for stage 'example'
        pass
