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
            Text("Hi"),
        )

        # Stage: visual (zone: main_visual, type: visual)
        self.stage("visual",
            Circle(),
            Square(),
            Dot(),
            Circle(),
            Line(),
        )

        # Stage: annotation (zone: annotation, type: text)
        # TODO: No content allocated for stage 'annotation'
        pass

        # Stage: example (zone: main_visual, type: visual)
        # TODO: No content allocated for stage 'example'
        pass
