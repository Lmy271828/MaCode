"""engines/manimgl/src/utils/pattern_helper.py
MaCode regex pattern factory — avoids Agents hand-writing 80+ character raw regexes.

Usage::

    from utils.pattern_helper import pattern

    # Number patterns
    pattern.number.int()        # r'[+-]?\\d+'
    pattern.number.float()      # r'[+-]?(?:\\d+\\.?\\d*|\\.\\d+)(?:[eE][+-]?\\d+)?'

    # Unit matching (number + space + unit)
    pattern.unit("m/s")         # r'\\d+(?:\\.\\d+)?\\s*m/s'

    # Composition
    p = pattern.number.float() + pattern.string.whitespace() + pattern.unit("kg")
    pattern.match(p, "12.5 kg")
"""

import re
from re import Pattern

# ------------------------------------------------------------------
# 1. Number patterns
# ------------------------------------------------------------------

class _NumberPatterns:
    """Integer, float, hex, percent, etc."""

    @staticmethod
    def int() -> str:
        """Signed integer."""
        return r"[+-]?\d+"

    @staticmethod
    def float() -> str:
        """Signed float (supports scientific notation)."""
        return r"[+-]?(?:\d+\.?\d*|\.\d+)(?:[eE][+-]?\d+)?"

    @staticmethod
    def hex() -> str:
        """Hex integer (0x / 0X prefix)."""
        return r"0[xX][0-9a-fA-F]+"

    @staticmethod
    def percent() -> str:
        """Percentage (e.g. 12.5%)."""
        return r"\d+(?:\.\d+)?%"


# ------------------------------------------------------------------
# 2. String patterns
# ------------------------------------------------------------------

class _StringPatterns:
    """Quoted strings, whitespace, etc."""

    @staticmethod
    def quoted(quote: str = '"') -> str:
        """Double-quoted string (no escape)."""
        return rf"{quote}[^{quote}]*{quote}"

    @staticmethod
    def whitespace() -> str:
        """One or more whitespace characters."""
        return r"\s+"


# ------------------------------------------------------------------
# 3. Time / file preset patterns
# ------------------------------------------------------------------

class _TimePatterns:
    """Timestamps, durations, etc."""

    @staticmethod
    def hms() -> str:
        """HH:MM:SS[.sss] time format."""
        return r"\d{1,2}:\d{2}:\d{2}(?:\.\d+)?"

    @staticmethod
    def duration() -> str:
        """Duration (e.g. 3.5s, 200ms, 2min)."""
        return r"\d+(?:\.\d+)?\s*(?:s|sec|seconds|ms|min|minutes)"


class _FilePatterns:
    """File paths, etc."""

    @staticmethod
    def path(exts: tuple | None = None) -> str:
        """Common file path (defaults to py/mp4/png/csv/json)."""
        if exts is None:
            exts = ("py", "mp4", "png", "csv", "json")
        ext_group = "|".join(exts)
        return rf"[\w\-\./]+\.(?:{ext_group})"


# ------------------------------------------------------------------
# 4. Pattern factory facade
# ------------------------------------------------------------------

class _PatternFactory:
    """Unified entry: pattern.number.int(), pattern.compile(...), etc."""

    number = _NumberPatterns()
    string = _StringPatterns()
    time = _TimePatterns()
    file = _FilePatterns()

    @staticmethod
    def unit(u: str = r"[a-zA-Z]+(?:/[a-zA-Z]+)?") -> str:
        """Generate ``number + optional space + unit`` matching pattern.

        Args:
            u: unit string, e.g. ``"m/s"``, ``"kg"``.
               Leave empty for generic unit placeholder.

        Returns:
            str: pattern string ready for regex

        Example::

            pattern.unit("m/s")   # -> r'\\d+(?:\\.\\d+)?\\s*m/s'
            pattern.unit("kg")    # -> r'\\d+(?:\\.\\d+)?\\s*kg'
        """
        return rf"\d+(?:\.\d+)?\s*{re.escape(u) if u != r'[a-zA-Z]+(?:/[a-zA-Z]+)?' else u}"

    @staticmethod
    def compile(p: str, flags: int = 0) -> Pattern:
        """Compile pattern string into ``re.Pattern``.

        Args:
            p: pattern string (can be concatenated with ``+``)
            flags: regex flags, e.g. ``re.IGNORECASE``
        """
        return re.compile(p, flags)

    @staticmethod
    def match(p: str, text: str, flags: int = 0) -> re.Match | None:
        """Match pattern *p* at the beginning of *text*.

        Equivalent to ``re.match(p, text, flags)``, but more convenient.
        """
        return re.match(p, text, flags)

    @staticmethod
    def search(p: str, text: str, flags: int = 0) -> re.Match | None:
        """Search for the first match of *p* in *text*."""
        return re.search(p, text, flags)


# Global singleton
pattern = _PatternFactory()
