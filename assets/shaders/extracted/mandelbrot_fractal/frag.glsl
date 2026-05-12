#version 330

uniform vec2 parameter;
uniform float opacity;
uniform float n_steps;
uniform float mandelbrot;

uniform vec3 color0;
uniform vec3 color1;
uniform vec3 color2;
uniform vec3 color3;
uniform vec3 color4;
uniform vec3 color5;
uniform vec3 color6;
uniform vec3 color7;
uniform vec3 color8;

in vec3 xyz_coords;

out vec4 frag_color;

uniform vec3 light_position;
uniform vec3 camera_position;
uniform vec3 shading;

vec3 float_to_color(float value, float min_val, float max_val, vec3[9] colormap_data){
    float alpha = clamp((value - min_val) / (max_val - min_val), 0.0, 1.0);
    int disc_alpha = min(int(alpha * 8), 7);
    return mix(
        colormap_data[disc_alpha],
        colormap_data[disc_alpha + 1],
        8.0 * alpha - disc_alpha
    );
}


vec4 add_light(vec4 color, vec3 point, vec3 unit_normal){
    if(shading == vec3(0.0)) return color;

    float reflectiveness = shading.x;
    float gloss = shading.y;
    float shadow = shading.z;

    vec4 result = color;
    vec3 to_camera = normalize(camera_position - point);
    vec3 to_light = normalize(light_position - point);

    float light_to_normal = dot(to_light, unit_normal);
    // When unit normal points towards light, brighten
    float bright_factor = max(light_to_normal, 0) * reflectiveness;
    // For glossy surface, add extra shine if light beam go towards camera
    vec3 light_reflection = reflect(-to_light, unit_normal);
    float light_to_cam = dot(light_reflection, to_camera);
    float shine = gloss * exp(-3 * pow(1 - light_to_cam, 2));
    bright_factor += shine;

    result.rgb = mix(result.rgb, vec3(1.0), bright_factor);
    if (light_to_normal < 0){
        // Darken
        result.rgb = mix(
            result.rgb,
            vec3(0.0),
            max(-light_to_normal, 0) * shadow
        );
    }
    return result;
}

vec4 finalize_color(vec4 color, vec3 point, vec3 unit_normal){
    ///// INSERT COLOR FUNCTION HERE /////
    // The line above may be replaced by arbitrary code snippets, as per
    // the method Mobject.set_color_by_code
    return add_light(color, point, unit_normal);
}
vec2 complex_mult(vec2 z, vec2 w){
    return vec2(z.x * w.x - z.y * w.y, z.x * w.y + z.y * w.x);
}

vec2 complex_div(vec2 z, vec2 w){
    return complex_mult(z, vec2(w.x, -w.y)) / (w.x * w.x + w.y * w.y);
}

vec2 complex_pow(vec2 z, int n){
    vec2 result = vec2(1.0, 0.0);
    for(int i = 0; i < n; i++){
        result = complex_mult(result, z);
    }
    return result;
}

const int MAX_DEGREE = 5;

void main() {
    vec3 color_map[9] = vec3[9](
        color0, color1, color2, color3,
        color4, color5, color6, color7, color8
    );
    vec3 color;

    vec2 z;
    vec2 c;

    if(bool(mandelbrot)){
        c = xyz_coords.xy;
        z = vec2(0.0, 0.0);
    }else{
        c = parameter;
        z = xyz_coords.xy;
    }

    float outer_bound = 2.0;
    bool stable = true;
    for(int n = 0; n < int(n_steps); n++){
        z = complex_mult(z, z) + c;
        if(length(z) > outer_bound){
            float float_n = float(n);
            float_n += log(outer_bound) / log(length(z));
            float_n += 0.5 * length(c);
            color = float_to_color(sqrt(float_n), 1.5, 8.0, color_map);
            stable = false;
            break;
        }
    }
    if(stable){
        color = vec3(0.0, 0.0, 0.0);
    }

    frag_color = finalize_color(
        vec4(color, opacity),
        xyz_coords,
        vec3(0.0, 0.0, 1.0)
    );
 }