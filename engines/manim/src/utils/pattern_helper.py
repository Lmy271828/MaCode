"""engines/manim/src/utils/pattern_helper.py
MaCode 正则模式工厂 — 避免 Agent 手写 80+ 字符的原始 regex。

用法::

    from utils.pattern_helper import pattern

    # 数字模式
    pattern.number.int()        # r'[+-]?\\d+'
    pattern.number.float()      # r'[+-]?(?:\\d+\\.?\\d*|\\.\\d+)(?:[eE][+-]?\\d+)?'

    # 单位匹配（数字 + 空格 + 单位）
    pattern.unit("m/s")         # r'\\d+(?:\\.\\d+)?\\s*m/s'

    # 组合
    p = pattern.number.float() + pattern.string.whitespace() + pattern.unit("kg")
    pattern.match(p, "12.5 kg")
"""

import re
from typing import Optional, Pattern


# ------------------------------------------------------------------
# 1. 数字模式
# ------------------------------------------------------------------

class _NumberPatterns:
    """整数、浮点、十六进制、百分数等常见数字模式。"""

    @staticmethod
    def int() -> str:
        """有符号整数。"""
        return r"[+-]?\d+"

    @staticmethod
    def float() -> str:
        """有符号浮点数（支持科学计数法）。"""
        return r"[+-]?(?:\d+\.?\d*|\.\d+)(?:[eE][+-]?\d+)?"

    @staticmethod
    def hex() -> str:
        """十六进制整数（0x / 0X 前缀）。"""
        return r"0[xX][0-9a-fA-F]+"

    @staticmethod
    def percent() -> str:
        """百分数（如 12.5%）。"""
        return r"\d+(?:\.\d+)?%"


# ------------------------------------------------------------------
# 2. 字符串模式
# ------------------------------------------------------------------

class _StringPatterns:
    """引号字符串、空白字符等文本模式。"""

    @staticmethod
    def quoted(quote: str = '"') -> str:
        """双引号包裹的字符串（不含转义）。"""
        return rf"{quote}[^{quote}]*{quote}"

    @staticmethod
    def whitespace() -> str:
        """一个或多个空白字符。"""
        return r"\s+"


# ------------------------------------------------------------------
# 3. 时间 / 文件等预置模式
# ------------------------------------------------------------------

class _TimePatterns:
    """时间戳、持续时间等模式。"""

    @staticmethod
    def hms() -> str:
        """HH:MM:SS[.sss] 时间格式。"""
        return r"\d{1,2}:\d{2}:\d{2}(?:\.\d+)?"

    @staticmethod
    def duration() -> str:
        """持续时间（如 3.5s、200ms、2min）。"""
        return r"\d+(?:\.\d+)?\s*(?:s|sec|seconds|ms|min|minutes)"


class _FilePatterns:
    """文件路径等模式。"""

    @staticmethod
    def path(exts: Optional[tuple] = None) -> str:
        """常见文件路径（默认匹配 py/mp4/png/csv/json）。"""
        if exts is None:
            exts = ("py", "mp4", "png", "csv", "json")
        ext_group = "|".join(exts)
        return rf"[\w\-\./]+\.(?:{ext_group})"


# ------------------------------------------------------------------
# 4. 模式工厂门面
# ------------------------------------------------------------------

class _PatternFactory:
    """统一入口：pattern.number.int()、pattern.compile(...) 等。"""

    number = _NumberPatterns()
    string = _StringPatterns()
    time = _TimePatterns()
    file = _FilePatterns()

    @staticmethod
    def unit(u: str = r"[a-zA-Z]+(?:/[a-zA-Z]+)?") -> str:
        """生成 ``数字 + 可选空格 + 单位`` 的匹配模式。

        Args:
            u: 单位字符串，如 ``"m/s"``、``"kg"``。
               留空则使用通用单位占位符。

        Returns:
            str: 可直接用于 regex 的模式字符串

        示例::

            pattern.unit("m/s")   # -> r'\\d+(?:\\.\\d+)?\\s*m/s'
            pattern.unit("kg")    # -> r'\\d+(?:\\.\\d+)?\\s*kg'
        """
        return rf"\d+(?:\.\d+)?\s*{re.escape(u) if u != r'[a-zA-Z]+(?:/[a-zA-Z]+)?' else u}"

    @staticmethod
    def compile(p: str, flags: int = 0) -> Pattern:
        """编译模式字符串为 ``re.Pattern``。

        Args:
            p: 模式字符串（可由 ``+`` 拼接多个子模式）
            flags: 正则标志位，如 ``re.IGNORECASE``
        """
        return re.compile(p, flags)

    @staticmethod
    def match(p: str, text: str, flags: int = 0) -> Optional[re.Match]:
        """在 *text* 开头匹配模式 *p*。

        等价于 ``re.match(p, text, flags)``，但更方便链式调用。
        """
        return re.match(p, text, flags)

    @staticmethod
    def search(p: str, text: str, flags: int = 0) -> Optional[re.Match]:
        """在 *text* 中搜索第一个匹配 *p* 的位置。"""
        return re.search(p, text, flags)


# 全局单例
pattern = _PatternFactory()
