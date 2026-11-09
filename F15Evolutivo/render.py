import math

import moderngl
import numpy as np

import modelos as MD
import terreno as T
import texturas as TX

COMUN = """
uniform vec3 u_cam;
uniform vec3 u_sol;
uniform vec3 u_cenit;
uniform vec3 u_horiz;
uniform vec3 u_colsol;
uniform vec3 u_amb;
uniform float u_niebla;
uniform float u_noche;
vec3 cielo(vec3 d) {
    float y = d.y;
    vec3 c = mix(u_horiz, u_cenit, pow(clamp(y, 0.0, 1.0), 0.45));
    if (y < 0.0) c = mix(u_horiz, u_horiz * 0.72 + vec3(0.015), clamp(-y * 4.0, 0.0, 1.0));
    float s = max(dot(d, u_sol), 0.0);
    c += u_colsol * (pow(s, 5.0) * 0.16 + pow(s, 48.0) * 0.32) * (1.0 - u_noche * 0.8);
    return c;
}
vec3 aire(vec3 col, vec3 pos) {
    vec3 v = pos - u_cam;
    float d = length(v);
    vec3 dir = v / max(d, 1e-3);
    float hc = u_cam.y, hf = pos.y, H = 1700.0;
    float dh = hf - hc;
    float f = abs(dh) < 2.0 ? exp(-hc / H) : H * (exp(-hc / H) - exp(-hf / H)) / dh;
    float o = 1.0 - exp(-d * u_niebla * max(f, 0.02));
    vec3 fc = cielo(normalize(vec3(dir.x, clamp(dir.y, -0.05, 0.25) * 0.5, dir.z)));
    return mix(col, fc, clamp(o, 0.0, 1.0));
}
"""

VS_CIELO = """
#version 330
in vec2 in_pos;
out vec2 v_p;
void main() { v_p = in_pos; gl_Position = vec4(in_pos, 0.9999, 1.0); }
"""
FS_CIELO = """
#version 330
""" + COMUN + """
uniform mat4 u_inv;
uniform sampler2D u_ruido;
uniform float u_t;
in vec2 v_p;
out vec4 f;
void main() {
    vec4 q = u_inv * vec4(v_p, 1.0, 1.0);
    vec3 d = normalize(q.xyz / q.w);
    vec3 c = cielo(d);
    float s = max(dot(d, u_sol), 0.0);
    c += u_colsol * smoothstep(0.99955, 0.99975, s) * 6.0 * (1.0 - u_noche);
    if (u_noche > 0.5) {
        vec2 uv = d.xz / max(d.y, 0.05) * 3.0;
        float st = texture(u_ruido, uv * 0.37).a * texture(u_ruido, uv * 1.7).r;
        c += vec3(1.0) * smoothstep(0.62, 0.7, st) * clamp(d.y * 4.0, 0.0, 1.0) * (u_noche - 0.5) * 2.0;
        float luna = max(dot(d, normalize(vec3(-0.4, 0.5, 0.6))), 0.0);
        c += vec3(0.8, 0.85, 0.9) * smoothstep(0.9996, 0.9998, luna) * 1.5 + vec3(0.05, 0.06, 0.09) * pow(luna, 30.0);
    }
    if (d.y > 0.0) {
        vec2 uv = d.xz / (d.y + 0.08) * 0.35 + vec2(u_t * 0.0004, 0.0);
        float n = texture(u_ruido, uv).g * 0.6 + texture(u_ruido, uv * 3.1).b * 0.4;
        float cir = smoothstep(0.55, 0.85, n) * smoothstep(0.0, 0.25, d.y) * 0.5;
        vec3 cc = mix(u_horiz * 1.1, vec3(1.0) * (u_colsol * 0.6 + u_amb), 0.6);
        c = mix(c, cc, cir * (1.0 - u_noche * 0.9));
    }
    f = vec4(c, 1.0);
}
"""

VS_TERRENO = """
#version 330
uniform mat4 u_vp;
uniform vec3 u_cam;
in vec3 in_pos;
in vec3 in_nrm;
out vec3 v_pos;
out vec3 v_nrm;
void main() { v_pos = in_pos; v_nrm = in_nrm; gl_Position = u_vp * vec4(in_pos - u_cam, 1.0); }
"""
FS_TERRENO = """
#version 330
""" + COMUN + """
uniform sampler2D u_ruido;
uniform sampler2D u_bosque;
uniform float u_mitad;
in vec3 v_pos;
in vec3 v_nrm;
out vec4 f;
void main() {
    vec2 xz = v_pos.xz;
    float d = length(v_pos - u_cam);
    float n1 = texture(u_ruido, xz / 2300.0).r;
    float n2 = texture(u_ruido, xz / 420.0).g;
    float n3 = texture(u_ruido, xz / 61.0).b;
    float n4 = texture(u_ruido, xz / 9.3).a;
    vec3 N = normalize(v_nrm);
    float det = 1.0 - smoothstep(200.0, 2500.0, d);
    vec2 g = vec2(texture(u_ruido, xz / 37.0).r - texture(u_ruido, xz / 37.0 + vec2(0.01, 0.0)).r,
                  texture(u_ruido, xz / 37.0).r - texture(u_ruido, xz / 37.0 + vec2(0.0, 0.01)).r);
    N = normalize(N + vec3(g.x, 0.0, g.y) * 6.0 * det);
    float h = v_pos.y;
    float pend = 1.0 - N.y;
    vec3 pasto = mix(vec3(0.17, 0.27, 0.09), vec3(0.32, 0.36, 0.15), n1) * (0.82 + 0.36 * n2);
    vec2 r = mat2(0.96, -0.28, 0.28, 0.96) * xz;
    vec2 celda = floor(r / vec2(330.0, 210.0));
    vec2 dentro = fract(r / vec2(330.0, 210.0));
    float tipo = texture(u_ruido, celda / 61.0 + 0.5).r;
    vec3 cultivo = tipo < 0.4 ? vec3(0.30, 0.38, 0.13) : (tipo < 0.55 ? vec3(0.55, 0.48, 0.25) :
                   (tipo < 0.7 ? vec3(0.40, 0.31, 0.20) : vec3(0.24, 0.33, 0.12)));
    cultivo *= 0.85 + 0.2 * n3 + 0.08 * sin(dentro.y * 120.0) * det;
    float lindero = smoothstep(0.0, 0.015, dentro.x) * smoothstep(0.0, 0.02, dentro.y);
    cultivo = mix(vec3(0.16, 0.22, 0.10), cultivo, lindero);
    float campos = smoothstep(0.5, 0.62, texture(u_ruido, xz / 11000.0 + 0.3).g) * (1.0 - smoothstep(140.0, 330.0, h))
                   * (1.0 - smoothstep(0.05, 0.12, pend)) * smoothstep(6.0, 15.0, h);
    float fb = texture(u_bosque, (xz + u_mitad) / (2.0 * u_mitad)).r;
    float bosque = smoothstep(0.49, 0.53, fb + h / 6000.0 + (n2 - 0.5) * 0.05)
                   * smoothstep(8.0, 20.0, h) * (1.0 - smoothstep(1150.0, 1300.0, h));
    vec3 copa = vec3(0.07, 0.14, 0.05) * (0.75 + 0.6 * n3) * (0.9 + 0.2 * n4);
    vec3 roca = mix(vec3(0.36, 0.33, 0.30), vec3(0.52, 0.49, 0.44), n2) * (0.8 + 0.35 * n4);
    vec3 arena = vec3(0.74, 0.68, 0.52) * (0.9 + 0.15 * n3);
    vec3 c = pasto;
    c = mix(c, cultivo, campos);
    c = mix(c, copa, bosque * (1.0 - campos));
    c = mix(c, vec3(0.40, 0.37, 0.24) * (0.85 + 0.3 * n2), smoothstep(650.0, 1150.0, h + n1 * 250.0));
    c = mix(c, roca, clamp(smoothstep(0.22, 0.42, pend + (n2 - 0.5) * 0.15) + smoothstep(1350.0, 1600.0, h + n2 * 200.0), 0.0, 1.0));
    c = mix(c, vec3(0.93, 0.95, 0.98), smoothstep(1650.0, 1800.0, h + n2 * 180.0) * (1.0 - smoothstep(0.38, 0.6, pend)));
    c = mix(c, arena, 1.0 - smoothstep(3.0, 9.0, h + n3 * 4.0));
    c = mix(c, vec3(0.45, 0.42, 0.33), 1.0 - smoothstep(-1.0, 0.5, h));
    float dif = max(dot(N, u_sol), 0.0);
    vec3 luz = u_colsol * dif + u_amb * (0.55 + 0.45 * N.y);
    vec3 col = c * luz * (0.92 + 0.16 * n4 * det);
    f = vec4(aire(col, v_pos), 1.0);
}
"""

VS_AGUA = """
#version 330
uniform mat4 u_vp;
uniform vec3 u_cam;
in vec2 in_pos;
out vec3 v_pos;
void main() {
    vec3 p = vec3(in_pos.x + floor(u_cam.x / 400.0) * 400.0, 0.0, in_pos.y + floor(u_cam.z / 400.0) * 400.0);
    v_pos = p;
    gl_Position = u_vp * vec4(p - u_cam, 1.0);
}
"""
FS_AGUA = """
#version 330
""" + COMUN + """
uniform sampler2D u_ruido;
uniform sampler2D u_alturas;
uniform float u_mitad;
uniform float u_t;
in vec3 v_pos;
out vec4 f;
void main() {
    vec2 xz = v_pos.xz;
    float d = length(v_pos - u_cam);
    vec2 uvh = (xz + u_mitad) / (2.0 * u_mitad);
    float hf = (uvh.x < 0.0 || uvh.y < 0.0 || uvh.x > 1.0 || uvh.y > 1.0) ? -120.0 : texture(u_alturas, uvh).r;
    if (hf > 0.6) discard;
    float prof = -hf;
    float k = 1.0 - smoothstep(300.0, 9000.0, d);
    vec4 a = texture(u_ruido, xz / 160.0 + vec2(u_t * 0.006, u_t * 0.004));
    vec4 b = texture(u_ruido, xz / 47.0 - vec2(u_t * 0.009, -u_t * 0.005));
    vec4 c2 = texture(u_ruido, xz / 13.0 + vec2(u_t * 0.02, u_t * 0.013));
    vec3 N = normalize(vec3((a.r - 0.5) * 0.35 + (b.g - 0.5) * 0.25 + (c2.b - 0.5) * 0.12 * k, 1.0,
                            (a.g - 0.5) * 0.35 + (b.b - 0.5) * 0.25 + (c2.a - 0.5) * 0.12 * k));
    N = normalize(mix(vec3(0.0, 1.0, 0.0), N, 0.35 + 0.65 * k));
    vec3 V = normalize(u_cam - v_pos);
    vec3 R = reflect(-V, N);
    R.y = abs(R.y);
    float fres = 0.02 + 0.98 * pow(1.0 - max(dot(N, V), 0.0), 5.0);
    vec3 hondo = vec3(0.015, 0.06, 0.10);
    vec3 bajo = vec3(0.09, 0.30, 0.32);
    vec3 cuerpo = mix(bajo, hondo, smoothstep(0.0, 30.0, prof)) * (u_colsol * 0.6 + u_amb);
    vec3 col = mix(cuerpo, cielo(R), fres);
    col += u_colsol * pow(max(dot(R, u_sol), 0.0), 350.0) * 4.0 * (1.0 - u_noche);
    float espuma = (1.0 - smoothstep(0.0, 2.5, prof)) * smoothstep(0.45, 0.7, b.r + 0.3 * sin(u_t * 1.3 + prof * 3.0));
    col = mix(col, vec3(0.9) * (u_colsol + u_amb), espuma * 0.6);
    f = vec4(aire(col, v_pos), 1.0);
}
"""

VS_PISTA = """
#version 330
uniform mat4 u_vp;
uniform vec3 u_cam;
in vec3 in_pos;
in vec2 in_uv;
out vec3 v_pos;
out vec2 v_uv;
void main() {
    v_pos = in_pos;
    v_uv = in_uv;
    vec3 r = in_pos - u_cam;
    r.y += length(r) * 0.0007;
    gl_Position = u_vp * vec4(r, 1.0);
}
"""
FS_PISTA = """
#version 330
""" + COMUN + """
uniform sampler2D u_tex;
uniform sampler2D u_ruido;
uniform int u_tipo;
in vec3 v_pos;
in vec2 v_uv;
out vec4 f;
void main() {
    vec3 c;
    if (u_tipo == 0) c = texture(u_tex, v_uv).rgb;
    else {
        c = texture(u_tex, v_uv / 32.0).rgb * (0.9 + 0.2 * texture(u_ruido, v_uv / 300.0).r);
        if (u_tipo == 1 && abs(v_uv.x) < 0.25) c = vec3(0.78, 0.62, 0.12);
        if (u_tipo == 1 && abs(abs(v_uv.x) - 10.5) < 0.2) c = vec3(0.78, 0.62, 0.12);
    }
    vec3 luz = u_colsol * max(u_sol.y, 0.0) + u_amb;
    f = vec4(aire(c * luz, v_pos), 1.0);
}
"""

VS_OBJ = """
#version 330
uniform mat4 u_vp;
uniform mat4 u_m;
uniform vec3 u_cam;
in vec3 in_pos;
in vec3 in_nrm;
in vec3 in_col;
in float in_mat;
out vec3 v_pos;
out vec3 v_nrm;
out vec3 v_col;
out float v_mat;
out vec3 v_loc;
void main() {
    vec4 w = u_m * vec4(in_pos, 1.0);
    v_pos = w.xyz + u_cam;
    v_nrm = mat3(u_m) * in_nrm;
    v_col = in_col;
    v_mat = in_mat;
    v_loc = in_pos;
    gl_Position = u_vp * w;
}
"""
VS_OBJ_INST = """
#version 330
uniform mat4 u_vp;
uniform vec3 u_cam;
in vec3 in_pos;
in vec3 in_nrm;
in vec3 in_col;
in float in_mat;
in vec4 i_a;
in vec4 i_b;
in vec4 i_c;
in vec4 i_d;
out vec3 v_pos;
out vec3 v_nrm;
out vec3 v_col;
out float v_mat;
out vec3 v_loc;
out float v_alfa;
void main() {
    mat4 m = mat4(vec4(i_a.xyz, 0.0), vec4(i_b.xyz, 0.0), vec4(i_c.xyz, 0.0), vec4(i_d.xyz, 1.0));
    vec4 w = m * vec4(in_pos, 1.0);
    v_pos = w.xyz + u_cam;
    v_nrm = mat3(m) * in_nrm;
    v_col = in_col * (1.0 + i_a.w);
    v_mat = in_mat;
    v_loc = in_pos;
    v_alfa = i_d.w;
    gl_Position = u_vp * w;
}
"""
FS_OBJ = """
#version 330
""" + COMUN + """
uniform sampler2D u_ruido;
uniform float u_alfa;
uniform int u_camuflaje;
in vec3 v_pos;
in vec3 v_nrm;
in vec3 v_col;
in float v_mat;
in vec3 v_loc;
#ifdef INST
in float v_alfa;
#endif
out vec4 f;
void main() {
    vec3 N = normalize(v_nrm);
    vec3 V = normalize(u_cam - v_pos);
    if (dot(N, V) < 0.0) N = -N;
    vec3 base = v_col;
    if (u_camuflaje == 1 && v_mat < 0.9) {
        float n = texture(u_ruido, v_loc.xz * 0.045 + v_loc.y * 0.03).g;
        base *= mix(0.86, 1.06, smoothstep(0.42, 0.58, n));
        base *= 0.96 + 0.06 * texture(u_ruido, v_loc.xy * 0.6).a;
    }
    float dif = max(dot(N, u_sol), 0.0);
    vec3 H = normalize(V + u_sol);
    float brillo = mix(24.0, 220.0, v_mat);
    float esp = pow(max(dot(N, H), 0.0), brillo) * mix(0.15, 1.6, v_mat);
    vec3 R = reflect(-V, N);
    float fres = 0.04 + 0.96 * pow(1.0 - max(dot(N, V), 0.0), 5.0);
    vec3 col = base * (u_colsol * dif + u_amb * (0.55 + 0.45 * N.y));
    col += u_colsol * esp * (1.0 - u_noche * 0.7);
    col = mix(col, cielo(R), fres * mix(0.12, 0.85, v_mat));
    float a = u_alfa;
#ifdef INST
    a *= v_alfa;
#endif
    f = vec4(aire(col, v_pos), a);
}
"""

VS_INST_ARBOL = """
#version 330
uniform mat4 u_vp;
uniform vec3 u_cam;
in vec3 in_pos;
in vec3 in_nrm;
in vec3 in_col;
in float in_mat;
in vec3 i_pos;
in float i_esc;
in float i_tono;
out vec3 v_pos;
out vec3 v_nrm;
out vec3 v_col;
void main() {
    vec3 p = i_pos + in_pos * vec3(i_esc, i_esc * (0.85 + 0.4 * i_tono), i_esc);
    v_pos = p;
    v_nrm = in_nrm;
    v_col = in_col * (0.75 + 0.5 * i_tono) * vec3(1.0, 1.0 + 0.15 * (i_tono - 0.5), 1.0);
    gl_Position = u_vp * vec4(p - u_cam, 1.0);
}
"""
VS_INST_EDIF = """
#version 330
uniform mat4 u_vp;
uniform vec3 u_cam;
in vec3 in_pos;
in vec3 in_nrm;
in vec3 in_col;
in float in_mat;
in vec3 i_pos;
in vec3 i_tam;
in float i_rot;
out vec3 v_pos;
out vec3 v_nrm;
out vec3 v_col;
void main() {
    float c = cos(i_rot), s = sin(i_rot);
    vec3 l = in_pos * i_tam;
    vec3 p = i_pos + vec3(c * l.x - s * l.z, l.y, s * l.x + c * l.z);
    v_pos = p;
    v_nrm = vec3(c * in_nrm.x - s * in_nrm.z, in_nrm.y, s * in_nrm.x + c * in_nrm.z);
    float h = fract(sin(dot(i_pos.xz, vec2(12.9898, 78.233))) * 43758.5453);
    v_col = in_col * (0.8 + 0.35 * h);
    gl_Position = u_vp * vec4(p - u_cam, 1.0);
}
"""
FS_SIMPLE = """
#version 330
""" + COMUN + """
in vec3 v_pos;
in vec3 v_nrm;
in vec3 v_col;
out vec4 f;
void main() {
    vec3 N = normalize(v_nrm);
    float dif = max(dot(N, u_sol), 0.0);
    vec3 col = v_col * (u_colsol * dif + u_amb * (0.6 + 0.4 * N.y));
    f = vec4(aire(col, v_pos), 1.0);
}
"""

VS_SPRITE = """
#version 330
uniform mat4 u_vp;
uniform vec3 u_cam;
uniform vec3 u_der;
uniform vec3 u_arr;
in vec2 in_esq;
in vec3 i_pos;
in float i_tam;
in vec4 i_col;
out vec2 v_uv;
out vec4 v_col;
out vec3 v_pos;
void main() {
    vec3 p = i_pos + (u_der * in_esq.x + u_arr * in_esq.y) * i_tam;
    v_uv = in_esq * 0.5 + 0.5;
    v_col = i_col;
    v_pos = p;
    gl_Position = u_vp * vec4(p - u_cam, 1.0);
}
"""
FS_NUBE = """
#version 330
""" + COMUN + """
uniform sampler2D u_tex;
in vec2 v_uv;
in vec4 v_col;
in vec3 v_pos;
out vec4 f;
void main() {
    vec4 t = texture(u_tex, v_uv);
    float lado = clamp(0.5 + 0.5 * dot(normalize(v_pos - u_cam), u_sol), 0.0, 1.0);
    vec3 luz = u_colsol * (0.55 + 0.6 * t.r + 0.35 * pow(lado, 4.0)) + u_amb * 1.15;
    vec3 c = mix(u_amb * 0.9 + u_colsol * 0.25, vec3(1.0) * luz, t.r * v_col.r);
    float d = length(v_pos - u_cam);
    float cerca = smoothstep(20.0, 160.0, d);
    f = vec4(aire(c, v_pos), t.a * v_col.a * cerca);
}
"""
FS_HUMO = """
#version 330
""" + COMUN + """
uniform sampler2D u_tex;
uniform int u_aditivo;
in vec2 v_uv;
in vec4 v_col;
in vec3 v_pos;
out vec4 f;
void main() {
    vec4 t = texture(u_tex, v_uv);
    if (u_aditivo == 1) {
        float r = length(v_uv - 0.5) * 2.0;
        float a = (1.0 - smoothstep(0.0, 1.0, r)) * v_col.a;
        f = vec4(v_col.rgb * a, a);
    } else {
        vec3 c = v_col.rgb * (u_colsol * 0.5 + u_amb * 1.2) * (0.7 + 0.5 * t.r);
        f = vec4(aire(c, v_pos), t.a * v_col.a);
    }
}
"""

VS_LUZ = """
#version 330
uniform mat4 u_vp;
uniform vec3 u_cam;
uniform float u_px;
in vec3 in_pos;
in vec3 in_col;
in float in_tipo;
out vec3 v_col;
out float v_k;
void main() {
    vec3 r = in_pos - u_cam;
    float d = length(r);
    vec3 c = in_col;
    if (in_tipo > 0.5 && in_tipo < 5.0) {
        float ang = degrees(atan(-r.y, length(r.xz)));
        c = ang > in_tipo ? vec3(1.0, 0.95, 0.9) : vec3(1.0, 0.1, 0.05);
    }
    v_col = c;
    v_k = clamp(1.0 - d / 30000.0, 0.0, 1.0);
    gl_PointSize = clamp(u_px * 1400.0 / d, 2.2, 10.0);
    gl_Position = u_vp * vec4(r, 1.0);
}
"""
FS_LUZ = """
#version 330
uniform float u_intensidad;
in vec3 v_col;
in float v_k;
out vec4 f;
void main() {
    float r = length(gl_PointCoord - 0.5) * 2.0;
    float a = (1.0 - smoothstep(0.2, 1.0, r)) * u_intensidad * (0.35 + 0.65 * v_k);
    f = vec4(v_col * a, a);
}
"""

VS_TEX2D = """
#version 330
in vec2 in_pos;
in vec2 in_uv;
out vec2 v_uv;
void main() { v_uv = in_uv; gl_Position = vec4(in_pos, 0.0, 1.0); }
"""
FS_TEX2D = """
#version 330
uniform sampler2D u_tex;
in vec2 v_uv;
out vec4 f;
void main() { f = texture(u_tex, v_uv); }
"""

VS_PANEL = """
#version 330
uniform mat4 u_vp;
uniform mat4 u_m;
in vec3 in_pos;
in vec2 in_uv;
out vec2 v_uv;
void main() { v_uv = in_uv; gl_Position = u_vp * u_m * vec4(in_pos, 1.0); }
"""
FS_PANEL = """
#version 330
uniform sampler2D u_tex;
uniform vec3 u_luz;
uniform float u_auto;
in vec2 v_uv;
out vec4 f;
void main() {
    vec4 t = texture(u_tex, v_uv);
    vec3 emis = t.rgb * t.a;
    f = vec4(t.rgb * u_luz + emis * u_auto, 1.0);
}
"""

VS_LLAMA = """
#version 330
uniform mat4 u_vp;
uniform mat4 u_m;
uniform float u_largo;
in vec3 in_pos;
out float v_t;
out float v_r;
void main() {
    vec3 p = in_pos;
    v_t = -p.x;
    v_r = length(p.yz);
    p.x *= u_largo;
    gl_Position = u_vp * u_m * vec4(p, 1.0);
}
"""
FS_LLAMA = """
#version 330
uniform float u_pq;
uniform float u_t;
in float v_t;
in float v_r;
out vec4 f;
void main() {
    float diamante = 0.6 + 0.4 * sin(v_t * 28.0 - u_t * 4.0);
    vec3 c = mix(vec3(1.0, 0.95, 0.85), vec3(1.0, 0.45, 0.12), smoothstep(0.0, 0.7, v_t));
    c = mix(vec3(0.55, 0.65, 1.0), c, smoothstep(0.0, 0.25, v_t));
    float a = (1.0 - v_t) * u_pq * (0.65 + 0.35 * diamante);
    f = vec4(c * a, a);
}
"""


VS_BORRA = """
#version 330
in vec2 in_pos;
void main() { gl_Position = vec4(in_pos, 1.0, 1.0); }
"""
FS_BORRA = """
#version 330
out vec4 f;
void main() { f = vec4(0.0); }
"""


def perspectiva(fovy, aspecto, cerca, lejos):
    f = 1 / math.tan(math.radians(fovy) / 2)
    m = np.zeros((4, 4))
    m[0, 0] = f / aspecto
    m[1, 1] = f
    m[2, 2] = (lejos + cerca) / (cerca - lejos)
    m[2, 3] = 2 * lejos * cerca / (cerca - lejos)
    m[3, 2] = -1
    return m


def vista(adelante, arriba):
    f = adelante / np.linalg.norm(adelante)
    r = np.cross(f, arriba)
    r /= np.linalg.norm(r)
    u = np.cross(r, f)
    m = np.eye(4)
    m[0, :3], m[1, :3], m[2, :3] = r, u, -f
    return m


def _m4(R, t):
    m = np.eye(4)
    m[:3, :3] = R
    m[:3, 3] = t
    return m


def _rot_eje(eje, ang):
    eje = eje / np.linalg.norm(eje)
    x, y, z = eje
    c, s = math.cos(ang), math.sin(ang)
    C = 1 - c
    return np.array([[c + x * x * C, x * y * C - z * s, x * z * C + y * s],
                     [y * x * C + z * s, c + y * y * C, y * z * C - x * s],
                     [z * x * C - y * s, z * y * C + x * s, c + z * z * C]])


def _filtrar(prog, contenido):
    salida = []
    for buf, fmt, *nombres in contenido:
        partes = fmt.split()
        inst = partes[-1].endswith("/i")
        if inst:
            partes[-1] = partes[-1][:-2]
        nuevas, usados = [], []
        for parte, nombre in zip(partes, nombres):
            if nombre in prog:
                nuevas.append(parte)
                usados.append(nombre)
            else:
                nuevas.append(f"{int(parte[:-1]) * 4}x")
        f = " ".join(nuevas) + ("/i" if inst else "")
        salida.append((buf, f, *usados))
    return salida


def _w(prog, nombre, m):
    if nombre in prog:
        prog[nombre].write(np.asarray(m, dtype="f4").T.copy().tobytes())


def _v(prog, nombre, v):
    if nombre in prog:
        prog[nombre].value = v


HORAS = {
    "amanecer": dict(sol=(0.75, 0.16, -0.35), cenit=(0.20, 0.33, 0.58), horiz=(0.92, 0.66, 0.52),
                     colsol=(1.25, 0.82, 0.58), amb=(0.20, 0.21, 0.27), niebla=0.00010, noche=0.0, luces=0.7),
    "mediodía": dict(sol=(0.35, 0.82, 0.25), cenit=(0.18, 0.38, 0.75), horiz=(0.66, 0.78, 0.92),
                     colsol=(1.25, 1.18, 1.05), amb=(0.27, 0.32, 0.40), niebla=0.000075, noche=0.0, luces=0.35),
    "tarde": dict(sol=(-0.62, 0.42, 0.45), cenit=(0.22, 0.38, 0.70), horiz=(0.80, 0.78, 0.76),
                  colsol=(1.25, 1.05, 0.80), amb=(0.25, 0.28, 0.35), niebla=0.00009, noche=0.0, luces=0.45),
    "atardecer": dict(sol=(-0.8, 0.09, 0.4), cenit=(0.13, 0.20, 0.42), horiz=(0.98, 0.52, 0.30),
                      colsol=(1.2, 0.58, 0.30), amb=(0.16, 0.14, 0.20), niebla=0.00011, noche=0.15, luces=0.9),
    "noche": dict(sol=(-0.4, 0.5, 0.6), cenit=(0.008, 0.013, 0.035), horiz=(0.04, 0.055, 0.09),
                  colsol=(0.13, 0.15, 0.21), amb=(0.05, 0.06, 0.09), niebla=0.00007, noche=1.0, luces=1.0),
}
NUBES = {"despejado": 0, "dispersas": 70, "nublado": 190}


class Renderizador:
    def __init__(self, ctx, ancho, alto):
        self.ctx = ctx
        self.ancho, self.alto = ancho, alto
        self.t = 0.0
        self.destino = None
        self.progs = {}
        self.hora = "tarde"
        self.cielo_cfg = HORAS[self.hora]
        self._programas()
        self._texturas()
        self._terreno()
        self._agua()
        self._aeropuertos()
        self._vegetacion()
        self._aviones()
        self._sprites()
        self._cuadros()
        self.nubes(NUBES["dispersas"])
        self.panel_tex = ctx.texture((1024, 512), 4)
        self.panel_tex.filter = (moderngl.LINEAR_MIPMAP_LINEAR, moderngl.LINEAR)
        self.hud_tex = ctx.texture((ancho, alto), 4)

    def redimensionar(self, ancho, alto):
        self.ancho, self.alto = ancho, alto
        self.hud_tex.release()
        self.hud_tex = self.ctx.texture((ancho, alto), 4)

    def _va(self, prog, contenido, ibo=None):
        if ibo is None:
            return self.ctx.vertex_array(prog, _filtrar(prog, contenido))
        return self.ctx.vertex_array(prog, _filtrar(prog, contenido), ibo)

    def _prog(self, nombre, vs, fs, defs=""):
        if defs:
            fs = fs.replace("#version 330", "#version 330\n" + defs, 1)
        p = self.ctx.program(vertex_shader=vs, fragment_shader=fs)
        self.progs[nombre] = p
        return p

    def _programas(self):
        self._prog("cielo", VS_CIELO, FS_CIELO)
        self._prog("terreno", VS_TERRENO, FS_TERRENO)
        self._prog("agua", VS_AGUA, FS_AGUA)
        self._prog("pista", VS_PISTA, FS_PISTA)
        self._prog("obj", VS_OBJ, FS_OBJ)
        self._prog("obj_inst", VS_OBJ_INST, FS_OBJ, "#define INST")
        self._prog("arbol", VS_INST_ARBOL, FS_SIMPLE)
        self._prog("edif", VS_INST_EDIF, FS_SIMPLE)
        self._prog("nube", VS_SPRITE, FS_NUBE)
        self._prog("humo", VS_SPRITE, FS_HUMO)
        self._prog("luz", VS_LUZ, FS_LUZ)
        self._prog("tex2d", VS_TEX2D, FS_TEX2D)
        self._prog("panel", VS_PANEL, FS_PANEL)
        self._prog("llama", VS_LLAMA, FS_LLAMA)
        self._prog("borra", VS_BORRA, FS_BORRA)

    def _tex(self, img, mip=True, repetir=True, componentes=None):
        h, w = img.shape[:2]
        c = componentes or (img.shape[2] if img.ndim == 3 else 1)
        t = self.ctx.texture((w, h), c, np.ascontiguousarray(img).tobytes())
        if mip:
            t.build_mipmaps()
            t.filter = (moderngl.LINEAR_MIPMAP_LINEAR, moderngl.LINEAR)
            try:
                t.anisotropy = 8.0
            except Exception:
                pass
        t.repeat_x = t.repeat_y = repetir
        return t

    def _texturas(self):
        self.t_ruido = self._tex(TX.ruido_rgba())
        h = T.ALTURAS.astype("f4")
        self.t_alturas = self.ctx.texture((h.shape[1], h.shape[0]), 1, h.tobytes(), dtype="f4")
        self.t_alturas.repeat_x = self.t_alturas.repeat_y = False
        b = (np.clip(T.DENSIDAD, 0, 1) * 255).astype(np.uint8)
        self.t_bosque = self._tex(b, repetir=False)
        self.t_nube = self._tex(TX.mancha(128, 3, 0.7), repetir=False)
        self.t_humo = self._tex(TX.mancha(64, 8, 0.9), repetir=False)
        self.t_concreto = self._tex(TX.concreto())

    def _comunes(self, p, cam):
        cfg = self.cielo_cfg
        sol = np.array(cfg["sol"], float)
        sol /= np.linalg.norm(sol)
        _v(p, "u_cam", tuple(cam))
        _v(p, "u_sol", tuple(sol))
        for k in ("cenit", "horiz", "colsol", "amb"):
            _v(p, "u_" + k, tuple(cfg[k]))
        _v(p, "u_niebla", cfg["niebla"] * self.factor_niebla)
        _v(p, "u_noche", cfg["noche"])
        _v(p, "u_t", self.t)
        _v(p, "u_mitad", float(T.MITAD))

    def _terreno(self):
        n = T.N + 1
        eje = np.linspace(-T.MITAD, T.MITAD, n)
        X, Z = np.meshgrid(eje, eje)
        nrm = T.normales()
        v = np.concatenate([np.stack([X, T.ALTURAS, Z], -1), nrm], -1).reshape(-1, 6).astype("f4")
        self.vbo_terreno = self.ctx.buffer(v.tobytes())
        bloque = 32
        self.bloques = []
        indices = []
        base = 0
        for bi in range(0, T.N, bloque):
            for bj in range(0, T.N, bloque):
                lods = []
                for paso in (1, 2, 4, 8):
                    idx = []
                    for i in range(bi, bi + bloque, paso):
                        for j in range(bj, bj + bloque, paso):
                            a = i * n + j
                            b = a + paso
                            c = (i + paso) * n + j
                            d = c + paso
                            idx += [a, c, b, b, c, d]
                    lods.append((base, len(idx)))
                    base += len(idx)
                    indices += idx
                cx = eje[bi + bloque // 2]
                cz = eje[bj + bloque // 2]
                hs = T.ALTURAS[bi:bi + bloque + 1, bj:bj + bloque + 1]
                self.bloques.append((np.array([eje[bj + bloque // 2], float(hs.mean()), eje[bi + bloque // 2]]),
                                     float(hs.max()), float(hs.min()), lods))
        self.ibo_terreno = self.ctx.buffer(np.array(indices, dtype="i4").tobytes())
        self.vao_terreno = self._va(self.progs["terreno"], [(self.vbo_terreno, "3f 3f", "in_pos", "in_nrm")],
                                                 self.ibo_terreno)
        self.radio_bloque = bloque * T.CELDA * 0.75

    def _agua(self):
        anillos = []
        r = [0, 400, 1200, 3000, 7000, 15000, 30000, 70000, 140000]
        pts = []
        tris = []
        seg = 48
        for k, rad in enumerate(r):
            for i in range(seg):
                t = 2 * math.pi * i / seg
                pts.append((rad * math.cos(t), rad * math.sin(t)))
        for k in range(len(r) - 1):
            for i in range(seg):
                j = (i + 1) % seg
                a, b = k * seg + i, k * seg + j
                c, d = (k + 1) * seg + i, (k + 1) * seg + j
                tris += [a, c, b, b, c, d]
        vbo = self.ctx.buffer(np.array(pts, "f4").tobytes())
        ibo = self.ctx.buffer(np.array(tris, "i4").tobytes())
        self.vao_agua = self._va(self.progs["agua"], [(vbo, "2f", "in_pos")], ibo)

    def _rect(self, a, s0, s1, l0, l1, y, uv_fn):
        p = [a.mundo(s, l, y) for s, l in ((s0, l0), (s1, l0), (s1, l1), (s0, l1))]
        uv = [uv_fn(s, l) for s, l in ((s0, l0), (s1, l0), (s1, l1), (s0, l1))]
        v = [np.concatenate([p[i], uv[i]]) for i in (0, 1, 2, 0, 2, 3)]
        return v

    def _aeropuertos(self):
        self.pistas = []
        luces = []
        for k, a in enumerate(T.AEROPUERTOS):
            img, margen = TX.pista(a.largo, a.ancho, a.numero, 9 + k)
            tex = self._tex(img, repetir=False)
            w = a.ancho / 2 + margen
            v = self._rect(a, 0, a.largo, -w, w, a.elev + 0.06,
                           lambda s, l: ((l + w) / (2 * w), s / a.largo))
            vbo = self.ctx.buffer(np.array(v, "f4").tobytes())
            vao = self._va(self.progs["pista"], [(vbo, "3f 2f", "in_pos", "in_uv")])
            calle = []
            lt = -(a.ancho / 2 + 140)
            uvm = (lambda lc: (lambda s, l: (l - lc, s)))
            calle += self._rect(a, -60, a.largo + 60, lt - 11.5, lt + 11.5, a.elev + 0.05, uvm(lt))
            for sc in (-40, a.largo * 0.5, a.largo + 40):
                calle += self._rect(a, sc - 11.5, sc + 11.5, lt, -a.ancho / 2 - margen, a.elev + 0.045,
                                    lambda s, l, sc=sc: (s - sc, l))
            plat = self._rect(a, 550, (2300 if k == 0 else 1500), -(a.ancho / 2 + 380), lt - 11.5, a.elev + 0.04,
                              lambda s, l: (l * 0.7 + 30, s * 0.7))
            vbo_c = self.ctx.buffer(np.array(calle, "f4").tobytes())
            vbo_p = self.ctx.buffer(np.array(plat, "f4").tobytes())
            self.pistas.append((vao, tex,
                                self._va(self.progs["pista"], [(vbo_c, "3f 2f", "in_pos", "in_uv")]),
                                self._va(self.progs["pista"], [(vbo_p, "3f 2f", "in_pos", "in_uv")])))
            y = a.elev + 0.5
            for s in np.arange(0, a.largo + 1, 60):
                col = (1.0, 0.85, 0.45) if s > a.largo - 600 else (1.0, 0.95, 0.85)
                for l in (-a.ancho / 2 - 1, a.ancho / 2 + 1):
                    luces.append((*a.mundo(s, l, y), *col, 0))
            for l in np.linspace(-a.ancho / 2, a.ancho / 2, 10):
                luces.append((*a.mundo(-2, l, y), 0.2, 1.0, 0.3, 0))
                luces.append((*a.mundo(a.largo + 2, l, y), 1.0, 0.1, 0.05, 0))
            for d in np.arange(60, 901, 30):
                h = float(T.superficie(*a.mundo(-d, 0)[[0, 2]]))
                for l in np.linspace(-4.5, 4.5, 5):
                    luces.append((*a.mundo(-d, l, max(h, a.elev) + 1.5), 1.0, 0.95, 0.85, 0))
                if d % 150 == 0:
                    for l in np.linspace(-13, 13, 9):
                        luces.append((*a.mundo(-d, l, max(h, a.elev) + 1.5), 1.0, 0.95, 0.85, 0))
            for i, umbral in enumerate((3.5, 3.17, 2.83, 2.5)):
                luces.append((*a.mundo(400, -(a.ancho / 2 + 15 + 9 * i), y), 1, 1, 1, umbral))
            for s in np.arange(-60, a.largo + 61, 60):
                for l in (lt - 12.5, lt + 12.5):
                    luces.append((*a.mundo(s, l, y), 0.2, 0.35, 1.0, 0))
        for e in T.EDIFICIOS:
            if e[7] == 0 and e[4] < 60:
                luces.append((e[0], e[1] + e[4] * 0.6, e[2], 1.0, 0.72, 0.35, 0))
        self.estrobos = []
        a = T.BASE
        for d in np.arange(900, 300, -30):
            h = float(T.superficie(*a.mundo(-d, 0)[[0, 2]]))
            self.estrobos.append(a.mundo(-d, 0, max(h, a.elev) + 2))
        self.estrobos = np.array(self.estrobos)
        luces = np.array(luces, "f4")
        self.vbo_luces = self.ctx.buffer(luces.tobytes())
        self.vao_luces = self._va(self.progs["luz"], [(self.vbo_luces, "3f 3f 1f", "in_pos", "in_col",
                                                                     "in_tipo")])
        self.n_luces = len(luces)
        self.vbo_puntos = self.ctx.buffer(reserve=4 * 7 * 4096)
        self.vao_puntos = self._va(self.progs["luz"], [(self.vbo_puntos, "3f 3f 1f", "in_pos", "in_col",
                                                                      "in_tipo")])

    def _vegetacion(self):
        self.arboles = T.arboles()
        m = MD.arbol()
        self.vbo_arbol = self.ctx.buffer(m.tobytes())
        self.n_arbol = len(m)
        self.ibuf_arbol = self.ctx.buffer(reserve=len(self.arboles) * 5 * 4)
        self.vao_arbol = self._va(self.progs["arbol"], [
            (self.vbo_arbol, "3f 3f 3f 1f", "in_pos", "in_nrm", "in_col", "in_mat"),
            (self.ibuf_arbol, "3f 1f 1f/i", "i_pos", "i_esc", "i_tono")])
        self.arboles_visibles = 0
        self.cam_arboles = np.array([1e9, 0, 1e9])
        e = T.EDIFICIOS
        self.edif = []
        for tipo, malla in ((0, MD.edificio()), (1, MD.hangar()), (2, MD.torre())):
            sel = e[e[:, 7] == tipo]
            if not len(sel):
                continue
            inst = np.concatenate([sel[:, 0:3], sel[:, 3:6], -np.radians(sel[:, 6:7]) + math.pi / 2], 1).astype("f4")
            vb = self.ctx.buffer(malla.tobytes())
            ib = self.ctx.buffer(inst.tobytes())
            vao = self._va(self.progs["edif"], [(vb, "3f 3f 3f 1f", "in_pos", "in_nrm", "in_col", "in_mat"),
                                                             (ib, "3f 3f 1f/i", "i_pos", "i_tam", "i_rot")])
            self.edif.append((vao, len(malla), len(inst)))

    def _vao_obj(self, arreglo, prog="obj"):
        vb = self.ctx.buffer(arreglo.tobytes())
        return self._va(self.progs[prog], [(vb, "3f 3f 3f 1f", "in_pos", "in_nrm", "in_col", "in_mat")]), \
            len(arreglo)

    def _aviones(self):
        self.piezas = MD.f15()
        self.vao_piezas = {k: self._vao_obj(p.malla.arreglo()) for k, p in self.piezas.items()}
        self.inst_buf = self.ctx.buffer(reserve=16 * 4 * 256)
        self.vao_fantasma = {}
        for tren in (True, False):
            arr = MD.estatico(self.piezas, tren)
            vb = self.ctx.buffer(arr.tobytes())
            vao = self._va(self.progs["obj_inst"], [
                (vb, "3f 3f 3f 1f", "in_pos", "in_nrm", "in_col", "in_mat"),
                (self.inst_buf, "4f 4f 4f 4f/i", "i_a", "i_b", "i_c", "i_d")])
            self.vao_fantasma[tren] = vao
        self.vao_dron = self._vao_obj(MD.dron())
        self.vao_misil = self._vao_obj(MD.misil_suelto())
        self.vao_cabina = self._vao_obj(MD.cabina())
        self.vao_palanca = self._vao_obj(MD.palanca())
        self.vao_acel = self._vao_obj(MD.acelerador())
        cono = []
        n = 14
        for i in range(n):
            t0, t1 = 2 * math.pi * i / n, 2 * math.pi * (i + 1) / n
            for (x0, r0), (x1, r1) in (((0, 0.42), (-0.35, 0.33)), ((-0.35, 0.33), (-1.0, 0.0))):
                a = (x0, r0 * math.cos(t0), r0 * math.sin(t0))
                b = (x0, r0 * math.cos(t1), r0 * math.sin(t1))
                c = (x1, r1 * math.cos(t1), r1 * math.sin(t1))
                d = (x1, r1 * math.cos(t0), r1 * math.sin(t0))
                cono += [a, b, c, a, c, d]
        vb = self.ctx.buffer(np.array(cono, "f4").tobytes())
        self.vao_llama = self._va(self.progs["llama"], [(vb, "3f", "in_pos")])

    def _sprites(self):
        esq = np.array([(-1, -1), (1, -1), (1, 1), (-1, -1), (1, 1), (-1, 1)], "f4")
        self.vbo_esq = self.ctx.buffer(esq.tobytes())
        self.ibuf_nube = self.ctx.buffer(reserve=8 * 4 * 4000)
        self.vao_nube = self._va(self.progs["nube"], [(self.vbo_esq, "2f", "in_esq"),
                                                                   (self.ibuf_nube, "3f 1f 4f/i", "i_pos", "i_tam",
                                                                    "i_col")])
        self.ibuf_humo = self.ctx.buffer(reserve=8 * 4 * 6000)
        self.vao_humo = self._va(self.progs["humo"], [(self.vbo_esq, "2f", "in_esq"),
                                                                   (self.ibuf_humo, "3f 1f 4f/i", "i_pos", "i_tam",
                                                                    "i_col")])

    def _cuadros(self):
        q = np.array([(-1, -1), (1, -1), (1, 1), (-1, -1), (1, 1), (-1, 1)], "f4")
        self.vao_cielo = self._va(self.progs["cielo"], [(self.ctx.buffer(q.tobytes()), "2f", "in_pos")])
        self.vao_borra = self._va(self.progs["borra"], [(self.ctx.buffer(q.tobytes()), "2f", "in_pos")])
        hud = np.array([(-1, -1, 0, 1), (1, -1, 1, 1), (1, 1, 1, 0), (-1, -1, 0, 1), (1, 1, 1, 0), (-1, 1, 0, 0)],
                       "f4")
        self.vao_hud = self._va(self.progs["tex2d"], [(self.ctx.buffer(hud.tobytes()), "2f 2f",
                                                                    "in_pos", "in_uv")])
        x, y0, y1, z0, z1 = 5.715, 0.605, 1.055, -0.465, 0.465
        panel = np.array([(x, y0, z0, 0, 1), (x, y0, z1, 1, 1), (x, y1, z1, 1, 0),
                          (x, y0, z0, 0, 1), (x, y1, z1, 1, 0), (x, y1, z0, 0, 0)], "f4")
        self.vao_panel = self._va(self.progs["panel"], [(self.ctx.buffer(panel.tobytes()), "3f 2f",
                                                                      "in_pos", "in_uv")])

    def nubes(self, cantidad, semilla=31):
        rng = np.random.default_rng(semilla)
        puf = []
        for _ in range(cantidad):
            cx, cz = rng.uniform(-T.MITAD * 1.3, T.MITAD * 1.3, 2)
            base = rng.uniform(1700, 2600)
            ancho = rng.uniform(500, 1500)
            for _ in range(int(rng.integers(8, 20))):
                ox, oz = rng.normal(0, ancho * 0.45, 2)
                r = rng.uniform(140, 380)
                oy = abs(rng.normal(0, 160)) + r * 0.3
                brillo = 0.85 + 0.15 * min(1, oy / 300)
                puf.append((cx + ox, base + oy, cz + oz, r, brillo, 0, 0, rng.uniform(0.55, 0.85)))
        self.puf = np.array(puf, "f4").reshape(-1, 8)
        self.n_nubes_total = cantidad

    def dentro_nube(self, cam):
        if not len(self.puf):
            return 0.0
        d = np.linalg.norm(self.puf[:, :3] - cam, axis=1) / self.puf[:, 3]
        return float(np.clip(1.2 - d.min(), 0, 1))

    def configurar(self, hora=None):
        if hora:
            self.hora = hora
            self.cielo_cfg = HORAS[hora]

    def _bloques_visibles(self, cam, fwd, fov_cos):
        if not hasattr(self, "_b_centro"):
            self._b_centro = np.array([b[0] for b in self.bloques])
            self._b_max = np.array([b[1] for b in self.bloques])
            self._b_min = np.array([b[2] for b in self.bloques])
            self._b_lods = np.array([b[3] for b in self.bloques])
        c = self._b_centro.copy()
        c[:, 1] = np.clip(cam[1], self._b_min, self._b_max)
        r = c - cam
        d = np.linalg.norm(r, axis=1) + 1e-6
        cerca = d <= self.radio_bloque * 1.5
        visible = cerca | (r @ fwd / d >= fov_cos - self.radio_bloque / d * 1.4)
        lod = np.digitize(d, [5000, 12000, 24000])
        idx = np.flatnonzero(visible)
        return self._b_lods[idx, lod[idx]].tolist()

    def dibujar(self, esc):
        ctx = self.ctx
        self.t = esc["t"]
        self.factor_niebla = esc.get("niebla", 1.0)
        cam = np.asarray(esc["cam"], float)
        fwd, arr = esc["adelante"], esc["arriba"]
        aspecto = self.ancho / self.alto
        V = vista(fwd, arr)
        P = perspectiva(esc["fov"], aspecto, 1.5, 160000.0)
        VP = P @ V
        der = np.cross(fwd, arr)
        der /= np.linalg.norm(der)
        arr2 = np.cross(der, fwd)
        ctx.disable(moderngl.CULL_FACE)
        ctx.enable(moderngl.DEPTH_TEST)
        ctx.depth_func = "<"
        ctx.disable(moderngl.BLEND)

        p = self.progs["cielo"]
        self._comunes(p, cam)
        _w(p, "u_inv", np.linalg.inv(VP))
        self.t_ruido.use(0)
        _v(p, "u_ruido", 0)
        ctx.depth_mask = False
        self.vao_cielo.render()
        ctx.depth_mask = True

        p = self.progs["terreno"]
        self._comunes(p, cam)
        _w(p, "u_vp", VP)
        self.t_ruido.use(0)
        self.t_bosque.use(1)
        _v(p, "u_ruido", 0)
        _v(p, "u_bosque", 1)
        tan = math.tan(math.radians(esc["fov"]) / 2) * math.sqrt(1 + aspecto * aspecto)
        fov_cos = math.cos(math.atan(tan))
        for ini, cant in self._bloques_visibles(cam, fwd, fov_cos):
            self.vao_terreno.render(moderngl.TRIANGLES, vertices=cant, first=ini)

        p = self.progs["agua"]
        self._comunes(p, cam)
        _w(p, "u_vp", VP)
        self.t_ruido.use(0)
        self.t_alturas.use(2)
        _v(p, "u_ruido", 0)
        _v(p, "u_alturas", 2)
        self.vao_agua.render()

        p = self.progs["pista"]
        self._comunes(p, cam)
        _w(p, "u_vp", VP)
        ctx.polygon_offset = (-2.0, -8.0)
        for vao, tex, vao_c, vao_p in self.pistas:
            self.t_concreto.use(0)
            self.t_ruido.use(1)
            _v(p, "u_tex", 0)
            _v(p, "u_ruido", 1)
            _v(p, "u_tipo", 2)
            vao_p.render()
            _v(p, "u_tipo", 1)
            vao_c.render()
            tex.use(0)
            _v(p, "u_tipo", 0)
            vao.render()
        ctx.polygon_offset = (0.0, 0.0)

        if np.linalg.norm(cam[[0, 2]] - self.cam_arboles[[0, 2]]) > 400:
            self.cam_arboles = cam.copy()
            d = np.hypot(self.arboles[:, 0] - cam[0], self.arboles[:, 2] - cam[2])
            sel = self.arboles[d < 9000]
            self.ibuf_arbol.write(sel.tobytes())
            self.arboles_visibles = len(sel)
        if self.arboles_visibles and cam[1] < 6000:
            p = self.progs["arbol"]
            self._comunes(p, cam)
            _w(p, "u_vp", VP)
            self.vao_arbol.render(instances=self.arboles_visibles)
        p = self.progs["edif"]
        self._comunes(p, cam)
        _w(p, "u_vp", VP)
        for vao, nv, ni in self.edif:
            vao.render(instances=ni)

        self._aviones_ext(esc, cam, VP)
        self._efectos(esc, cam, VP, der, arr2)

        self._borrar_profundidad()
        Pc = perspectiva(esc["fov"], aspecto, 0.04, 80.0)
        VPc = Pc @ V
        propio = esc.get("propio")
        if propio is not None:
            self._propio(propio, cam, VPc, esc)
        ctx.disable(moderngl.DEPTH_TEST)

    def _borrar_profundidad(self):
        ctx = self.ctx
        fbo = self.destino or ctx.screen
        mascara = fbo.color_mask
        fbo.color_mask = (False, False, False, False)
        fbo.use()
        ctx.depth_func = "1"
        ctx.depth_mask = True
        self.vao_borra.render()
        ctx.depth_func = "<"
        fbo.color_mask = mascara
        fbo.use()

    def _matriz_avion(self, pos, R, cam):
        return _m4(R, pos - cam)

    def _aviones_ext(self, esc, cam, VP):
        ctx = self.ctx
        p = self.progs["obj_inst"]
        self._comunes(p, cam)
        _w(p, "u_vp", VP)
        self.t_ruido.use(0)
        _v(p, "u_ruido", 0)
        _v(p, "u_camuflaje", 1)
        _v(p, "u_alfa", 1.0)
        otros = esc.get("otros", [])
        if otros:
            ctx.enable(moderngl.BLEND)
            ctx.blend_func = moderngl.SRC_ALPHA, moderngl.ONE_MINUS_SRC_ALPHA
            for tren in (True, False):
                sel = [o for o in otros if (o["tren"] > 0.5) == tren]
                if not sel:
                    continue
                m = np.zeros((len(sel), 16), "f4")
                for i, o in enumerate(sel[:256]):
                    R = o["R"]
                    t = o["pos"] - cam
                    m[i, 0:3], m[i, 3] = R[:, 0], o.get("tinte", 0.0)
                    m[i, 4:7] = R[:, 1]
                    m[i, 8:11] = R[:, 2]
                    m[i, 12:15], m[i, 15] = t, o.get("alfa", 1.0)
                self.inst_buf.write(m[:256].tobytes())
                ctx.depth_mask = True
                self.vao_fantasma[tren].render(instances=min(len(sel), 256))
            ctx.disable(moderngl.BLEND)
        p = self.progs["obj"]
        self._comunes(p, cam)
        _w(p, "u_vp", VP)
        _v(p, "u_ruido", 0)
        _v(p, "u_camuflaje", 0)
        _v(p, "u_alfa", 1.0)
        for d in esc.get("drones", []):
            _w(p, "u_m", self._matriz_avion(d["pos"], d["R"], cam))
            self.vao_dron[0].render()
        for mi in esc.get("misiles", []):
            _w(p, "u_m", self._matriz_avion(mi["pos"], mi["R"], cam))
            self.vao_misil[0].render()
        llamas = [o for o in otros if o.get("pq", 0) > 0.02 and np.linalg.norm(o["pos"] - cam) < 6000]
        if llamas:
            ctx.enable(moderngl.BLEND)
            ctx.blend_func = moderngl.ONE, moderngl.ONE
            ctx.depth_mask = False
            p = self.progs["llama"]
            _w(p, "u_vp", VP)
            _v(p, "u_t", self.t)
            for o in llamas:
                for lado in (-1, 1):
                    off = o["R"] @ np.array([-9.55, 0.08, 0.64 * lado])
                    _w(p, "u_m", _m4(o["R"], o["pos"] + off - cam))
                    _v(p, "u_largo", 2.5 + 3.5 * o["pq"])
                    _v(p, "u_pq", min(1.0, o["pq"] * 1.3) * o.get("alfa", 1.0))
                    self.vao_llama.render()
            ctx.depth_mask = True
            ctx.disable(moderngl.BLEND)
        self._sombras(esc, cam, VP)

    def _sombras(self, esc, cam, VP):
        cfg = self.cielo_cfg
        if cfg["noche"] > 0.5:
            return
        sol = np.array(cfg["sol"], float)
        sol /= np.linalg.norm(sol)
        lista = list(esc.get("otros", []))
        if esc.get("propio") is not None:
            lista.append(esc["propio"])
        ctx = self.ctx
        p = self.progs["obj"]
        _v(p, "u_camuflaje", 0)
        ctx.enable(moderngl.BLEND)
        ctx.blend_func = moderngl.SRC_ALPHA, moderngl.ONE_MINUS_SRC_ALPHA
        ctx.depth_mask = False
        ctx.polygon_offset = (-1.0, -8.0)
        guardado = {k: p[k].value for k in ("u_colsol", "u_amb")}
        _v(p, "u_colsol", (0.0, 0.0, 0.0))
        _v(p, "u_amb", (0.0, 0.0, 0.0))
        for o in lista[:40]:
            pos = o["pos"]
            if np.linalg.norm(pos - cam) > 3000:
                continue
            suelo = float(T.superficie(pos[0], pos[2])) + 0.08
            h = pos[1] - suelo
            if h > 300 or h < -1:
                continue
            proy = np.eye(4)
            proy[0, 1] = -sol[0] / sol[1]
            proy[2, 1] = -sol[2] / sol[1]
            proy[1, 1] = 0.0
            proy[:3, 3] = [0, suelo, 0]
            trasl = np.eye(4)
            trasl[:3, 3] = -cam
            M = trasl @ proy @ _m4(o["R"], pos)
            _w(p, "u_m", M)
            _v(p, "u_alfa", 0.45 * max(0.0, 1 - h / 300) * o.get("alfa", 1.0))
            for nombre, (vao, n) in self.vao_piezas.items():
                if nombre.startswith("tren") and o["tren"] < 0.5 or nombre == "frente_baja":
                    continue
                vao.render()
        _v(p, "u_colsol", guardado["u_colsol"])
        _v(p, "u_amb", guardado["u_amb"])
        _v(p, "u_alfa", 1.0)
        ctx.polygon_offset = (0.0, 0.0)
        ctx.depth_mask = True
        ctx.disable(moderngl.BLEND)

    def _efectos(self, esc, cam, VP, der, arr):
        ctx = self.ctx
        cfg = self.cielo_cfg
        ctx.enable(moderngl.BLEND)
        ctx.enable(moderngl.PROGRAM_POINT_SIZE)
        ctx.depth_mask = False
        ctx.blend_func = moderngl.ONE, moderngl.ONE
        p = self.progs["luz"]
        _w(p, "u_vp", VP)
        _v(p, "u_cam", tuple(cam))
        _v(p, "u_px", self.alto / 720.0)
        _v(p, "u_intensidad", cfg["luces"])
        self.vao_luces.render(moderngl.POINTS, vertices=self.n_luces)
        pts = list(esc.get("puntos", []))
        k = int(self.t * 2.0 * len(self.estrobos)) % len(self.estrobos)
        e = self.estrobos[k]
        pts.append((*e, 1.6, 1.6, 1.7, 0))
        if pts:
            arr_p = np.array(pts[:4096], "f4")
            self.vbo_puntos.write(arr_p.tobytes())
            _v(p, "u_intensidad", 1.0)
            self.vao_puntos.render(moderngl.POINTS, vertices=len(arr_p))

        humo = esc.get("humo", [])
        if len(humo):
            ctx.blend_func = moderngl.SRC_ALPHA, moderngl.ONE_MINUS_SRC_ALPHA
            h = np.asarray(humo, "f4")
            d = np.linalg.norm(h[:, :3] - cam, axis=1)
            h = h[np.argsort(-d)][:6000]
            self.ibuf_humo.write(h.tobytes())
            p = self.progs["humo"]
            self._comunes(p, cam)
            _w(p, "u_vp", VP)
            _v(p, "u_der", tuple(der))
            _v(p, "u_arr", tuple(arr))
            self.t_humo.use(0)
            _v(p, "u_tex", 0)
            _v(p, "u_aditivo", 0)
            self.vao_humo.render(instances=len(h))
        fuego = esc.get("fuego", [])
        if len(fuego):
            ctx.blend_func = moderngl.ONE, moderngl.ONE
            h = np.asarray(fuego, "f4")[:6000]
            self.ibuf_humo.write(h.tobytes())
            p = self.progs["humo"]
            self._comunes(p, cam)
            _w(p, "u_vp", VP)
            _v(p, "u_der", tuple(der))
            _v(p, "u_arr", tuple(arr))
            _v(p, "u_aditivo", 1)
            self.vao_humo.render(instances=len(h))

        if len(self.puf):
            ctx.blend_func = moderngl.SRC_ALPHA, moderngl.ONE_MINUS_SRC_ALPHA
            d = np.linalg.norm(self.puf[:, :3] - cam, axis=1)
            sel = d < 60000
            orden = np.argsort(-d[sel])
            datos = self.puf[sel][orden][:4000]
            self.ibuf_nube.write(datos.tobytes())
            p = self.progs["nube"]
            self._comunes(p, cam)
            _w(p, "u_vp", VP)
            _v(p, "u_der", tuple(der))
            _v(p, "u_arr", tuple(arr))
            self.t_nube.use(0)
            _v(p, "u_tex", 0)
            self.vao_nube.render(instances=len(datos))
        ctx.depth_mask = True
        ctx.disable(moderngl.BLEND)

    def _propio(self, o, cam, VP, esc):
        ctx = self.ctx
        ctx.enable(moderngl.DEPTH_TEST)
        p = self.progs["obj"]
        self._comunes(p, cam)
        _w(p, "u_vp", VP)
        self.t_ruido.use(0)
        _v(p, "u_ruido", 0)
        _v(p, "u_alfa", 1.0)
        R = o["R"]
        base = _m4(R, o["pos"] - cam)
        mando = o.get("mandos", {})
        angulos = {
            "estab_i": -0.35 * mando.get("elev", 0) + 0.2 * mando.get("alabeo", 0),
            "estab_d": -0.35 * mando.get("elev", 0) - 0.2 * mando.get("alabeo", 0),
            "aleron_i": 0.35 * mando.get("alabeo", 0), "aleron_d": 0.35 * mando.get("alabeo", 0),
            "flap_i": -0.5 * o.get("flaps", 0), "flap_d": -0.5 * o.get("flaps", 0),
            "timon_i": 0.4 * mando.get("timon", 0), "timon_d": 0.4 * mando.get("timon", 0),
            "aerofreno": 0.75 * o.get("aerofreno", 0),
            "tren_n": (1 - o.get("tren", 1)) * 1.7, "tren_i": -(1 - o.get("tren", 1)) * 1.5,
            "tren_d": (1 - o.get("tren", 1)) * 1.5,
        }
        misiles = o.get("misiles", 4)
        ocultar = {"canopy", "frente"}
        orden_m = ["misil_f0_i", "misil_f0_d", "misil_f1_i", "misil_f1_d", "misil_ala_i", "misil_ala_d",
                   "misil_ala2_i", "misil_ala2_d"]
        for k in range(len(orden_m) - min(8, misiles * 2)):
            ocultar.add(orden_m[-1 - k])
        for nombre, (vao, n) in self.vao_piezas.items():
            if nombre in ocultar:
                continue
            if nombre.startswith("tren") and o.get("tren", 1) < 0.02:
                continue
            pz = self.piezas[nombre]
            ang = angulos.get(nombre, 0.0)
            _v(p, "u_camuflaje", 1)
            if ang:
                Rl = _rot_eje(pz.eje, ang)
                local = _m4(Rl, pz.pivote - Rl @ pz.pivote)
                _w(p, "u_m", base @ local)
            else:
                _w(p, "u_m", base)
            vao.render()
        _v(p, "u_camuflaje", 0)
        _w(p, "u_m", base)
        self.vao_cabina[0].render()
        el, al = mando.get("elev", 0), mando.get("alabeo", 0)
        Rp = _rot_eje(np.array([0, 0, 1.0]), -0.25 * el) @ _rot_eje(np.array([1.0, 0, 0]), 0.25 * al)
        _w(p, "u_m", base @ _m4(Rp, MD.PALANCA_PIVOTE))
        self.vao_palanca[0].render()
        g = o.get("gases", 0)
        Ra = _rot_eje(np.array([0, 0, 1.0]), -0.5 + 0.9 * g)
        _w(p, "u_m", base @ _m4(Ra, MD.ACELERADOR_PIVOTE))
        self.vao_acel[0].render()
        pp = self.progs["panel"]
        _w(pp, "u_vp", VP)
        _w(pp, "u_m", base)
        cfg = self.cielo_cfg
        luz = np.array(cfg["colsol"]) * max(0.15, np.dot(R[:, 1], np.array(cfg["sol"]) /
                                                         np.linalg.norm(cfg["sol"]))) * 0.35 + np.array(cfg["amb"])
        _v(pp, "u_luz", tuple(np.clip(luz, 0, 1.2)))
        _v(pp, "u_auto", 0.35 + 0.65 * cfg["noche"])
        self.panel_tex.use(0)
        _v(pp, "u_tex", 0)
        self.vao_panel.render()

    @staticmethod
    def _orden(superficie):
        r, g, b, a = superficie.get_masks()
        nombres = {}
        for canal, mascara in (("R", r), ("G", g), ("B", b), ("A", a)):
            nombres[{0xff: 0, 0xff00: 1, 0xff0000: 2, 0xff000000: 3}.get(mascara, 0)] = canal
        return "".join(nombres.get(k, "A") for k in range(4))

    def subir_panel(self, superficie):
        self.panel_tex.swizzle = self._orden(superficie)
        self.panel_tex.write(superficie.get_buffer())
        self.panel_tex.build_mipmaps()

    def hud(self, superficie):
        ctx = self.ctx
        self.hud_tex.swizzle = self._orden(superficie)
        self.hud_tex.write(superficie.get_buffer())
        ctx.disable(moderngl.DEPTH_TEST)
        ctx.enable(moderngl.BLEND)
        ctx.blend_func = moderngl.SRC_ALPHA, moderngl.ONE_MINUS_SRC_ALPHA
        self.hud_tex.use(0)
        self.progs["tex2d"]["u_tex"].value = 0
        self.vao_hud.render()
        ctx.disable(moderngl.BLEND)
