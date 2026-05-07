r"""engines/manimgl/src/utils/latex_helper.py
MaCode LaTeX helper — ManimGL version.

Solves three pain points when Agents use LaTeX:
1. Chinese rendering: default latex does not support Unicode, needs xelatex+ctex
2. Formula building: common math structures (matrices, piecewise functions, aligned equations) have high memory cost
3. Compile performance: batch pre-compilation can significantly speed up scenes with many formulas

Usage::

    from utils.latex_helper import ChineseTex, math, tex_template_full

    # Chinese formula (works out of the box)
    ChineseTex(r"\text{Euler's formula: } e^{i\pi} + 1 = 0")

    # Chain builder
    math("E = mc^2").set_color(RED).scale(1.5)

    # Pre-configured template (with full math packages)
    t = tex_template_full()
    Tex(r"\bm{A}x = \bm{b}", template=t)
"""

from manimlib.imports import *
import os
import tempfile
import warnings


# ------------------------------------------------------------------
# 1. Pre-configured templates
# ------------------------------------------------------------------

_TEX_TEMPLATE_DIR = os.path.join(tempfile.gettempdir(), "mancode_manimgl_tex")


def _ensure_template_dir():
    os.makedirs(_TEX_TEMPLATE_DIR, exist_ok=True)


def _write_template(name: str, content: str) -> str:
    _ensure_template_dir()
    path = os.path.join(_TEX_TEMPLATE_DIR, name)
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)
    return path


def tex_template_chinese() -> str:
    """Chinese LaTeX template path (xelatex + ctex).

    Returns a file path that can be passed to ``Tex(..., template=...)``.
    """
    template = r"""\documentclass[preview]{standalone}
\usepackage[UTF8]{ctex}
\usepackage{amsmath}
\usepackage{amssymb}
\begin{document}
$\displaystyle BODY$
\end{document}
"""
    return _write_template("chinese_template.tex", template)


def tex_template_full() -> str:
    """Full math package template path (xelatex + ctex + common math packages).

    Includes: amsmath, amssymb, mathtools, bm, physics (common subset)
    """
    template = r"""\documentclass[preview]{standalone}
\usepackage[UTF8]{ctex}
\usepackage{amsmath}
\usepackage{amssymb}
\usepackage{mathtools}
\usepackage{bm}
\usepackage{physics}
\begin{document}
$\displaystyle BODY$
\end{document}
"""
    return _write_template("full_template.tex", template)


# ------------------------------------------------------------------
# 2. Out-of-the-box Chinese subclasses
# ------------------------------------------------------------------

class ChineseTex(Tex):
    r"""Chinese-supporting Tex.

    Inherits Tex, internally uses xelatex+ctex template.
    Usage is identical to normal Tex::

        ChineseTex(r"\text{Area} = \pi r^2")
    """

    def __init__(self, tex_string, **kwargs):
        kwargs.setdefault("template", tex_template_chinese())
        super().__init__(tex_string, **kwargs)


# ------------------------------------------------------------------
# 3. Formula builder (chainable API)
# ------------------------------------------------------------------

def math(expr, color=None, scale=1.0, template=None, **kwargs):
    """Create styled Tex (factory function).

    More concise than direct Tex construction, auto-uses Chinese template,
    supports one-shot color and scale setting::

        eq = math("E = mc^2", color=RED, scale=1.5)
        self.play(Write(eq))

    Args:
        expr: LaTeX expression string
        color: Manim color constant or HEX string
        scale: scale factor
        template: optional custom template file path
        **kwargs: other arguments passed to Tex

    Returns:
        Tex: formula object ready for ``self.play``
    """
    t = template or tex_template_chinese()
    m = Tex(expr, template=t, **kwargs)
    if color is not None:
        m.set_color(color)
    if scale != 1.0:
        m.scale(scale)
    return m


# ------------------------------------------------------------------
# 4. Common math structure factory functions
# ------------------------------------------------------------------

def cases(*branches, template=None):
    """Piecewise function / cases environment.

    Args:
        branches: each element is an (expr, condition) tuple

    Returns:
        Tex

    Example::

        cases(
            ("x^2", "x > 0"),
            ("0",   "x \\leq 0"),
        )
    """
    t = template or tex_template_chinese()
    body = r"\begin{cases} "
    parts = [f"{expr} & {cond} \\ " for expr, cond in branches]
    body += r" ".join(parts)
    body += r"\end{cases}"
    return Tex(body, template=t)


def matrix(entries, template=None, bracket="parens"):
    """Matrix builder.

    Args:
        entries: 2D list, e.g. ``[[1, 2], [3, 4]]``
        bracket: ``"parens"`` (default), ``"brackets"``, ``"braces"``

    Returns:
        Tex
    """
    t = template or tex_template_chinese()
    env_map = {"parens": "pmatrix", "brackets": "bmatrix", "braces": "Bmatrix"}
    env = env_map.get(bracket, "pmatrix")

    rows = [" & ".join(str(e) for e in row) for row in entries]
    body = r"\begin{" + env + r"} " + r" \\ ".join(rows) + r" \end{" + env + r"}"
    return Tex(body, template=t)


def align_eqns(*lines, template=None):
    r"""``align*`` environment multi-line formulas.

    Args:
        lines: one string per line, ``&`` for alignment

    Returns:
        Tex

    Example::

        align_eqns(
            "E &= mc^2",
            "F &= ma",
        )
    """
    t = template or tex_template_chinese()
    body = r"\begin{align*} " + r" \\ ".join(lines) + r" \end{align*}"
    return Tex(body, template=t)


def integral(expr, var="x", lower=None, upper=None, template=None):
    """Definite / indefinite integral.

    Example::

        integral("e^{-x^2}", var="x", lower="-\\infty", upper="\\infty")
    """
    t = template or tex_template_chinese()
    if lower is not None and upper is not None:
        body = rf"\int_{{{lower}}}^{{{upper}}} {expr} \, d{var}"
    else:
        body = rf"\int {expr} \, d{var}"
    return Tex(body, template=t)


def derivative(expr, var="x", order=1, template=None):
    """Derivative / partial derivative.

    Example::

        derivative("f(x)", var="x", order=2)   # d^2 f(x) / dx^2
    """
    t = template or tex_template_chinese()
    if order == 1:
        body = rf"\frac{{d}}{{d{var}}} {expr}"
    else:
        body = rf"\frac{{d^{order}}}{{d{var}^{order}}} {expr}"
    return Tex(body, template=t)


# ------------------------------------------------------------------
# 5. Batch pre-compilation (performance optimization)
# ------------------------------------------------------------------

def precompile_formulas(expressions, template=None, quiet=True):
    r"""Batch pre-compile formulas to warm up ManimGL's Tex file cache.

    ManimGL caches compiled results under ``media/Tex/`` (named by content hash).
    Calling this at the top of ``construct()`` batches first-time compilation
    into one loop, avoiding stutter during animation.

    Args:
        expressions: list of formula strings
        template: optional custom template file path
        quiet: whether to suppress log output

    Returns:
        list[Tex]: pre-compiled formula objects

    Example::

        formulas = [
            "E = mc^2",
            r"\int_{-\infty}^{\infty} e^{-x^2} dx = \sqrt{\pi}",
            r"\sum_{n=1}^{\infty} \frac{1}{n^2} = \frac{\pi^2}{6}",
        ]
        tex_objects = precompile_formulas(formulas)
        # use tex_objects[i] directly later, no re-compilation
    """
    t = template or tex_template_chinese()
    results = []
    for expr in expressions:
        try:
            with warnings.catch_warnings():
                if quiet:
                    warnings.simplefilter("ignore")
                m = Tex(expr, template=t)
            results.append(m)
        except Exception as e:
            if not quiet:
                print(f"[latex_helper] Precompile failed for: {expr}")
                print(f"  Error: {e}")
            # Return placeholder text to avoid crashing the whole scene
            results.append(Tex(r"\text{[LaTeX error]}", template=t))
    return results


# ------------------------------------------------------------------
# 6. Error diagnosis
# ------------------------------------------------------------------

def diagnose_tex_error(tex_string, template=None):
    r"""Diagnose LaTeX compilation error for a single formula and suggest fixes.

    Call this when you encounter LaTeX compile failure in scene development::

        try:
            m = Tex("bad formula")
        except Exception:
            diagnose_tex_error("bad formula")

    Returns:
        str: human-readable error analysis and suggestions
    """
    common_fixes = [
        (r"Unicode", "Contains Chinese characters but ChineseTex or tex_template_chinese() not used"),
        (r"Undefined control sequence", "Undefined LaTeX command; check spelling or add corresponding package"),
        (r"Missing \$ inserted", "Math symbol in text mode; wrap with $...$ or use Tex directly"),
        (r"Double subscript|Double superscript", "Multiple subscripts/superscripts at same position; group with braces: a_{i_j}"),
        (r"Missing right|Missing left", "Unmatched delimiters; check \\left( ... \\right) pairing"),
        (r"Environment .* undefined", "Undefined environment; confirm required package loaded (e.g. amsmath, mathtools)"),
    ]

    t = template or tex_template_chinese()
    try:
        Tex(tex_string, template=t)
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
