"""engines/manim/src/utils/audio_builder.py
音频操作便利包装器，基于 ffmpeg_builder 封装常用音频处理。

让纯音频任务更直观，无需手动处理 -vn 等选项。
"""

from typing import Optional, Union

from utils.ffmpeg_builder import FFMpeg


class AudioBuilder(FFMpeg):
    """专注于音频处理的 FFmpeg 构建器。

    自动禁用视频流（``-vn``），简化常见音频操作。

    用法示例::

        cmd = AudioBuilder() \\
            .input_audio("input.mp4") \\
            .fade(type="in", duration=0.5) \\
            .trim(start=2.0, end=8.0) \\
            .vol(0.8) \\
            .output_audio("output.aac")
    """

    def __init__(self):
        super().__init__()
        self.global_option("-vn")  # 禁用视频

    def input_audio(self, path: str):
        """添加音频输入（同 ``input()``，语义更清晰）。"""
        return self.input(path)

    def fade(self, type: str, duration: float, start: Optional[float] = None):
        """音频淡入/淡出（``afade`` 的别名）。"""
        self.audio.afade(type=type, duration=duration, start=start)
        return self

    def trim(self, start: Optional[float] = None, end: Optional[float] = None):
        """音频截取（``atrim`` 的别名）。"""
        self.audio.atrim(start=start, end=end)
        return self

    def mix(self, inputs: int = 2):
        """混合多路音频（``amix`` 的别名）。"""
        self.audio.amix(inputs=inputs)
        return self

    def vol(self, gain: Union[float, str]):
        """调整音量（``volume`` 的别名）。"""
        self.audio.volume(gain=gain)
        return self

    def output_audio(self, path: str, acodec: str = "aac", bitrate: str = "192k", **kwargs):
        """输出音频文件（默认 AAC 编码）。

        Args:
            path: 输出文件路径
            acodec: 音频编码器，默认 ``aac``
            bitrate: 音频码率，默认 ``192k``
            **kwargs: 其他输出选项

        Returns:
            AudioBuilder: self，支持链式调用
        """
        kwargs.setdefault("acodec", acodec)
        kwargs.setdefault("b:a", bitrate)
        return self.output(path, **kwargs)
