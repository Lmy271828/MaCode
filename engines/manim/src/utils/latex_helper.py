"""engines/manim/src/utils/latex_helper.py
MaCode LaTeX 辅助工具 — ManimCE 版本。

解决 Agent 使用 LaTeX 的三大痛点：
1. 中文渲染：默认 latex 不支持 Unicode，需手动配置 xelatex+ctex
2. 公式构建：常见数学结构（矩阵、分段函数、对齐方程）记忆成本高
3. 编译性能：批量公式场景预编译可显著加速

用法::

    from utils.latex_helper import ChineseMathTex, Math, tex_template_full

    # 中文公式（开箱即用）
    ChineseMathTex("\\text{欧拉公式: } e^{i\\pi} + 1 = 0")

    # 链式构建器
    Math("E = mc^2").red().scale(1.5)

    # 预配置模板（含完整数学包）
    t = tex_template_full()
    MathTex("\\bm{A}x = \\bm{b}", tex_template=t)
"""

from manim import MathTex, SingleStringMathTex, Tex, TexTemplate, VGroup, config
import warnings


# ------------------------------------------------------------------
# 1. 预配置模板
# ------------------------------------------------------------------

def tex_template_chinese() -> TexTemplate:
    """中文 LaTeX 模板（xelatex + ctex）。

    直接用于 MathTex / Tex 的 ``tex_template`` 参数，
    或在创建前设为全局默认::

        config.tex_template = tex_template_chinese()
        MathTex("中文公式")
    """
    t = TexTemplate()
    t.tex_compiler = "xelatex"
    t.output_format = ".pdf"
    # ctex 自动处理中文字体，无需额外字体配置
    t.add_to_preamble(r"\usepackage{ctex}")
    return t


def tex_template_full() -> TexTemplate:
    """完整数学包模板（xelatex + ctex + 常用数学宏包）。

    包含：amsmath, amssymb, mathtools, bm, physics（常用子集）
    """
    t = tex_template_chinese()
    t.add_to_preamble(r"\usepackage{amsmath}")
    t.add_to_preamble(r"\usepackage{amssymb}")
    t.add_to_preamble(r"\usepackage{mathtools}")
    t.add_to_preamble(r"\usepackage{bm}")
    # physics 包提供 \bra, \braket, \nabla 等简写
    t.add_to_preamble(r"\usepackage{physics}")
    return t


# ------------------------------------------------------------------
# 2. 开箱即用的中文子类
# ------------------------------------------------------------------

class ChineseMathTex(MathTex):
    """支持中文的 MathTex。

    继承 MathTex，内部自动使用 xelatex+ctex 模板。
    用法与普通 MathTex 完全一致::

        ChineseMathTex("\\text{面积} = \\pi r^2")
    """

    def __init__(self, *tex_strings, **kwargs):
        kwargs.setdefault("tex_template", tex_template_chinese())
        super().__init__(*tex_strings, **kwargs)


class ChineseTex(Tex):
    """支持中文的 Tex（文本模式）。

    适合渲染纯文本段落或混合文本与简单公式::

        ChineseTex("勾股定理指出：$a^2 + b^2 = c^2$")
    """

    def __init__(self, *tex_strings, **kwargs):
        kwargs.setdefault("tex_template", tex_template_chinese())
        super().__init__(*tex_strings, **kwargs)


# ------------------------------------------------------------------
# 3. 公式构建器（链式 API）
# ------------------------------------------------------------------

def math(expr, color=None, scale=1.0, tex_template=None, **kwargs):
    """创建带样式的 MathTex（工厂函数）。

    比直接构造 MathTex 更简洁，自动使用中文模板，
    支持一次性设置颜色和缩放::

        eq = math("E = mc^2", color=RED, scale=1.5)
        self.play(Write(eq))

    Args:
        expr: LaTeX 表达式字符串
        color: 颜色（Manim 颜色常量或 HEX 字符串）
        scale: 缩放倍率
        tex_template: 可选自定义模板
        **kwargs: 传递给 MathTex 的其他参数

    Returns:
        MathTex: 可直接用于 ``self.play`` 的公式对象
    """
    t = tex_template or tex_template_chinese()
    m = MathTex(expr, tex_template=t, **kwargs)
    if color is not None:
        m.set_color(color)
    if scale != 1.0:
        m.scale(scale)
    return m


# ------------------------------------------------------------------
# 4. 常见数学结构工厂函数
# ------------------------------------------------------------------

def cases(*branches, tex_template=None):
    """分段函数 / cases 环境。

    Args:
        branches: 每个元素为 (expr, condition) 元组

    Returns:
        MathTex

    示例::

        cases(
            ("x^2", "x > 0"),
            ("0",   "x \\leq 0"),
        )
    """
    t = tex_template or tex_template_chinese()
    body = r"\begin{cases} "
    parts = [f"{expr} & {cond} \\\\ " for expr, cond in branches]
    body += r" ".join(parts)
    body += r"\end{cases}"
    return SingleStringMathTex(body, tex_template=t)


def matrix(entries, tex_template=None, bracket="parens"):
    """矩阵构建器。

    Args:
        entries: 二维列表，如 ``[[1, 2], [3, 4]]``
        bracket: ``"parens"`` (默认), ``"brackets"``, ``"braces"``

    Returns:
        MathTex
    """
    t = tex_template or tex_template_chinese()
    env_map = {"parens": "pmatrix", "brackets": "bmatrix", "braces": "Bmatrix"}
    env = env_map.get(bracket, "pmatrix")

    rows = [" & ".join(str(e) for e in row) for row in entries]
    body = r"\begin{" + env + r"} " + r" \\ ".join(rows) + r" \end{" + env + r"}"
    return SingleStringMathTex(body, tex_template=t)


def align_eqns(*lines, tex_template=None):
    r"""``align*`` 环境多行公式。

    Args:
        lines: 每行一个字符串，``&`` 前对齐

    Returns:
        MathTex

    示例::

        align_eqns(
            "E &= mc^2",
            "F &= ma",
        )
    """
    t = tex_template or tex_template_chinese()
    # MathTex 默认使用 align* 环境，无需显式包裹
    body = r" \\ ".join(lines)
    return MathTex(body, tex_template=t)


def integral(expr, var="x", lower=None, upper=None, tex_template=None):
    """定积分 / 不定积分。

    示例::

        integral("e^{-x^2}", var="x", lower="-\\infty", upper="\\infty")
    """
    t = tex_template or tex_template_chinese()
    if lower is not None and upper is not None:
        body = rf"\int_{{{lower}}}^{{{upper}}} {expr} \, d{var}"
    else:
        body = rf"\int {expr} \, d{var}"
    return MathTex(body, tex_template=t)


def derivative(expr, var="x", order=1, tex_template=None):
    """导数 / 偏导数。

    示例::

        derivative("f(x)", var="x", order=2)   # d^2 f(x) / dx^2
    """
    t = tex_template or tex_template_chinese()
    if order == 1:
        body = rf"\frac{{d}}{{d{var}}} {expr}"
    else:
        body = rf"\frac{{d^{order}}}{{d{var}^{order}}} {expr}"
    return MathTex(body, tex_template=t)


# ------------------------------------------------------------------
# 5. 批量预编译（性能优化）
# ------------------------------------------------------------------

def precompile_formulas(expressions, tex_template=None, quiet=True):
    """批量预编译公式，利用 Manim 的 Tex 文件缓存加速后续场景渲染。

    ManimCE 会在 ``media/Tex/`` 下缓存编译结果（按内容哈希命名）。
    在 ``construct()`` 开头调用此函数，可将大量公式的首次编译
    集中在一次循环中完成，避免动画过程中卡顿。

    Args:
        expressions: 公式字符串列表
        tex_template: 可选，自定义模板
        quiet: 是否抑制日志输出

    Returns:
        list[MathTex]: 预编译好的公式对象列表

    示例::

        formulas = [
            "E = mc^2",
            "\\int_{-\\infty}^{\\infty} e^{-x^2} dx = \\sqrt{\\pi}",
            "\\sum_{n=1}^{\\infty} \\frac{1}{n^2} = \\frac{\\pi^2}{6}",
        ]
        tex_objects = precompile_formulas(formulas)
        # 之后直接使用 tex_objects[i]，无需重新编译
    """
    t = tex_template or tex_template_chinese()
    results = []
    for expr in expressions:
        try:
            with warnings.catch_warnings():
                if quiet:
                    warnings.simplefilter("ignore")
                m = MathTex(expr, tex_template=t)
            results.append(m)
        except Exception as e:
            if not quiet:
                print(f"[latex_helper] Precompile failed for: {expr}")
                print(f"  Error: {e}")
            # 返回占位文本，避免整个场景崩溃
            results.append(MathTex(r"\text{[LaTeX error]}", tex_template=t))
    return results


# ------------------------------------------------------------------
# 6. 错误诊断
# ------------------------------------------------------------------

def diagnose_tex_error(tex_string, tex_template=None):
    r"""诊断单个 LaTeX 公式的编译错误并给出修复建议。

    在场景开发中遇到 LaTeX 编译失败时调用::

        try:
            m = MathTex("错误公式")
        except Exception:
            diagnose_tex_error("错误公式")

    Returns:
        str: 人类可读的错误分析和建议
    """
    common_fixes = [
        (r"Unicode", "包含中文字符但未使用 ChineseMathTex 或 tex_template_chinese()"),
        (r"Undefined control sequence", "使用了未定义的 LaTeX 命令；检查拼写或添加对应宏包"),
        (r"Missing \$ inserted", "文本模式中出现数学符号，需用 $...$ 包裹或用 MathTex 替代 Tex"),
        (r"Double subscript|Double superscript", "同一位置有多个下标/上标；用花括号分组：a_{i_j}"),
        (r"Missing right|Missing left", "括号不匹配；检查 \\left( ... \\right) 是否成对"),
        (r"Environment .* undefined", "环境未定义；确认已加载对应宏包（如 amsmath, mathtools）"),
    ]

    t = tex_template or tex_template_chinese()
    try:
        MathTex(tex_string, tex_template=t)
        return f"[latex_helper] '{tex_string[:40]}...' compiled OK."
    except Exception as e:
        msg = str(e)
        suggestions = []
        for pattern, fix in common_fixes:
            import re
            if re.search(pattern, msg, re.I):
                suggestions.append(f"  • {fix}")

        report = [
            f"[latex_helper] LaTeX compilation failed for:",
            f"  Formula: {tex_string[:80]}{'...' if len(tex_string) > 80 else ''}",
            f"  Error:   {msg[:200]}",
        ]
        if suggestions:
            report.append("  Suggested fixes:")
            report.extend(suggestions)
        else:
            report.append("  Tip: Try simplifying the formula or check for unsupported Unicode characters.")
        return "\n".join(report)
