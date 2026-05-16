"""engines/manim/src/utils/ffmpeg_builder.py
FFmpeg 命令构建器 —— 让 Coding Agent 摆脱手写 -vf "fade=t=in:st=0:d=0.5" 字符串。

提供流式 API，支持常见视频/音频滤镜以及复杂 filtergraph。
"""

import re
import shlex
import subprocess

# ------------------------------------------------------------------
# 1. 滤镜链构建器
# ------------------------------------------------------------------

class _FilterBuilder:
    """滤镜链构建器基类。"""

    def __init__(self):
        self._filters: list[str] = []

    def _add(self, expr: str):
        self._filters.append(expr)
        return self

    def build(self) -> str:
        """将所有滤镜用逗号连接。"""
        return ",".join(self._filters)


class VideoFilterBuilder(_FilterBuilder):
    """视频滤镜链构建器（-vf）。"""

    def fade(self, type: str, duration: float, start: float | None = None):
        """fade 滤镜：淡入/淡出。

        Args:
            type: "in" 或 "out"
            duration: 淡入/淡出时长（秒）
            start: 开始时间（秒）；fade out 时未提供则尝试自动从视频尾部计算

        Returns:
            VideoFilterBuilder: self，支持链式调用
        """
        if type not in ("in", "out"):
            raise ValueError(f"fade type must be 'in' or 'out', got {type!r}")
        if start is None:
            # fade_in 默认从 0 开始；fade_out 标记为自动计算
            start = 0 if type == "in" else -1
        expr = f"fade=t={type}:st={start}:d={duration}"
        return self._add(expr)

    def scale(self, w: int | str, h: int | str):
        """scale 滤镜：调整分辨率。"""
        return self._add(f"scale={w}:{h}")

    def crop(self, w: int | str, h: int | str, x: int = 0, y: int = 0):
        """crop 滤镜：裁剪画面。"""
        return self._add(f"crop={w}:{h}:{x}:{y}")

    def fps(self, n: int | float):
        """fps 滤镜：设置帧率。"""
        return self._add(f"fps={n}")

    def format(self, pix_fmt: str):
        """format 滤镜：设置像素格式。"""
        return self._add(f"format={pix_fmt}")

    def trim(self, start: float | None = None, end: float | None = None):
        """trim 滤镜：截取视频片段。"""
        parts = []
        if start is not None:
            parts.append(f"start={start}")
        if end is not None:
            parts.append(f"end={end}")
        return self._add(f"trim={':'.join(parts)}")

    def setpts(self, expr: str = "PTS-STARTPTS"):
        """setpts 滤镜：重置时间戳。"""
        return self._add(f"setpts={expr}")


class AudioFilterBuilder(_FilterBuilder):
    """音频滤镜链构建器（-af）。"""

    def afade(self, type: str, duration: float, start: float | None = None):
        """afade 滤镜：音频淡入/淡出。

        Args:
            type: "in" 或 "out"
            duration: 淡入/淡出时长（秒）
            start: 开始时间（秒）；afade out 时未提供则尝试自动从尾部计算

        Returns:
            AudioFilterBuilder: self，支持链式调用
        """
        if type not in ("in", "out"):
            raise ValueError(f"afade type must be 'in' or 'out', got {type!r}")
        if start is None:
            start = 0 if type == "in" else -1
        expr = f"afade=t={type}:st={start}:d={duration}"
        return self._add(expr)

    def atrim(self, start: float | None = None, end: float | None = None):
        """atrim 滤镜：截取音频片段。"""
        parts = []
        if start is not None:
            parts.append(f"start={start}")
        if end is not None:
            parts.append(f"end={end}")
        return self._add(f"atrim={':'.join(parts)}")

    def asetpts(self, expr: str = "PTS-STARTPTS"):
        """asetpts 滤镜：重置音频时间戳。"""
        return self._add(f"asetpts={expr}")

    def amix(self, inputs: int = 2):
        """amix 滤镜：混合多路音频。"""
        return self._add(f"amix=inputs={inputs}")

    def volume(self, gain: float | str):
        """volume 滤镜：调整音量。"""
        return self._add(f"volume={gain}")


# ------------------------------------------------------------------
# 2. 核心构建器
# ------------------------------------------------------------------

class _FilterProxy:
    """滤镜代理，将底层 FilterBuilder 的方法调用转发，但返回 FFMpeg 自身以支持链式 API。"""

    def __init__(self, ffmpeg: "FFMpeg", builder: _FilterBuilder):
        self._ffmpeg = ffmpeg
        self._builder = builder

    def __getattr__(self, name: str):
        real = getattr(self._builder, name)
        if not callable(real):
            return real

        def wrapper(*args, **kwargs):
            real(*args, **kwargs)
            return self._ffmpeg
        return wrapper


class FFMpeg:
    """FFmpeg 命令构建器。

    用法示例::

        cmd = FFMpeg() \\
            .input("video.mp4") \\
            .video.fade(type="in", duration=0.5) \\
            .video.fade(type="out", start=9.5, duration=0.5) \\
            .audio.afade(type="in", duration=0.5) \\
            .output("out.mp4", vcodec="libx264", acodec="aac")

        cmd.build()   # -> list of command args for subprocess
        cmd.command() # -> full shell command string
    """

    def __init__(self):
        self._inputs: list[str] = []
        self._video = VideoFilterBuilder()
        self._audio = AudioFilterBuilder()
        self._filter_complex: str | None = None
        self._output_path: str | None = None
        self._output_options: dict = {}
        self._global_options: list[str] = []
        self._duration: float | None = None  # 缓存时长，避免重复 ffprobe

    @property
    def video(self) -> "_FilterProxy":
        """视频滤镜访问器。"""
        return _FilterProxy(self, self._video)

    @property
    def audio(self) -> "_FilterProxy":
        """音频滤镜访问器。"""
        return _FilterProxy(self, self._audio)

    def input(self, path: str):
        """添加输入文件。

        Args:
            path: 输入媒体文件路径

        Returns:
            FFMpeg: self，支持链式调用
        """
        self._inputs.append(path)
        return self

    def filter_complex(self, expr: str):
        """设置复杂滤镜图（-filter_complex）。

        设置后将覆盖简单的 -vf / -af 滤镜链。
        """
        self._filter_complex = expr
        return self

    def append_filter_complex(self, expr: str):
        """追加复杂滤镜图表达式（用分号连接）。"""
        if self._filter_complex is None:
            self._filter_complex = expr
        else:
            self._filter_complex = f"{self._filter_complex};{expr}"
        return self

    def output(self, path: str, **options):
        """设置输出文件及编码选项。

        Args:
            path: 输出文件路径
            **options: 编码选项，如 ``vcodec="libx264"``、``acodec="aac"``、``crf=23`` 等

        Returns:
            FFMpeg: self，支持链式调用
        """
        self._output_path = path
        self._output_options = options
        return self

    def global_option(self, *args: str):
        """添加全局选项，如 ``-y``、``-hide_banner`` 等。"""
        self._global_options.extend(args)
        return self

    # ------------------------------------------------------------------
    # 内部辅助
    # ------------------------------------------------------------------

    def _probe_duration(self, input_path: str) -> float:
        """使用 ffprobe 查询媒体时长（秒）。"""
        if self._duration is not None:
            return self._duration
        try:
            result = subprocess.run(
                [
                    "ffprobe",
                    "-v", "error",
                    "-show_entries", "format=duration",
                    "-of", "default=noprint_wrappers=1:nokey=1",
                    input_path,
                ],
                capture_output=True,
                text=True,
                check=True,
            )
            self._duration = float(result.stdout.strip())
            return self._duration
        except Exception as exc:
            raise RuntimeError(
                f"Failed to probe duration for {input_path}: {exc}"
            ) from exc

    def _resolve_fade_starts(self):
        """解析并自动补全 fade_out / afade_out 的 start 参数。"""
        if not self._inputs:
            return

        # 视频 fade_out 自动计算
        for i, filt in enumerate(self._video._filters):
            if filt.startswith("fade=t=out:") and ":st=-1:" in filt:
                dur = self._probe_duration(self._inputs[0])
                m = re.search(r":d=([0-9.]+)", filt)
                if m:
                    fdur = float(m.group(1))
                    start = max(0.0, dur - fdur)
                    self._video._filters[i] = f"fade=t=out:st={start}:d={fdur}"

        # 音频 afade_out 自动计算
        for i, filt in enumerate(self._audio._filters):
            if filt.startswith("afade=t=out:") and ":st=-1:" in filt:
                dur = self._probe_duration(self._inputs[0])
                m = re.search(r":d=([0-9.]+)", filt)
                if m:
                    fdur = float(m.group(1))
                    start = max(0.0, dur - fdur)
                    self._audio._filters[i] = f"afade=t=out:st={start}:d={fdur}"

    def build(self) -> list[str]:
        """构建为子进程参数列表。

        Returns:
            list[str]: 可直接传给 ``subprocess.run([...])`` 的参数列表
        """
        self._resolve_fade_starts()

        args: list[str] = ["ffmpeg"]
        args.extend(self._global_options)

        for inp in self._inputs:
            args.extend(["-i", inp])

        if self._filter_complex is not None:
            args.extend(["-filter_complex", self._filter_complex])
        else:
            vf = self._video.build()
            if vf:
                args.extend(["-vf", vf])
            af = self._audio.build()
            if af:
                args.extend(["-af", af])

        if self._output_path:
            for k, v in self._output_options.items():
                args.extend([f"-{k}", str(v)])
            args.append(self._output_path)

        return args

    def command(self) -> str:
        """构建为可执行的 shell 命令字符串。

        Returns:
            str: 已正确转义的 shell 命令
        """
        return " ".join(shlex.quote(str(arg)) for arg in self.build())
