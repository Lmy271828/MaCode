#version 330
uniform float time;
uniform vec2 resolution;
out vec4 fragColor;
/*
contributors: Patricio Gonzalez Vivo
description: make some square tiles. XY provide coords inside of the tile. ZW provides tile coords
use: <vec4> hexTile(<vec2> st [, <float> scale])
license:
    - Copyright (c) 2021 Patricio Gonzalez Vivo under Prosperity License - https://prosperitylicense.com/versions/3.0.0
    - Copyright (c) 2021 Patricio Gonzalez Vivo under Patron License - https://lygia.xyz/license
*/

#ifndef FNC_SQTILE
#define FNC_SQTILE
vec4 sqTile(vec2 st) { return vec4(fract(st), floor(st)); }
vec4 sqTile(vec2 st, float scale) { return sqTile(st * scale); }
#endif
/*
contributors: Patricio Gonzalez Vivo
description: 'Return a black or white in a square checker patter'
use:
    - <vec4> checkerTile(<vec4> tile)
    - <vec4> checkerTile(<vec2> st [, <vec2> scale])
examples:
    - https://raw.githubusercontent.com/patriciogonzalezvivo/lygia_examples/main/draw_tiles.frag
license:
    - Copyright (c) 2021 Patricio Gonzalez Vivo under Prosperity License - https://prosperitylicense.com/versions/3.0.0
    - Copyright (c) 2021 Patricio Gonzalez Vivo under Patron License - https://lygia.xyz/license
*/

#ifndef FNC_CHECKERTILE
#define FNC_CHECKERTILE
float checkerTile(vec4 t) {
    vec2 c = mod(t.zw,2.);
    return abs(c.x-c.y);
}

float checkerTile(vec2 v) {
    return checkerTile(sqTile(v));
}

float checkerTile(vec2 v, float s) {
    return checkerTile(v * s);
}

float checkerTile(vec2 v, vec2 s) {
    return checkerTile(v * s);
}
#endif
void main() {
    vec2 uv = gl_FragCoord.xy / resolution.xy;
    float c = checkerTile(uv * 4.0 + time * 0.2);
    fragColor = vec4(vec3(c), 1.0);
}
