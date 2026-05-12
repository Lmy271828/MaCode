"""engines/manimgl/src/templates/scene_base.py
MaCode Scene Base — ManimGL version.

Inherits from manimlib.scene.scene.Scene, providing:
1. Adapter path auto-injection (so `from utils.xxx` works without manual sys.path.insert)
2. Intro/outro animation hooks
3. Audio sync data loading convenience method

Usage::

    from templates.scene_base import MaCodeScene

    class MyScene(MaCodeScene):
        def construct(self):
            circle = Circle()
            self.play(ShowCreation(circle))
"""

from manimlib import *


class MaCodeScene(Scene):
    """MaCode unified scene base class.

    Subclasses can override class attributes to adjust behavior::

        class MyScene(MaCodeScene):
            AUTO_INTRO = True   # auto play intro()
            AUTO_OUTRO = True   # auto play outro()

            def construct(self):
                ...
    """

    # --- Subclass-overridable config ---
    AUTO_INTRO = False
    AUTO_OUTRO = False

    # ------------------------------------------------------------------
    # Lifecycle hooks
    # ------------------------------------------------------------------
    def setup(self):
        """Run before construct(). Injects path and optionally plays intro."""
        super().setup()
        self._inject_adapter_path()
        if self.AUTO_INTRO:
            self.intro()

    def tear_down(self):
        """Run after construct(). Optionally plays outro."""
        if self.AUTO_OUTRO:
            self.outro()
        super().tear_down()

    # ------------------------------------------------------------------
    # Internal utilities
    # ------------------------------------------------------------------
    def _inject_adapter_path(self):
        """Add engines/manimgl/src/ to sys.path so utils modules can be imported directly."""
        import sys
        from pathlib import Path

        adapter_src = Path(__file__).parent.parent
        path_str = str(adapter_src)
        if path_str not in sys.path:
            sys.path.insert(0, path_str)

    # ------------------------------------------------------------------
    # Subclass-overridable animation hooks
    # ------------------------------------------------------------------
    def intro(self):
        """Intro animation. Default no-op; override for unified intro effects."""
        pass

    def outro(self):
        """Outro animation. Default no-op; override for unified outro effects."""
        pass

    # ------------------------------------------------------------------
    # Convenience methods
    # ------------------------------------------------------------------
    def load_audio_sync(self, csv_path):
        """Load audio beat sync data.

        Args:
            csv_path: timeline.csv file path (supports :class:`pathlib.Path` or ``str``)

        Returns:
            :class:`~utils.audio_sync.AudioSync`: audio sync instance
        """
        from utils.audio_sync import AudioSync

        return AudioSync(csv_path)
