#version 330

uniform float time;
in vec2 uv;

out vec4 frag_color;

void main(){

    // Noise node: noise (backend=CPU, impl=hash)
    float noise_value = 0.0;
    {
        float freq = 3.000;
        int octaves = 4;
        vec2 p = uv * freq;
        float amp = 1.0;
        for(int i = 0; i < octaves; i++){
            noise_value += amp * (sin(p.x * 12.9898 + p.y * 78.233) * 43758.5453 - floor(sin(p.x * 12.9898 + p.y * 78.233) * 43758.5453));
            p *= 2.0;
            amp *= 0.5;
        }
    }


    // Colorize node: node_1 (palette=heatmap)
    
    vec3 node_1_rgb = vec3(
        smoothstep(0.0, 0.33, noise_value) * (1.0 - smoothstep(0.33, 0.66, noise_value)) + smoothstep(0.66, 1.0, noise_value),
        smoothstep(0.0, 0.5, noise_value),
        1.0 - smoothstep(0.33, 0.66, noise_value)
    );
    vec4 node_1_color = vec4(node_1_rgb, 1.0);

    frag_color = node_1_color;
}
