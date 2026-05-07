"""engines/manimgl/src/utils/audio_builder.py
Audio operation convenience wrapper, based on ffmpeg_builder for common audio processing.

Makes pure-audio tasks more intuitive without manually handling -vn and other options.
"""

from typing import Optional, Union

from utils.ffmpeg_builder import FFMpeg


class AudioBuilder(FFMpeg):
    """FFmpeg builder focused on audio processing.

    Automatically disables video stream (``-vn``), simplifying common audio operations.

    Example::

        cmd = AudioBuilder() \\
            .input_audio("input.mp4") \\
            .fade(type="in", duration=0.5) \\
            .trim(start=2.0, end=8.0) \\
            .vol(0.8) \\
            .output_audio("output.aac")
    """

    def __init__(self):
        super().__init__()
        self.global_option("-vn")  # disable video

    def input_audio(self, path: str):
        """Add audio input (same as ``input()``, clearer semantics)."""
        return self.input(path)

    def fade(self, type: str, duration: float, start: Optional[float] = None):
        """Audio fade in / out (alias for ``afade``)."""
        self.audio.afade(type=type, duration=duration, start=start)
        return self

    def trim(self, start: Optional[float] = None, end: Optional[float] = None):
        """Audio trim (alias for ``atrim``)."""
        self.audio.atrim(start=start, end=end)
        return self

    def mix(self, inputs: int = 2):
        """Mix multiple audio streams (alias for ``amix``)."""
        self.audio.amix(inputs=inputs)
        return self

    def vol(self, gain: Union[float, str]):
        """Adjust volume (alias for ``volume``)."""
        self.audio.volume(gain=gain)
        return self

    def output_audio(self, path: str, acodec: str = "aac", bitrate: str = "192k", **kwargs):
        """Output audio file (default AAC encoding).

        Args:
            path: output file path
            acodec: audio encoder, default ``aac``
            bitrate: audio bitrate, default ``192k``
            **kwargs: other output options

        Returns:
            AudioBuilder: self, supports chaining
        """
        kwargs.setdefault("acodec", acodec)
        kwargs.setdefault("b:a", bitrate)
        return self.output(path, **kwargs)
