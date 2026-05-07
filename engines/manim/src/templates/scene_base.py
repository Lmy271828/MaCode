"""engines/manim/src/templates/scene_base.py
MaCode 场景基类 — ManimCE 版本。

继承 MovingCameraScene，提供：
1. 适配层路径自动注入（使 `from utils.xxx` 可用，无需手动 sys.path.insert）
2. 开场/结尾动画钩子
3. 音频同步数据加载便利方法
4. 相机聚焦/自动缩放封装

用法::

    from templates.scene_base import MaCodeScene

    class MyScene(MaCodeScene):
        def construct(self):
            circle = Circle()
            self.play(Create(circle))
            self.focus_on(circle, zoom=1.5)
"""

from manim import *


class MaCodeScene(MovingCameraScene):
    """MaCode 统一场景基类。

    子类可通过覆盖类属性调整行为::

        class MyScene(MaCodeScene):
            AUTO_INTRO = True   # 自动播放 intro()
            AUTO_OUTRO = True   # 自动播放 outro()

            def construct(self):
                ...
    """

    # --- 子类可覆盖的配置 ---
    AUTO_INTRO = False
    AUTO_OUTRO = False

    # ------------------------------------------------------------------
    # 生命周期钩子
    # ------------------------------------------------------------------
    def setup(self):
        """在 construct() 之前运行。注入路径并可选播放开场。"""
        super().setup()
        self._inject_adapter_path()
        if self.AUTO_INTRO:
            self.intro()

    def tear_down(self):
        """在 construct() 之后运行。可选播放结尾。"""
        if self.AUTO_OUTRO:
            self.outro()
        super().tear_down()

    # ------------------------------------------------------------------
    # 内部工具
    # ------------------------------------------------------------------
    def _inject_adapter_path(self):
        """将 engines/manim/src/ 加入 sys.path，使 utils 模块可直接 import。"""
        import sys
        from pathlib import Path

        adapter_src = Path(__file__).parent.parent
        path_str = str(adapter_src)
        if path_str not in sys.path:
            sys.path.insert(0, path_str)

    # ------------------------------------------------------------------
    # 子类可覆盖的动画钩子
    # ------------------------------------------------------------------
    def intro(self):
        """开场动画。默认空操作；子类覆盖以实现统一开场效果。"""
        pass

    def outro(self):
        """结尾动画。默认空操作；子类覆盖以实现统一结尾效果。"""
        pass

    # ------------------------------------------------------------------
    # 便利方法
    # ------------------------------------------------------------------
    def load_audio_sync(self, csv_path):
        """加载音频节拍同步数据。

        Args:
            csv_path: timeline.csv 文件路径（支持 :class:`pathlib.Path` 或 ``str``）

        Returns:
            :class:`~utils.audio_sync.AudioSync`: 音频同步实例
        """
        from utils.audio_sync import AudioSync

        return AudioSync(csv_path)

    def focus_on(self, target, zoom=1.0, run_time=1.0):
        """移动相机聚焦到目标并可选缩放。

        Args:
            target: Mobject 或坐标点（如 ``np.array([1, 2, 0])``）
            zoom: 相机缩放倍率（1.0 = 不缩放）
            run_time: 动画时长（秒）
        """
        point = target.get_center() if hasattr(target, "get_center") else target

        anim = self.camera.frame.animate.move_to(point)
        if zoom != 1.0:
            anim = anim.scale(zoom)

        self.play(anim, run_time=run_time)

    def zoom_to_fit(self, mobjects, margin=0.5, run_time=1.0):
        """自动调整相机以包含所有对象（带边距）。

        Args:
            mobjects: Mobject 或 Mobject 列表
            margin: 边距比例
            run_time: 动画时长（秒）
        """
        if not isinstance(mobjects, list):
            mobjects = [mobjects]
        self.play(
            self.camera.auto_zoom(mobjects, margin=margin),
            run_time=run_time,
        )
