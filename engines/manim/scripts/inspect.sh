#!/usr/bin/env bash
set -euo pipefail

# engines/manim/scripts/inspect.sh
# 打印该引擎可用的模板与工具函数。

CONDA_PYTHON="$HOME/miniconda3/envs/math/bin/python"
if [[ -x "$CONDA_PYTHON" ]]; then
    PYTHON="$CONDA_PYTHON"
else
    PYTHON="python3"
fi

echo "=== ManimCE Engine Inspection ==="
echo ""
echo "--- Version ---"
"$PYTHON" -m manim --version 2>&1 || true
echo ""

echo "--- Built-in Mobjects ---"
"$PYTHON" -c "
import manim
import inspect
print('Scene classes:')
for name in sorted(dir(manim)):
    obj = getattr(manim, name)
    if inspect.isclass(obj) and issubclass(obj, manim.Scene):
        print(f'  {name}')
" 2>&1
echo ""

echo "--- Common Mobjects ---"
"$PYTHON" -c "
import manim
mobjects = [
    'Circle', 'Square', 'Rectangle', 'Triangle', 'Line', 'Arrow', 'Text',
    'MathTex', 'VGroup', 'Axes', 'NumberPlane', 'Graph',
]
for name in mobjects:
    if hasattr(manim, name):
        print(f'  {name}')
" 2>&1
echo ""

echo "--- Common Animations ---"
"$PYTHON" -c "
import manim
anims = [
    'Create', 'FadeIn', 'FadeOut', 'Write', 'Transform',
    'Rotate', 'Scale', 'MoveTo', 'ReplacementTransform',
]
for name in anims:
    if hasattr(manim, name):
        print(f'  {name}')
" 2>&1
echo ""

echo "--- Package Path ---"
"$PYTHON" -c "import manim; print(manim.__path__[0])" 2>&1
