import math

import moderngl
import numpy as np

COMUN = """
float hash(vec2 p){ return fract(sin(dot(p, vec2(127.1, 311.7))) * 43758.5453); }
float ruido(vec2 p){
    vec2 i = floor(p), f = fract(p);
    vec2 u = f * f * (3.0 - 2.0 * f);
    return mix(mix(hash(i), hash(i + vec2(1, 0)), u.x), mix(hash(i + vec2(0, 1)), hash(i + vec2(1, 1)), u.x), u.y);
}
vec3 niebla(vec3 c, vec3 h, float d, float k){ return mix(c, h, 1.0 - exp(-d * k)); }
"""

V_PANTALLA = """
#version 330
in vec2 in_pos;
out vec2 uv;
out vec2 ndc;
void main(){ uv = in_pos * 0.5 + 0.5; ndc = in_pos; gl_Position = vec4(in_pos, 0.0, 1.0); }
"""

F_CIELO = """
#version 330
uniform mat4 inv_vp;
uniform vec3 cam;
uniform float tiempo;
uniform vec3 luna;
uniform vec3 horizonte;
in vec2 ndc;
out vec4 o;
""" + COMUN + """
void main(){
    vec4 a = inv_vp * vec4(ndc, 1.0, 1.0);
    vec3 d = normalize(a.xyz / a.w - cam);
    float h = d.z;
    vec3 zen = vec3(0.0025, 0.0045, 0.014);
    vec3 c = mix(horizonte, zen, pow(clamp(h, 0.0, 1.0), 0.42));
    c += vec3(0.075, 0.040, 0.020) * exp(-max(h, 0.0) * 16.0);
    vec2 sph = vec2(atan(d.y, d.x), asin(clamp(d.z, -1.0, 1.0)));
    vec2 g = sph * (300.0 / 3.14159);
    vec2 cel = floor(g);
    vec2 f = fract(g) - 0.5;
    float r = hash(cel);
    if (r > 0.982 && h > 0.0) {
        vec2 off = vec2(hash(cel + 3.1), hash(cel + 7.7)) - 0.5;
        float dd = length(f - off * 0.6);
        float br = pow(hash(cel + 1.3), 5.0) * 2.8 + 0.12;
        float tw = 0.7 + 0.3 * sin(tiempo * (1.5 + 4.0 * r) + r * 50.0);
        vec3 tono = mix(vec3(0.75, 0.85, 1.0), vec3(1.0, 0.9, 0.75), hash(cel + 9.1));
        c += tono * br * tw * smoothstep(0.16, 0.0, dd) * smoothstep(0.0, 0.18, h);
    }
    float mm = dot(d, luna);
    c += vec3(1.0, 0.97, 0.9) * smoothstep(0.99965, 0.99978, mm) * 1.3;
    c += vec3(0.30, 0.32, 0.40) * pow(max(mm, 0.0), 900.0) * 0.5 + vec3(0.04, 0.05, 0.08) * pow(max(mm, 0.0), 14.0) * 0.35;
    o = vec4(c, 1.0);
}
"""

V_SUELO = """
#version 330
uniform mat4 vp;
in vec2 in_pos;
out vec3 w;
void main(){ w = vec3(in_pos, 0.0); gl_Position = vp * vec4(w, 1.0); }
"""

F_SUELO = """
#version 330
uniform vec3 cam;
uniform vec2 pad_org;
uniform float pad_paso;
uniform ivec2 pad_dim;
uniform int pad_n;
uniform vec4 luces[16];
uniform vec3 luces_c[16];
uniform vec3 horizonte;
uniform vec3 luna_c;
in vec3 w;
out vec4 o;
""" + COMUN + """
void main(){
    vec2 p = w.xy;
    float n = ruido(p * 0.07) * 0.55 + ruido(p * 0.6) * 0.3 + ruido(p * 3.0) * 0.15;
    vec3 alb = mix(vec3(0.045, 0.075, 0.040), vec3(0.075, 0.105, 0.055), n);
    vec2 lo = pad_org - vec2(7.0), hi = pad_org + vec2(pad_dim - 1) * pad_paso + vec2(7.0);
    vec2 aa = fwidth(p);
    vec2 e = smoothstep(lo - aa, lo + aa, p) * (1.0 - smoothstep(hi - aa, hi + aa, p));
    float zona = e.x * e.y;
    alb = mix(alb, vec3(0.11, 0.115, 0.12) + n * 0.02, zona);
    vec2 q = (p - pad_org) / pad_paso;
    vec2 id = floor(q + 0.5);
    vec2 fq = abs(q - id);
    float idx = id.y * float(pad_dim.x) + id.x;
    float valido = step(0.0, id.x) * step(id.x, float(pad_dim.x - 1)) * step(0.0, id.y) * step(idx, float(pad_n - 1));
    vec2 aq = fwidth(q) * 1.2;
    float cuadro = (1.0 - smoothstep(0.2 - aq.x, 0.2 + aq.x, fq.x)) * (1.0 - smoothstep(0.2 - aq.y, 0.2 + aq.y, fq.y));
    float borde = cuadro * (1.0 - (1.0 - smoothstep(0.16 - aq.x, 0.16 + aq.x, fq.x)) * (1.0 - smoothstep(0.16 - aq.y, 0.16 + aq.y, fq.y)));
    alb = mix(alb, vec3(0.20, 0.21, 0.22), cuadro * valido * zona);
    alb = mix(alb, vec3(0.55, 0.50, 0.30), borde * valido * zona);
    vec2 db = min(abs(p - lo), abs(p - hi));
    float linea = (1.0 - smoothstep(0.05, 0.05 + aa.x * 1.5, min(db.x, db.y))) * step(lo.x - 0.2, p.x) * step(p.x, hi.x + 0.2) * step(lo.y - 0.2, p.y) * step(p.y, hi.y + 0.2);
    vec3 L = luna_c;
    for (int i = 0; i < 16; i++) {
        vec3 dd = luces[i].xyz - vec3(p, 0.0);
        float d2 = dot(dd, dd) + 1.0;
        L += luces_c[i] * luces[i].w * max(dd.z, 0.4) / (d2 * sqrt(d2));
    }
    vec3 c = alb * L;
    c += vec3(0.9, 0.55, 0.15) * linea * 0.35;
    float dist = length(w - cam);
    o = vec4(niebla(c, horizonte * 0.9, dist, 0.0011), 1.0);
}
"""

V_EDIF = """
#version 330
uniform mat4 vp;
in vec3 in_pos;
in vec3 in_nrm;
in vec4 caja;
in vec3 extra;
out vec3 w;
out vec3 nrm;
out vec2 fac;
out float semilla;
out float alto;
void main(){
    float c = cos(extra.z), s = sin(extra.z);
    vec2 l = in_pos.xy * caja.zw;
    vec2 r = vec2(l.x * c - l.y * s, l.x * s + l.y * c);
    w = vec3(caja.xy + r, in_pos.z * extra.x);
    nrm = vec3(in_nrm.x * c - in_nrm.y * s, in_nrm.x * s + in_nrm.y * c, in_nrm.z);
    fac = vec2(abs(in_nrm.x) > 0.5 ? l.y : l.x, w.z);
    semilla = extra.y;
    alto = extra.x;
    gl_Position = vp * vec4(w, 1.0);
}
"""

F_EDIF = """
#version 330
uniform vec3 cam;
uniform vec3 horizonte;
in vec3 w;
in vec3 nrm;
in vec2 fac;
in float semilla;
in float alto;
out vec4 o;
""" + COMUN + """
void main(){
    vec3 base = vec3(0.010, 0.012, 0.018) * (0.8 + 0.4 * hash(vec2(semilla, 1.0)));
    vec3 c = base;
    if (abs(nrm.z) < 0.5) {
        vec2 cel = vec2(fac.x / 3.4, fac.y / 3.6);
        vec2 id = floor(cel);
        vec2 f = fract(cel);
        float r = hash(id + semilla * 17.0);
        float ven = step(0.2, f.x) * step(f.x, 0.8) * step(0.22, f.y) * step(f.y, 0.78);
        float on = step(0.76, r) * step(fac.y, alto - 2.5) * step(3.0, fac.y);
        vec3 wc = mix(vec3(1.0, 0.70, 0.40), vec3(0.70, 0.82, 1.0), step(0.9, hash(id + semilla * 3.0)));
        vec3 luz = ven * on * wc * (0.35 + 0.9 * hash(id + 1.7));
        vec3 prom = wc * 0.3 * 0.33 * 0.56 * 0.8;
        float lejos = smoothstep(0.25, 0.7, max(fwidth(cel.x), fwidth(cel.y)));
        c += mix(luz, prom * 0.75, lejos) * 0.75;
    }
    float d = length(w - cam);
    o = vec4(niebla(c, horizonte, d, 0.00075), 1.0);
}
"""

V_ARBOL = """
#version 330
uniform mat4 vp;
in vec3 in_pos;
in vec4 inst;
out vec3 w;
void main(){
    w = vec3(inst.xy + in_pos.xy * inst.z, in_pos.z * inst.w);
    gl_Position = vp * vec4(w, 1.0);
}
"""

F_ARBOL = """
#version 330
uniform vec3 cam;
uniform vec3 horizonte;
in vec3 w;
out vec4 o;
""" + COMUN + """
void main(){
    vec3 c = vec3(0.006, 0.010, 0.007) * (0.7 + 0.6 * ruido(w.xy * 0.8 + w.z));
    o = vec4(niebla(c, horizonte * 0.9, length(w - cam), 0.0011), 1.0);
}
"""

V_DRON = """
#version 330
uniform mat4 vp;
in vec3 in_pos;
in vec3 in_nrm;
in float in_emi;
in vec3 i_pos;
in vec3 i_x;
in vec3 i_y;
in vec3 i_z;
in vec4 i_luz;
out vec3 nrm;
out vec3 led;
out float emi;
void main(){
    mat3 R = mat3(i_x, i_y, i_z);
    vec3 w = i_pos + R * in_pos;
    nrm = R * in_nrm;
    led = i_luz.rgb * i_luz.a;
    emi = in_emi;
    gl_Position = vp * vec4(w, 1.0);
}
"""

F_DRON = """
#version 330
uniform vec3 luna;
in vec3 nrm;
in vec3 led;
in float emi;
out vec4 o;
void main(){
    vec3 n = normalize(nrm);
    vec3 alb = vec3(0.10, 0.105, 0.115);
    vec3 c = alb * (vec3(0.03, 0.035, 0.05) + vec3(0.25, 0.27, 0.33) * max(dot(n, luna), 0.0) + led * max(-n.z, 0.0) * 0.45 + led * 0.04);
    c = mix(c, led * 1.2 + vec3(0.02), emi);
    o = vec4(c, 1.0);
}
"""

V_LUZ = """
#version 330
uniform mat4 vp;
uniform float escala;
uniform float tam;
uniform float minpx;
uniform float maxpx;
in vec3 in_pos;
in vec3 in_col;
in float in_b;
out vec3 col;
void main(){
    vec4 c = vp * vec4(in_pos, 1.0);
    gl_Position = c;
    float px = tam * escala / max(c.w, 0.05);
    float sz = clamp(px, minpx, maxpx);
    float energia = clamp(mix(1.0, (px * px) / (sz * sz), 0.55), 0.35, 1.0);
    col = in_col * in_b * energia;
    gl_PointSize = sz * 5.0;
}
"""

F_LUZ = """
#version 330
in vec3 col;
out vec4 o;
void main(){
    float r = length(gl_PointCoord - 0.5) * 2.0;
    if (r > 1.0) discard;
    float rr = r * 5.0;
    float nucleo = exp(-rr * rr * 1.6);
    float halo = exp(-r * r * 6.0) * 0.16 + exp(-r * r * 24.0) * 0.25;
    vec3 c = col * (nucleo * 8.0 + halo * 1.6) + vec3(1.0) * nucleo * dot(col, vec3(0.33)) * 0.7;
    o = vec4(c, 1.0);
}
"""

F_ESTELA = """
#version 330
uniform sampler2D previa;
uniform sampler2D actual;
uniform float decaer;
in vec2 uv;
out vec4 o;
void main(){ o = vec4(max(texture(previa, uv).rgb * decaer, texture(actual, uv).rgb), 1.0); }
"""

F_BRILLO = """
#version 330
uniform sampler2D escena;
uniform sampler2D luces;
uniform vec2 texel;
uniform float umbral;
in vec2 uv;
out vec4 o;
void main(){
    vec3 c = vec3(0.0);
    for (int i = 0; i < 4; i++) {
        vec2 off = vec2(i % 2 == 0 ? -0.5 : 0.5, i < 2 ? -0.5 : 0.5) * texel;
        c += texture(escena, uv + off).rgb + texture(luces, uv + off).rgb;
    }
    c *= 0.25;
    float l = max(c.r, max(c.g, c.b));
    o = vec4(c * max(l - umbral, 0.0) / max(l, 1e-4), 1.0);
}
"""

F_DESENFOQUE = """
#version 330
uniform sampler2D fuente;
uniform vec2 dir;
in vec2 uv;
out vec4 o;
void main(){
    float w[5] = float[](0.227027, 0.1945946, 0.1216216, 0.054054, 0.016216);
    vec3 c = texture(fuente, uv).rgb * w[0];
    for (int i = 1; i < 5; i++) {
        c += texture(fuente, uv + dir * float(i)).rgb * w[i];
        c += texture(fuente, uv - dir * float(i)).rgb * w[i];
    }
    o = vec4(c, 1.0);
}
"""

F_FINAL = """
#version 330
uniform sampler2D escena;
uniform sampler2D luces;
uniform sampler2D b1;
uniform sampler2D b2;
uniform sampler2D b3;
uniform sampler2D hud;
uniform float exposicion;
uniform float usar_hud;
uniform float tiempo;
in vec2 uv;
out vec4 o;
vec3 aces(vec3 x){ return clamp((x * (2.51 * x + 0.03)) / (x * (2.43 * x + 0.59) + 0.14), 0.0, 1.0); }
void main(){
    vec3 c = texture(escena, uv).rgb + texture(luces, uv).rgb;
    c += texture(b1, uv).rgb * 0.55 + texture(b2, uv).rgb * 0.65 + texture(b3, uv).rgb * 0.85;
    c = aces(c * exposicion);
    c = pow(c, vec3(1.0 / 2.2));
    vec2 v = uv - 0.5;
    c *= 1.0 - dot(v, v) * 0.55;
    float g = fract(sin(dot(uv * 1000.0 + tiempo, vec2(12.9898, 78.233))) * 43758.5453);
    c += (g - 0.5) / 255.0;
    vec4 h = texture(hud, uv);
    c = mix(c, h.rgb, h.a * usar_hud);
    o = vec4(c, 1.0);
}
"""


def perspectiva(fov, asp, cerca, lejos):
    t = 1.0 / math.tan(fov / 2)
    m = np.zeros((4, 4))
    m[0, 0] = t / asp
    m[1, 1] = t
    m[2, 2] = (lejos + cerca) / (cerca - lejos)
    m[2, 3] = 2 * lejos * cerca / (cerca - lejos)
    m[3, 2] = -1
    return m


def mirar(ojo, obj, arriba=(0, 0, 1)):
    ojo, obj = np.asarray(ojo, float), np.asarray(obj, float)
    f = obj - ojo
    f /= max(np.linalg.norm(f), 1e-9)
    s = np.cross(f, arriba)
    if np.linalg.norm(s) < 1e-6:
        s = np.cross(f, (0, 1, 0))
    s /= np.linalg.norm(s)
    u = np.cross(s, f)
    m = np.eye(4)
    m[0, :3], m[1, :3], m[2, :3] = s, u, -f
    m[0, 3], m[1, 3], m[2, 3] = -s @ ojo, -u @ ojo, f @ ojo
    return m


def _f4(m):
    return np.ascontiguousarray(m.T, dtype="f4").tobytes()


def _caja(x0, x1, y0, y1, z0, z1, emi=0.0):
    v, n = [], []
    caras = [
        ((x1, y0, z0), (x1, y1, z0), (x1, y1, z1), (x1, y0, z1), (1, 0, 0)),
        ((x0, y1, z0), (x0, y0, z0), (x0, y0, z1), (x0, y1, z1), (-1, 0, 0)),
        ((x1, y1, z0), (x0, y1, z0), (x0, y1, z1), (x1, y1, z1), (0, 1, 0)),
        ((x0, y0, z0), (x1, y0, z0), (x1, y0, z1), (x0, y0, z1), (0, -1, 0)),
        ((x0, y0, z1), (x1, y0, z1), (x1, y1, z1), (x0, y1, z1), (0, 0, 1)),
        ((x0, y1, z0), (x1, y1, z0), (x1, y0, z0), (x0, y0, z0), (0, 0, -1)),
    ]
    for a, b, c, d, nn in caras:
        for p in (a, b, c, a, c, d):
            v.append((*p, *nn, emi))
    return v


def _cilindro(cx, cy, r, z0, z1, lados=10, emi=0.0):
    v = []
    for i in range(lados):
        a0, a1 = 2 * math.pi * i / lados, 2 * math.pi * (i + 1) / lados
        p0 = (cx + r * math.cos(a0), cy + r * math.sin(a0))
        p1 = (cx + r * math.cos(a1), cy + r * math.sin(a1))
        nm = ((math.cos(a0) + math.cos(a1)) / 2, (math.sin(a0) + math.sin(a1)) / 2, 0)
        for p in ((*p0, z0), (*p1, z0), (*p1, z1), (*p0, z0), (*p1, z1), (*p0, z1)):
            v.append((*p, *nm, emi))
        for z, nz in ((z1, 1), (z0, -1)):
            tri = ((cx, cy, z), (*p0, z), (*p1, z)) if nz > 0 else ((cx, cy, z), (*p1, z), (*p0, z))
            for p in tri:
                v.append((*p, 0, 0, nz, emi))
    return v


def malla_dron():
    v = []
    v += _caja(-0.07, 0.07, -0.08, 0.08, -0.03, 0.035)
    for ang in (math.pi / 4, -math.pi / 4):
        brazo = _caja(-0.30, 0.30, -0.016, 0.016, -0.012, 0.012)
        c, s = math.cos(ang), math.sin(ang)
        for p in brazo:
            x, y, z, nx, ny, nz, e = p
            v.append((x * c - y * s, x * s + y * c, z, nx * c - ny * s, nx * s + ny * c, nz, e))
    for k in range(4):
        a = math.pi / 4 + k * math.pi / 2
        cx, cy = 0.30 * math.cos(a), 0.30 * math.sin(a)
        v += _cilindro(cx, cy, 0.028, -0.01, 0.045, 8)
        v += _cilindro(cx, cy, 0.13, 0.05, 0.056, 14)
    v += _cilindro(0, 0, 0.035, -0.07, -0.03, 10, emi=1.0)
    return np.array(v, "f4")


def malla_cono(lados=9):
    v = []
    for i in range(lados):
        a0, a1 = 2 * math.pi * i / lados, 2 * math.pi * (i + 1) / lados
        v += [(math.cos(a0), math.sin(a0), 0.15), (math.cos(a1), math.sin(a1), 0.15), (0, 0, 1)]
        v += [(0.15 * math.cos(a0), 0.15 * math.sin(a0), 0), (0.15 * math.cos(a1), 0.15 * math.sin(a1), 0), (0, 0, 0.3)]
    return np.array(v, "f4")


class Render:
    def __init__(self, ctx, tam, plan):
        self.ctx = ctx
        self.plan = plan
        self.n = plan.n
        ctx.enable(moderngl.PROGRAM_POINT_SIZE)
        self.horizonte = (0.028, 0.030, 0.050)
        self.luna = np.array([-0.55, 0.70, 0.42])
        self.luna /= np.linalg.norm(self.luna)
        self.p_cielo = ctx.program(vertex_shader=V_PANTALLA, fragment_shader=F_CIELO)
        self.p_suelo = ctx.program(vertex_shader=V_SUELO, fragment_shader=F_SUELO)
        self.p_edif = ctx.program(vertex_shader=V_EDIF, fragment_shader=F_EDIF)
        self.p_arbol = ctx.program(vertex_shader=V_ARBOL, fragment_shader=F_ARBOL)
        self.p_dron = ctx.program(vertex_shader=V_DRON, fragment_shader=F_DRON)
        self.p_luz = ctx.program(vertex_shader=V_LUZ, fragment_shader=F_LUZ)
        self.p_estela = ctx.program(vertex_shader=V_PANTALLA, fragment_shader=F_ESTELA)
        self.p_brillo = ctx.program(vertex_shader=V_PANTALLA, fragment_shader=F_BRILLO)
        self.p_blur = ctx.program(vertex_shader=V_PANTALLA, fragment_shader=F_DESENFOQUE)
        self.p_final = ctx.program(vertex_shader=V_PANTALLA, fragment_shader=F_FINAL)
        tri = ctx.buffer(np.array([-1, -1, 3, -1, -1, 3], "f4").tobytes())
        self.pantalla = {p: ctx.vertex_array(p, [(tri, "2f", "in_pos")])
                         for p in (self.p_cielo, self.p_estela, self.p_brillo, self.p_blur, self.p_final)}
        L = 6000.0
        suelo = np.array([-L, -L, L, -L, L, L, -L, -L, L, L, -L, L], "f4")
        self.vao_suelo = ctx.vertex_array(self.p_suelo, [(ctx.buffer(suelo.tobytes()), "2f", "in_pos")])
        self._ciudad()
        self._arboles()
        malla = malla_dron()
        self.n_malla = len(malla)
        self.vbo_malla = ctx.buffer(malla.tobytes())
        self.vbo_inst = ctx.buffer(reserve=self.n * 16 * 4)
        self.vao_dron = ctx.vertex_array(self.p_dron, [
            (self.vbo_malla, "3f 3f 1f", "in_pos", "in_nrm", "in_emi"),
            (self.vbo_inst, "3f 3f 3f 3f 4f/i", "i_pos", "i_x", "i_y", "i_z", "i_luz")])
        self.vbo_luz = ctx.buffer(reserve=self.n * 7 * 4)
        self.vao_luz = ctx.vertex_array(self.p_luz, [(self.vbo_luz, "3f 3f 1f", "in_pos", "in_col", "in_b")])
        self._balizas()
        self.hud_tex = None
        self.tam = (0, 0)
        self.redimensionar(tam)
        self.estelas = False
        self.cuerpos = True
        self.exposicion = 1.15
        self._estela_i = 0
        self._cam_prev = None
        self.ultimo_vp = np.eye(4)

    def _ciudad(self):
        rng = np.random.default_rng(42)
        cajas, extra, tops = [], [], []
        for _ in range(520):
            ang = rng.uniform(0, 2 * math.pi)
            frente = math.sin(ang)
            radio = rng.uniform(700, 1700) if frente > -0.3 else rng.uniform(900, 2000)
            if frente < -0.3 and rng.uniform() < 0.55:
                continue
            x, y = radio * math.cos(ang), radio * math.sin(ang)
            h = float(np.clip(rng.lognormal(3.4, 0.55), 10, 140))
            if rng.uniform() < 0.04:
                h = rng.uniform(150, 240)
            w, d = rng.uniform(18, 48), rng.uniform(18, 48)
            cajas.append((x, y, w, d))
            extra.append((h, rng.uniform(0, 100), rng.uniform(0, math.pi)))
            if h > 110:
                tops.append((x, y, h + 2))
        cubo = []
        for p in _caja(-0.5, 0.5, -0.5, 0.5, 0, 1):
            cubo.append(p[:6])
        cubo = np.array(cubo, "f4")
        inst = np.hstack([np.array(cajas), np.array(extra)]).astype("f4")
        self.n_edif = len(inst)
        self.vao_edif = self.ctx.vertex_array(self.p_edif, [
            (self.ctx.buffer(cubo.tobytes()), "3f 3f", "in_pos", "in_nrm"),
            (self.ctx.buffer(inst.tobytes()), "4f 3f/i", "caja", "extra")])
        self.cumbres = np.array(tops, "f4").reshape(-1, 3)

    def _arboles(self):
        rng = np.random.default_rng(8)
        inst = []
        for _ in range(900):
            ang = rng.uniform(0, 2 * math.pi)
            r = rng.uniform(230, 420)
            if math.sin(ang) < -0.55 and rng.uniform() < 0.7:
                continue
            esc = rng.uniform(3.5, 7.5)
            inst.append((r * math.cos(ang), r * math.sin(ang), esc, esc * rng.uniform(1.8, 3.2)))
        inst = np.array(inst, "f4")
        self.n_arb = len(inst)
        cono = malla_cono()
        self.n_cono = len(cono)
        self.vao_arbol = self.ctx.vertex_array(self.p_arbol, [
            (self.ctx.buffer(cono.tobytes()), "3f", "in_pos"),
            (self.ctx.buffer(inst.tobytes()), "4f/i", "inst")])

    def _balizas(self):
        pads = self.plan.pads
        lo, hi = pads[:, :2].min(0) - 7, pads[:, :2].max(0) + 7
        pts = []
        for x in np.arange(lo[0], hi[0] + 0.1, 6.0):
            pts += [(x, lo[1], 0.25), (x, hi[1], 0.25)]
        for y in np.arange(lo[1] + 6, hi[1] - 0.1, 6.0):
            pts += [(lo[0], y, 0.25), (hi[0], y, 0.25)]
        self.perimetro = np.array(pts, "f4")
        todas = np.vstack([self.perimetro, self.cumbres]) if len(self.cumbres) else self.perimetro
        self.n_bal = len(todas)
        self.bal_pos = todas
        self.vbo_bal = self.ctx.buffer(reserve=max(self.n_bal, 1) * 7 * 4)
        self.vao_bal = self.ctx.vertex_array(self.p_luz, [(self.vbo_bal, "3f 3f 1f", "in_pos", "in_col", "in_b")])

    def redimensionar(self, tam):
        tam = (max(int(tam[0]), 64), max(int(tam[1]), 64))
        if tam == self.tam:
            return
        self.tam = tam
        ctx = self.ctx

        def tex(t, filtro=True):
            x = ctx.texture(t, 4, dtype="f2")
            x.filter = (moderngl.LINEAR, moderngl.LINEAR) if filtro else (moderngl.NEAREST, moderngl.NEAREST)
            x.repeat_x = x.repeat_y = False
            return x
        self.prof = ctx.depth_texture(tam)
        self.t_escena = tex(tam)
        self.t_luces = tex(tam)
        self.f_escena = ctx.framebuffer([self.t_escena], self.prof)
        self.f_luces = ctx.framebuffer([self.t_luces], self.prof)
        self.t_estela = [tex(tam), tex(tam)]
        self.f_estela = [ctx.framebuffer([t]) for t in self.t_estela]
        for f in self.f_estela:
            f.clear(0, 0, 0, 1)
        self.niveles = []
        w, h = tam
        for k in range(3):
            w, h = max(w // 2, 8), max(h // 2, 8)
            a, b = tex((w, h)), tex((w, h))
            self.niveles.append(((w, h), a, b, ctx.framebuffer([a]), ctx.framebuffer([b])))
        self.hud_tex = ctx.texture(tam, 4)
        self.hud_tex.filter = (moderngl.NEAREST, moderngl.NEAREST)

    def subir_hud(self, datos):
        self.hud_tex.write(datos)

    def _u(self, prog, nombre, valor):
        if nombre in prog:
            if isinstance(valor, bytes):
                prog[nombre].write(valor)
            else:
                prog[nombre].value = valor

    def _luces_suelo(self, pos, col, b):
        vivos = b > 0.02
        luces = np.zeros((16, 4), "f4")
        colores = np.zeros((16, 3), "f4")
        if not vivos.any():
            return luces, colores
        p, c, bb = pos[vivos], col[vivos], b[vivos]
        lo, hi = p[:, :2].min(0), p[:, :2].max(0) + 1e-3
        ij = np.clip(((p[:, :2] - lo) / (hi - lo) * 4).astype(int), 0, 3)
        k = ij[:, 0] * 4 + ij[:, 1]
        peso = np.bincount(k, weights=bb, minlength=16)
        for e in range(3):
            luces[:, e] = np.bincount(k, weights=p[:, e] * bb, minlength=16) / np.maximum(peso, 1e-6)
            colores[:, e] = np.bincount(k, weights=c[:, e] * bb, minlength=16) / np.maximum(peso, 1e-6)
        luces[:, 3] = peso * 2.2
        return luces, colores

    def dibujar(self, camara, pos, col, b, ejes, t, hud_visible):
        ctx = self.ctx
        w, h = self.tam
        ojo, obj, fov = camara
        V = mirar(ojo, obj)
        Pm = perspectiva(fov, w / h, 0.3, 9000.0)
        VP = Pm @ V
        self.ultimo_vp = VP
        inv = np.linalg.inv(VP)
        vp = _f4(VP)
        ojo_t = tuple(float(v) for v in ojo)
        hz = self.horizonte

        self.f_escena.use()
        ctx.viewport = (0, 0, w, h)
        self.f_escena.clear(0, 0, 0, 1, depth=1.0)
        ctx.disable(moderngl.DEPTH_TEST | moderngl.BLEND)
        self._u(self.p_cielo, "inv_vp", _f4(inv))
        self._u(self.p_cielo, "cam", ojo_t)
        self._u(self.p_cielo, "tiempo", float(t))
        self._u(self.p_cielo, "luna", tuple(self.luna))
        self._u(self.p_cielo, "horizonte", hz)
        self.pantalla[self.p_cielo].render(moderngl.TRIANGLES)

        ctx.enable(moderngl.DEPTH_TEST)
        pads = self.plan.pads
        luces, colores = self._luces_suelo(pos, col, b)
        ps = self.p_suelo
        self._u(ps, "vp", vp)
        self._u(ps, "cam", ojo_t)
        self._u(ps, "pad_org", (float(pads[:, 0].min()), float(pads[:, 1].min())))
        self._u(ps, "pad_paso", float(self.plan_paso()))
        self._u(ps, "pad_dim", (int(self.plan.cols), int(self.plan.filas)))
        self._u(ps, "pad_n", int(self.n))
        self._u(ps, "luces", luces.tobytes())
        self._u(ps, "luces_c", colores.tobytes())
        self._u(ps, "horizonte", hz)
        self._u(ps, "luna_c", (0.030, 0.034, 0.050))
        self.vao_suelo.render(moderngl.TRIANGLES)

        for p in (self.p_edif, self.p_arbol):
            self._u(p, "vp", vp)
            self._u(p, "cam", ojo_t)
            self._u(p, "horizonte", hz)
        self.vao_edif.render(moderngl.TRIANGLES, instances=self.n_edif)
        self.vao_arbol.render(moderngl.TRIANGLES, instances=self.n_arb)

        if self.cuerpos:
            inst = np.empty((self.n, 16), "f4")
            inst[:, 0:3] = pos
            inst[:, 3:6] = ejes[0]
            inst[:, 6:9] = ejes[1]
            inst[:, 9:12] = ejes[2]
            inst[:, 12:15] = col
            inst[:, 15] = b
            self.vbo_inst.write(inst.tobytes())
            self._u(self.p_dron, "vp", vp)
            self._u(self.p_dron, "luna", tuple(self.luna))
            self.vao_dron.render(moderngl.TRIANGLES, instances=self.n)

        self.f_luces.use()
        ctx.viewport = (0, 0, w, h)
        self.f_luces.clear(0, 0, 0, 1)
        self.f_luces.depth_mask = False
        ctx.enable(moderngl.BLEND)
        ctx.blend_func = moderngl.ONE, moderngl.ONE
        escala = h / (2 * math.tan(fov / 2))
        pl = self.p_luz
        self._u(pl, "vp", vp)
        self._u(pl, "escala", float(escala))
        self._u(pl, "tam", 0.09)
        self._u(pl, "minpx", 2.1 * h / 900)
        self._u(pl, "maxpx", 14.0 * h / 900)
        datos = np.empty((self.n, 7), "f4")
        datos[:, 0:3] = pos - [0, 0, 0.06]
        datos[:, 3:6] = col
        datos[:, 6] = b
        self.vbo_luz.write(datos.tobytes())
        self.vao_luz.render(moderngl.POINTS, vertices=self.n)
        if self.n_bal:
            bal = np.empty((self.n_bal, 7), "f4")
            bal[:, 0:3] = self.bal_pos
            np_ = len(self.perimetro)
            bal[:np_, 3:6] = (1.0, 0.55, 0.12)
            bal[:np_, 6] = 0.16
            parpadeo = 0.9 if (t * 0.8) % 1.0 < 0.5 else 0.05
            bal[np_:, 3:6] = (1.0, 0.08, 0.05)
            bal[np_:, 6] = parpadeo
            self.vbo_bal.write(bal.tobytes())
            self._u(pl, "tam", 0.28)
            self.vao_bal.render(moderngl.POINTS, vertices=self.n_bal)
        self.f_luces.depth_mask = True
        ctx.disable(moderngl.BLEND | moderngl.DEPTH_TEST)

        luces_tex = self.t_luces
        dirv = (np.asarray(obj, float) - np.asarray(ojo, float))
        dirv /= max(np.linalg.norm(dirv), 1e-9)
        mov = 0.0
        if self._cam_prev is not None:
            po, pd = self._cam_prev
            mov = np.linalg.norm(np.asarray(ojo, float) - po) / max(np.linalg.norm(np.asarray(obj, float) - ojo), 1.0) + np.linalg.norm(dirv - pd)
        self._cam_prev = (np.asarray(ojo, float).copy(), dirv)
        decaer = 0.955 if mov < 0.0015 else (0.8 if mov < 0.006 else 0.0)
        if self.estelas:
            a, bdst = self._estela_i, 1 - self._estela_i
            self.f_estela[bdst].use()
            ctx.viewport = (0, 0, w, h)
            self.t_estela[a].use(0)
            self.t_luces.use(1)
            self._u(self.p_estela, "previa", 0)
            self._u(self.p_estela, "actual", 1)
            self._u(self.p_estela, "decaer", decaer)
            self.pantalla[self.p_estela].render(moderngl.TRIANGLES)
            self._estela_i = bdst
            luces_tex = self.t_estela[bdst]

        fuente_a, fuente_b = self.t_escena, luces_tex
        for k, (tam, ta, tb, fa, fb) in enumerate(self.niveles):
            fa.use()
            ctx.viewport = (0, 0, *tam)
            if k == 0:
                fuente_a.use(0)
                fuente_b.use(1)
                self._u(self.p_brillo, "escena", 0)
                self._u(self.p_brillo, "luces", 1)
                self._u(self.p_brillo, "texel", (1.0 / w, 1.0 / h))
                self._u(self.p_brillo, "umbral", 0.55)
                self.pantalla[self.p_brillo].render(moderngl.TRIANGLES)
            else:
                prev = self.niveles[k - 1][1]
                prev.use(0)
                self._u(self.p_blur, "fuente", 0)
                self._u(self.p_blur, "dir", (0.0, 0.0))
                self.pantalla[self.p_blur].render(moderngl.TRIANGLES)
            for _ in range(2 if k == 0 else 1):
                fb.use()
                ctx.viewport = (0, 0, *tam)
                ta.use(0)
                self._u(self.p_blur, "fuente", 0)
                self._u(self.p_blur, "dir", (1.0 / tam[0], 0.0))
                self.pantalla[self.p_blur].render(moderngl.TRIANGLES)
                fa.use()
                ctx.viewport = (0, 0, *tam)
                tb.use(0)
                self._u(self.p_blur, "dir", (0.0, 1.0 / tam[1]))
                self.pantalla[self.p_blur].render(moderngl.TRIANGLES)

        ctx.screen.use()
        ctx.viewport = (0, 0, w, h)
        pf = self.p_final
        self.t_escena.use(0)
        luces_tex.use(1)
        for k in range(3):
            self.niveles[k][1].use(2 + k)
        self.hud_tex.use(5)
        for nombre, u in (("escena", 0), ("luces", 1), ("b1", 2), ("b2", 3), ("b3", 4), ("hud", 5)):
            self._u(pf, nombre, u)
        self._u(pf, "exposicion", float(self.exposicion))
        self._u(pf, "usar_hud", 1.0 if hud_visible else 0.0)
        self._u(pf, "tiempo", float(t % 100))
        self.pantalla[pf].render(moderngl.TRIANGLES)

    def plan_paso(self):
        p = self.plan.pads
        if self.plan.cols > 1:
            return float(p[1, 0] - p[0, 0])
        return 3.0

    def proyectar(self, p):
        q = self.ultimo_vp @ np.array([*p, 1.0])
        if q[3] <= 0:
            return None
        x = (q[0] / q[3] * 0.5 + 0.5) * self.tam[0]
        y = (1 - (q[1] / q[3] * 0.5 + 0.5)) * self.tam[1]
        return x, y
