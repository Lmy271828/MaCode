#version 330
uniform float time;
uniform vec2 resolution;
out vec4 fragColor;
/*
contributors: Patricio Gonzalez Vivo
description: Returns a rectangular SDF
use:
    - rectSDF(<vec2> st [, <vec2|float> size])
    - rectSDF(<vec2> st [, <vec2|float> size, float radius])
options:
    - CENTER_2D: vec2, defaults to vec2(.5)
examples:
    - https://raw.githubusercontent.com/patriciogonzalezvivo/lygia_examples/main/draw_shapes.frag
license:
    - Copyright (c) 2021 Patricio Gonzalez Vivo under Prosperity License - https://prosperitylicense.com/versions/3.0.0
    - Copyright (c) 2021 Patricio Gonzalez Vivo under Patron License - https://lygia.xyz/license
*/

#ifndef FNC_RECTSDF
#define FNC_RECTSDF

float rectSDF(vec2 p, vec2 b, float r) {
    vec2 d = abs(p - 0.5) * 4.2 - b + vec2(r);
    return min(max(d.x, d.y), 0.0) + length(max(d, 0.0)) - r;   
}

float rectSDF(vec2 p, float b, float r) {
    return rectSDF(p, vec2(b), r);
}

float rectSDF(in vec2 st, in vec2 s) {
    #ifdef CENTER_2D
        st -= CENTER_2D;
        st *= 2.0;
    #else
        st = st * 2.0 - 1.0;
    #endif
    return max( abs(st.x / s.x),
                abs(st.y / s.y) );
}

float rectSDF(in vec2 st, in float s) {
    return rectSDF(st, vec2(s) );
}

float rectSDF(in vec2 st) {
    return rectSDF(st, vec2(1.0));
}

#endif
/*
contributors: Matt DesLauriers
description: Performs a smoothstep using standard derivatives for anti-aliased edges at any level of magnification. From https://github.com/glslify/glsl-aastep
use: aastep(<float> threshold, <float> value)
option:
    AA_EDGE: in the absence of derivatives you can specify the antialiasing factor
examples:
    - https://raw.githubusercontent.com/eduardfossas/lygia-study-examples/main/draw/aastep.frag
*/

#ifndef FNC_AASTEP
#define FNC_AASTEP

#if defined(GL_OES_standard_derivatives)
#extension GL_OES_standard_derivatives : enable
#endif

float aastep(float threshold, float value) {
#if !defined(GL_ES) || __VERSION__ >= 300 || defined(GL_OES_standard_derivatives)
    float afwidth = 0.7 * length(vec2(dFdx(value), dFdy(value)));
    return smoothstep(threshold-afwidth, threshold+afwidth, value);
#elif defined(AA_EDGE)
    float afwidth = AA_EDGE;
    return smoothstep(threshold-afwidth, threshold+afwidth, value);
#else 
    return step(threshold, value);
#endif
}
#endif
/*
contributors: Patricio Gonzalez Vivo
description: Fill a SDF. From PixelSpiritDeck https://github.com/patriciogonzalezvivo/PixelSpiritDeck
use: fill(<float> sdf, <float> size [, <float> edge])
examples:
    - https://raw.githubusercontent.com/patriciogonzalezvivo/lygia_examples/main/draw_shapes.frag
license:
    - Copyright (c) 2021 Patricio Gonzalez Vivo under Prosperity License - https://prosperitylicense.com/versions/3.0.0
    - Copyright (c) 2021 Patricio Gonzalez Vivo under Patron License - https://lygia.xyz/license
*/

#ifndef FNC_FILL
#define FNC_FILL
float fill(float x, float size, float edge) {
    return 1.0 - smoothstep(size - edge, size + edge, x);
}

float fill(float x, float size) {
    return 1.0 - aastep(size, x);
}
#endif

/*
contributors: Patricio Gonzalez Vivo
description: Fill a stroke in a SDF. From PixelSpiritDeck https://github.com/patriciogonzalezvivo/PixelSpiritDeck
use: stroke(<float> sdf, <float> size, <float> width [, <float> edge])
license:
    - Copyright (c) 2021 Patricio Gonzalez Vivo under Prosperity License - https://prosperitylicense.com/versions/3.0.0
    - Copyright (c) 2021 Patricio Gonzalez Vivo under Patron License - https://lygia.xyz/license
*/

#ifndef FNC_STROKE
#define FNC_STROKE
// ALREADY INCLUDED: ../math/aastep.glsl

/*
contributors: Patricio Gonzalez Vivo
description: clamp a value between 0 and 1
use: <float|vec2|vec3|vec4> saturation(<float|vec2|vec3|vec4> value)
examples:
    - https://raw.githubusercontent.com/patriciogonzalezvivo/lygia_examples/main/math_functions.frag
license:
    - Copyright (c) 2021 Patricio Gonzalez Vivo under Prosperity License - https://prosperitylicense.com/versions/3.0.0
    - Copyright (c) 2021 Patricio Gonzalez Vivo under Patron License - https://lygia.xyz/license
*/

#if !defined(FNC_SATURATE) && !defined(saturate)
#define FNC_SATURATE
#define saturate(V) clamp(V, 0.0, 1.0)
#endif
float stroke(float x, float size, float w) {
    float d = aastep(size, x + w * 0.5) - aastep(size, x - w * 0.5);
    return saturate(d);
}

float stroke(float x, float size, float w, float edge) {
    float d = smoothstep(size - edge, size + edge, x + w * 0.5) - smoothstep(size - edge, size + edge, x - w * 0.5);
    return saturate(d);
}

#endif

/*
contributors: Patricio Gonzalez Vivo
description: Draw a rectangel filled or not.
use: rect(<vec2> st, <vec2> size [, <float> width])
license:
    - Copyright (c) 2021 Patricio Gonzalez Vivo under Prosperity License - https://prosperitylicense.com/versions/3.0.0
    - Copyright (c) 2021 Patricio Gonzalez Vivo under Patron License - https://lygia.xyz/license
*/

#ifndef FNC_RECT
#define FNC_RECT

float rect(vec2 st, vec2 size, float strokeWidth) {
    return stroke(rectSDF(st, size), 1.0, strokeWidth);
}

float rect(vec2 st, float size, float strokeWidth) {
    return stroke(rectSDF(st, vec2(size)), 1.0, strokeWidth);
}

float rect(vec2 st, vec2 size) {
    return fill(rectSDF(st, size), 1.0);
}

float rect(vec2 st, float size) {
    return fill(rectSDF(st, vec2(size)), 1.0);
}

#endif
// ALREADY INCLUDED: lygia/draw/stroke.glsl

void main() {
    vec2 uv = gl_FragCoord.xy / resolution.xy;
    float r = rect(uv, 0.5);
    float s = stroke(r, 0.5, 0.02);
    fragColor = vec4(vec3(s), 1.0);
}
