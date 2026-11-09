import ctypes
import math
import os
import sys
import time

os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")

import moderngl
import numpy as np
import pygame

from grabador import Grabador

VERT_TERRENO = """
#version 330
uniform mat4 mvp;
uniform float exag;
uniform float z0;
in vec3 pos;
in vec3 nor;
in vec2 uv;
out vec2 v_uv;
out vec3 v_nor;
out float v_dist;
uniform vec3 ojo;
void main() {
    vec3 p = vec3(pos.x, pos.y, (pos.z - z0) * exag);
    gl_Position = mvp * vec4(p, 1.0);
    v_uv = uv;
    v_nor = normalize(vec3(nor.x * exag, nor.y * exag, nor.z));
    v_dist = length(p - ojo);
}
"""
FRAG_TERRENO = """
#version 330
uniform sampler2D tex;
uniform vec3 luz;
uniform float niebla;
in vec2 v_uv;
in vec3 v_nor;
in float v_dist;
out vec4 color;
void main() {
    vec3 c = texture(tex, v_uv).rgb;
    float d = max(dot(normalize(v_nor), normalize(luz)), 0.0);
    vec3 l = c * (0.42 + 0.75 * d);
    float f = clamp(v_dist * niebla, 0.0, 0.55);
    color = vec4(mix(l, vec3(0.055, 0.063, 0.078), f), 1.0);
}
"""
VERT_COLOR = """
#version 330
uniform mat4 mvp;
uniform float exag;
uniform float z0;
uniform float tam;
in vec3 pos;
in vec3 col;
out vec3 v_col;
void main() {
    gl_Position = mvp * vec4(pos.x, pos.y, (pos.z - z0) * exag, 1.0);
    gl_PointSize = tam;
    v_col = col;
}
"""
FRAG_COLOR = """
#version 330
in vec3 v_col;
out vec4 color;
void main() { color = vec4(v_col, 1.0); }
"""
VERT_HUD = """
#version 330
in vec2 pos;
in vec2 uv;
out vec2 v_uv;
void main() { gl_Position = vec4(pos, 0.0, 1.0); v_uv = uv; }
"""
FRAG_HUD = """
#version 330
uniform sampler2D tex;
in vec2 v_uv;
out vec4 color;
void main() { color = texture(tex, v_uv); }
"""

CLASES = {1: (0.6, 0.6, 0.6), 2: (0.72, 0.56, 0.38), 3: (0.55, 0.8, 0.35), 4: (0.3, 0.68, 0.25), 5: (0.12, 0.5, 0.18),
          6: (0.9, 0.35, 0.3), 7: (1.0, 0.0, 1.0)}
SEVERIDAD = {"crítica": (255, 95, 95), "alta": (255, 160, 77), "media": (245, 180, 0), "info": (138, 147, 166)}


def perspectiva(fov, asp, cerca, lejos):
    f = 1 / math.tan(fov / 2)
    m = np.zeros((4, 4), np.float32)
    m[0, 0], m[1, 1] = f / asp, f
    m[2, 2] = (lejos + cerca) / (cerca - lejos)
    m[2, 3] = 2 * lejos * cerca / (cerca - lejos)
    m[3, 2] = -1
    return m


def mirar(ojo, obj, arriba=(0, 0, 1)):
    f = obj - ojo
    f = f / np.linalg.norm(f)
    s = np.cross(f, arriba)
    s = s / max(np.linalg.norm(s), 1e-9)
    u = np.cross(s, f)
    m = np.eye(4, dtype=np.float32)
    m[0, :3], m[1, :3], m[2, :3] = s, u, -f
    m[:3, 3] = -m[:3, :3] @ ojo
    return m


class Visor:
    def __init__(self, archivo):
        d = np.load(archivo, allow_pickle=True)
        self.d = d
        try:
            ctypes.windll.user32.SetProcessDPIAware()
        except Exception:
            pass
        pygame.init()
        pygame.display.gl_set_attribute(pygame.GL_CONTEXT_MAJOR_VERSION, 3)
        pygame.display.gl_set_attribute(pygame.GL_CONTEXT_MINOR_VERSION, 3)
        pygame.display.gl_set_attribute(pygame.GL_CONTEXT_PROFILE_MASK, pygame.GL_CONTEXT_PROFILE_CORE)
        pygame.display.gl_set_attribute(pygame.GL_MULTISAMPLESAMPLES, 4)
        info = pygame.display.Info()
        self.tam = (min(1500, info.current_w - 80), min(900, info.current_h - 120))
        pygame.display.set_mode(self.tam, pygame.OPENGL | pygame.DOUBLEBUF | pygame.RESIZABLE)
        pygame.display.set_caption(f"Modelo 3D — {str(d['nombre'])}")
        self.ctx = moderngl.create_context()
        self.ctx.enable(moderngl.DEPTH_TEST | moderngl.PROGRAM_POINT_SIZE)
        self.f = pygame.font.SysFont("segoeui", 15)
        self.fb = pygame.font.SysFont("segoeuisemibold", 17)
        self.ancho = float(d["ancho"])
        self.dtm = d["dtm"].astype(np.float32)
        self.z0 = float(self.dtm.min())
        self.exag = 1.5
        self._terreno()
        self.texturas = []
        for nombre in d["capas"]:
            img = d[f"capa_{nombre}"]
            t = self.ctx.texture((img.shape[1], img.shape[0]), 3, np.ascontiguousarray(img[::-1]).tobytes())
            t.build_mipmaps()
            t.filter = (moderngl.LINEAR_MIPMAP_LINEAR, moderngl.LINEAR)
            t.anisotropy = 8.0
            self.texturas.append((str(nombre), t))
        self.capa = 0
        self.prog_c = self.ctx.program(vertex_shader=VERT_COLOR, fragment_shader=FRAG_COLOR)
        self.modo_puntos = 0
        self.ver_puntos = "px" in d.files and len(d["px"]) > 0
        self.ver_terreno = True
        self._puntos()
        self.lineas = []
        if "rutas" in d.files:
            self._lineas(d["rutas"], (0.24, 0.84, 0.96), "rutas")
        if "zonas" in d.files:
            self._lineas(d["zonas"], None, "zonas", d["zonas_color"])
        self.ver = {"rutas": True, "zonas": True, "alertas": True}
        self.alertas = list(zip(d["alertas_xyz"], d["alertas_txt"], d["alertas_sev"])) if "alertas_xyz" in d.files else []
        if self.alertas:
            pts, cols = [], []
            for (x, y, z), _, sev in self.alertas:
                c = np.array(SEVERIDAD.get(str(sev), (255, 255, 255))) / 255
                pts += [[x, y, z], [x, y, z + 60]]
                cols += [c, c]
            self._vao_lineas(np.array(pts, np.float32), np.array(cols, np.float32), "alertas", moderngl.LINES)
        self.prog_h = self.ctx.program(vertex_shader=VERT_HUD, fragment_shader=FRAG_HUD)
        q = np.array([-1, -1, 0, 0, 1, -1, 1, 0, -1, 1, 0, 1, 1, 1, 1, 1], np.float32)
        self.vao_h = self.ctx.vertex_array(self.prog_h, [(self.ctx.buffer(q.tobytes()), "2f 2f", "pos", "uv")])
        self.tex_h = None
        self.yaw, self.pitch = math.radians(-65), math.radians(42)
        self.dist = self.ancho * 0.85
        self.obj = np.array([self.ancho / 2, self.ancho / 2, float(np.median(self.dtm) - self.z0) * 0.6], np.float32)
        self.ayuda = True
        self.reloj = pygame.time.Clock()
        self.grabador = Grabador()
        self.rect_grabar = pygame.Rect(0, 0, 0, 0)
        self.aviso = ("", 0.0)
        self._tam_video = (0, 0)

    def _terreno(self):
        dtm = self.dtm
        ny, nx = dtm.shape
        res = self.ancho / nx
        xs = (np.arange(nx) + 0.5) * res
        ys = self.ancho - (np.arange(ny) + 0.5) * res
        X, Y = np.meshgrid(xs, ys)
        gy, gx = np.gradient(dtm, res)
        nor = np.dstack([-gx, gy, np.ones_like(gx)])
        nor /= np.linalg.norm(nor, axis=2, keepdims=True)
        u = (np.arange(nx) + 0.5) / nx
        v = 1 - (np.arange(ny) + 0.5) / ny
        U, V = np.meshgrid(u, v)
        datos = np.dstack([X, Y, dtm, nor, U, V]).astype(np.float32).reshape(-1, 8)
        i = np.arange(ny - 1)[:, None] * nx + np.arange(nx - 1)[None, :]
        idx = np.column_stack([i.ravel(), (i + nx).ravel(), (i + 1).ravel(), (i + 1).ravel(), (i + nx).ravel(),
                               (i + nx + 1).ravel()]).astype(np.uint32)
        self.prog_t = self.ctx.program(vertex_shader=VERT_TERRENO, fragment_shader=FRAG_TERRENO)
        self.vao_t = self.ctx.vertex_array(self.prog_t, [(self.ctx.buffer(datos.tobytes()), "3f 3f 2f", "pos", "nor", "uv")],
                                           self.ctx.buffer(idx.tobytes()))

    def _puntos(self):
        d = self.d
        self.vao_p = None
        if "px" not in d.files or not len(d["px"]):
            return
        p = np.column_stack([d["px"], d["py"], d["pz"]]).astype(np.float32)
        z = p[:, 2]
        t = (z - z.min()) / max(np.ptp(z), 1)
        paleta = np.array([[0.19, 0.21, 0.58], [0.15, 0.62, 0.75], [0.36, 0.78, 0.39], [0.95, 0.85, 0.3], [0.9, 0.35, 0.2]])
        k = t * (len(paleta) - 1)
        i = np.clip(k.astype(int), 0, len(paleta) - 2)
        f = (k - i)[:, None]
        elev = paleta[i] * (1 - f) + paleta[i + 1] * f
        clase = np.array([CLASES.get(int(c), (1, 1, 1)) for c in range(8)])[np.clip(d["pc"], 0, 7)]
        inten = d["pi"].astype(np.float32)
        inten = np.clip(inten / np.percentile(inten, 98), 0, 1)[:, None] * np.array([1, 1, 1])
        self.colores_p = [("elevación", elev), ("clase", clase), ("intensidad", inten)]
        self.buf_p = self.ctx.buffer(p.tobytes())
        self.buf_c = self.ctx.buffer(elev.astype(np.float32).tobytes())
        self.vao_p = self.ctx.vertex_array(self.prog_c, [(self.buf_p, "3f", "pos"), (self.buf_c, "3f", "col")])
        self.n_p = len(p)

    def _vao_lineas(self, pts, cols, grupo, modo=moderngl.LINE_STRIP):
        vao = self.ctx.vertex_array(self.prog_c, [(self.ctx.buffer(pts.astype(np.float32).tobytes()), "3f", "pos"),
                                                  (self.ctx.buffer(cols.astype(np.float32).tobytes()), "3f", "col")])
        self.lineas.append((grupo, vao, modo))

    def _lineas(self, lista, color, grupo, colores=None):
        for k, l in enumerate(lista):
            l = np.asarray(l, np.float32)
            if len(l) < 2:
                continue
            c = np.array(color if color is not None else colores[k], np.float32)
            self._vao_lineas(l, np.repeat(c[None], len(l), axis=0), grupo)

    def _matriz(self):
        w, h = pygame.display.get_surface().get_size()
        ojo = self.obj + self.dist * np.array([math.cos(self.pitch) * math.cos(self.yaw), math.cos(self.pitch) * math.sin(self.yaw),
                                               math.sin(self.pitch)], np.float32)
        return perspectiva(math.radians(45), w / max(h, 1), self.ancho * 0.002, self.ancho * 8) @ mirar(ojo, self.obj), ojo

    def _hud(self, mvp):
        w, h = pygame.display.get_surface().get_size()
        sup = pygame.Surface((w, h), pygame.SRCALPHA)
        if self.ver["alertas"]:
            cajas = []
            for (x, y, z), txt, sev in self.alertas:
                p = mvp @ np.array([x, y, (z + 60 - self.z0) * self.exag, 1.0], np.float32)
                if p[3] <= 0:
                    continue
                sx, sy = (p[0] / p[3] * 0.5 + 0.5) * w, (1 - (p[1] / p[3] * 0.5 + 0.5)) * h
                if not (0 <= sx < w and 0 <= sy < h):
                    continue
                col = SEVERIDAD.get(str(sev), (255, 255, 255))
                img = self.f.render(str(txt), True, (232, 235, 241))
                r = img.get_rect(midbottom=(sx, sy - 4)).inflate(14, 6)
                for _ in range(6):
                    choca = r.collidelist(cajas)
                    if choca < 0:
                        break
                    r.bottom = cajas[choca].top - 2
                cajas.append(r.copy())
                pygame.draw.rect(sup, (14, 16, 20, 225), r, border_radius=6)
                pygame.draw.rect(sup, col, r, 1, border_radius=6)
                sup.blit(img, img.get_rect(center=r.center))
        lineas = [f"{str(self.d['nombre'])} · capa: {self.texturas[self.capa][0]} · exageración ×{self.exag:.1f}"]
        if self.vao_p is not None:
            lineas.append(f"Nube LiDAR: {self.n_p:,} puntos ({self.colores_p[self.modo_puntos][0]})".replace(",", " ")
                          + ("" if self.ver_puntos else " · oculta"))
        if self.ayuda:
            lineas += ["Arrastrar: girar · clic derecho: desplazar · rueda: acercar",
                       "1–9: capa · T: terreno · P: nube · C: color de la nube · R: rutas · Z: zonas · A: alertas",
                       "E / Q: exageración vertical · F9: grabar video · F12: captura · H: ocultar ayuda · Esc: salir"]
        y = 12
        for k, t in enumerate(lineas):
            img = (self.fb if k == 0 else self.f).render(t, True, (232, 235, 241) if k == 0 else (190, 196, 210))
            caja = img.get_rect(topleft=(14, y)).inflate(16, 6)
            pygame.draw.rect(sup, (14, 16, 20, 200), caja, border_radius=6)
            sup.blit(img, (14, y))
            y += img.get_height() + 8
        self._boton_grabar(sup, w, h)
        datos = pygame.image.tobytes(sup, "RGBA", True)
        if self.tex_h is None or self.tex_h.size != (w, h):
            self.tex_h = self.ctx.texture((w, h), 4)
        self.tex_h.write(datos)
        self.ctx.disable(moderngl.DEPTH_TEST)
        self.ctx.enable(moderngl.BLEND)
        self.ctx.blend_func = moderngl.SRC_ALPHA, moderngl.ONE_MINUS_SRC_ALPHA
        self.tex_h.use(0)
        self.prog_h["tex"] = 0
        self.vao_h.render(moderngl.TRIANGLE_STRIP)
        self.ctx.disable(moderngl.BLEND)
        self.ctx.enable(moderngl.DEPTH_TEST)

    def _boton_grabar(self, sup, w, h):
        g = self.grabador
        r = pygame.Rect(w - 196, h - 52, 182, 36)
        self.rect_grabar = r
        sobre = r.collidepoint(pygame.mouse.get_pos())
        if g.grabando:
            fondo = (200, 40, 44, 235) if sobre else (176, 32, 36, 225)
            s = int(time.perf_counter() - g.inicio)
            texto = f"Stop  {s // 60:02d}:{s % 60:02d}"
        else:
            fondo = (40, 46, 60, 235) if sobre else (22, 26, 34, 215)
            texto = "Grabar pantalla"
        pygame.draw.rect(sup, fondo, r, border_radius=8)
        pygame.draw.rect(sup, (239, 83, 80, 255), r, 1, border_radius=8)
        if g.grabando:
            if int(time.perf_counter() * 2) % 2 == 0:
                pygame.draw.rect(sup, (255, 255, 255, 255), (r.x + 13, r.centery - 6, 12, 12))
        else:
            pygame.draw.circle(sup, (239, 83, 80, 255), (r.x + 19, r.centery), 7)
        img = self.fb.render(texto, True, (255, 255, 255))
        sup.blit(img, img.get_rect(midleft=(r.x + 34, r.centery)))
        txt, t0 = self.aviso
        if txt and time.perf_counter() - t0 < 4:
            img = self.f.render(txt, True, (232, 235, 241))
            caja = img.get_rect(bottomright=(r.right, r.top - 10)).inflate(16, 8)
            pygame.draw.rect(sup, (14, 16, 20, 225), caja, border_radius=6)
            pygame.draw.rect(sup, (239, 83, 80, 255), caja, 1, border_radius=6)
            sup.blit(img, img.get_rect(center=caja.center))

    def _grabar(self):
        g = self.grabador
        if g.grabando:
            g.detener()
            self.aviso = (f"Video guardado: grabaciones\\{os.path.basename(g.archivo)}", time.perf_counter())
            return
        try:
            w, h = pygame.display.get_surface().get_size()
            g.iniciar(w, h)
            self._tam_video = (w, h)
            self.aviso = ("Grabando la pantalla… (F9 o el botón para detener)", time.perf_counter())
        except Exception as ex:
            self.aviso = (f"No se pudo grabar: {ex}", time.perf_counter())

    def _cuadro_video(self):
        g = self.grabador
        if g.grabando and g.necesita_cuadro():
            w, h = pygame.display.get_surface().get_size()
            if (w, h) != self._tam_video:
                g.detener()
                self.aviso = ("Grabación detenida: cambió el tamaño de la ventana", time.perf_counter())
                return
            g.cuadro(self.ctx.screen.read(viewport=(0, 0, w, h), components=3))

    def dibujar(self):
        w, h = pygame.display.get_surface().get_size()
        self.ctx.viewport = (0, 0, w, h)
        self.ctx.clear(0.055, 0.063, 0.078)
        mvp, ojo = self._matriz()
        mt = mvp.T.copy().tobytes()
        if self.ver_terreno:
            self.prog_t["mvp"].write(mt)
            self.prog_t["exag"] = self.exag
            self.prog_t["z0"] = self.z0
            self.prog_t["ojo"] = tuple(map(float, ojo))
            self.prog_t["luz"] = (-0.5, 0.6, 0.8)
            self.prog_t["niebla"] = 0.18 / self.ancho
            self.texturas[self.capa][1].use(0)
            self.prog_t["tex"] = 0
            self.vao_t.render()
        self.prog_c["mvp"].write(mt)
        self.prog_c["exag"] = self.exag
        self.prog_c["z0"] = self.z0
        if self.vao_p is not None and self.ver_puntos:
            self.prog_c["tam"] = 2.0
            self.vao_p.render(moderngl.POINTS)
        self.prog_c["tam"] = 1.0
        for grupo, vao, modo in self.lineas:
            if self.ver.get(grupo, True):
                vao.render(modo)
        self._hud(mvp)

    def captura(self):
        w, h = pygame.display.get_surface().get_size()
        datos = self.ctx.screen.read(components=3)
        img = pygame.image.frombytes(datos, (w, h), "RGB", True)
        carpeta = os.path.join(os.path.dirname(os.path.abspath(__file__)), "exportaciones")
        os.makedirs(carpeta, exist_ok=True)
        ruta = os.path.join(carpeta, time.strftime("vista3d_%Y%m%d_%H%M%S.png"))
        pygame.image.save(img, ruta)
        return ruta

    def correr(self, capturas=None):
        arrastre = None
        cuadros = 0
        while True:
            for e in pygame.event.get():
                if e.type == pygame.QUIT or (e.type == pygame.KEYDOWN and e.key == pygame.K_ESCAPE):
                    self.grabador.detener(esperar=True)
                    pygame.quit()
                    return
                if e.type == pygame.VIDEORESIZE:
                    pygame.display.set_mode((e.w, e.h), pygame.OPENGL | pygame.DOUBLEBUF | pygame.RESIZABLE)
                if e.type == pygame.MOUSEBUTTONDOWN and e.button == 1 and self.rect_grabar.collidepoint(e.pos):
                    self._grabar()
                elif e.type == pygame.MOUSEBUTTONDOWN and e.button in (1, 3):
                    arrastre = (e.button, e.pos, self.yaw, self.pitch, self.obj.copy())
                if e.type == pygame.MOUSEBUTTONUP:
                    arrastre = None
                if e.type == pygame.MOUSEWHEEL:
                    self.dist = float(np.clip(self.dist * (0.88 if e.y > 0 else 1.14), self.ancho * 0.03, self.ancho * 4))
                if e.type == pygame.MOUSEMOTION and arrastre:
                    b, p0, y0, pt0, o0 = arrastre
                    dx, dy = e.pos[0] - p0[0], e.pos[1] - p0[1]
                    if b == 1:
                        self.yaw = y0 - dx * 0.006
                        self.pitch = float(np.clip(pt0 + dy * 0.006, math.radians(5), math.radians(89)))
                    else:
                        k = self.dist / 900
                        der = np.array([-math.sin(self.yaw), math.cos(self.yaw), 0])
                        fr = np.array([-math.cos(self.yaw), -math.sin(self.yaw), 0])
                        self.obj = (o0 - der * dx * k + fr * dy * k).astype(np.float32)
                if e.type == pygame.KEYDOWN:
                    if pygame.K_1 <= e.key <= pygame.K_9 and e.key - pygame.K_1 < len(self.texturas):
                        self.capa = e.key - pygame.K_1
                    elif e.key == pygame.K_t:
                        self.ver_terreno = not self.ver_terreno
                    elif e.key == pygame.K_p:
                        self.ver_puntos = not self.ver_puntos
                    elif e.key == pygame.K_c and self.vao_p is not None:
                        self.modo_puntos = (self.modo_puntos + 1) % len(self.colores_p)
                        self.buf_c.write(self.colores_p[self.modo_puntos][1].astype(np.float32).tobytes())
                    elif e.key == pygame.K_r:
                        self.ver["rutas"] = not self.ver["rutas"]
                    elif e.key == pygame.K_z:
                        self.ver["zonas"] = not self.ver["zonas"]
                    elif e.key == pygame.K_a:
                        self.ver["alertas"] = not self.ver["alertas"]
                    elif e.key == pygame.K_e:
                        self.exag = min(5.0, self.exag + 0.5)
                    elif e.key == pygame.K_q:
                        self.exag = max(1.0, self.exag - 0.5)
                    elif e.key == pygame.K_h:
                        self.ayuda = not self.ayuda
                    elif e.key == pygame.K_F9:
                        self._grabar()
                    elif e.key == pygame.K_F12:
                        self.captura()
            self.dibujar()
            self._cuadro_video()
            pygame.display.flip()
            cuadros += 1
            if capturas and cuadros == 3:
                carpeta = capturas
                os.makedirs(carpeta, exist_ok=True)
                for k in range(len(self.texturas)):
                    self.capa = k
                    self.ver_puntos = k == 0 and self.vao_p is not None
                    self.dibujar()
                    w, h = pygame.display.get_surface().get_size()
                    img = pygame.image.frombytes(self.ctx.screen.read(components=3), (w, h), "RGB", True)
                    pygame.image.save(img, os.path.join(carpeta, f"vista3d_{k + 1}.png"))
                pygame.quit()
                return
            self.reloj.tick(60)


def preparar(ruta, sitio, capas, dtm, nube=None, rutas=(), zonas=(), alertas=(), max_lado=640, max_puntos=1500000):
    paso = max(1, int(math.ceil(dtm.shape[0] / max_lado)))
    d = {"nombre": sitio.nombre, "ancho": sitio.ancho, "dtm": dtm[::paso, ::paso].astype(np.float32)}
    nombres = []
    from PIL import Image
    for nombre, img in capas:
        lado = min(2048, img.shape[0])
        d[f"capa_{nombre}"] = np.asarray(Image.fromarray(img).resize((lado, lado), Image.LANCZOS))
        nombres.append(nombre)
    d["capas"] = np.array(nombres)
    if nube is not None and len(nube["x"]):
        n = len(nube["x"])
        sel = np.random.default_rng(0).choice(n, min(n, max_puntos), replace=False) if n > max_puntos else slice(None)
        d.update(px=nube["x"][sel], py=nube["y"][sel], pz=nube["z"][sel], pc=nube["clase"][sel], pi=nube["i"][sel])
    if rutas:
        d["rutas"] = np.array([np.asarray(r, np.float32) for r in rutas], dtype=object)
    if zonas:
        lineas, colores = [], []
        for pts, col in zonas:
            p = np.asarray(pts + [pts[0]], dtype=float)
            q = [p[:1]]
            for a, b in zip(p[:-1], p[1:]):
                n = max(2, int(np.hypot(*(b - a)) / 8))
                q.append(a + (b - a) * np.linspace(0, 1, n)[1:, None])
            q = np.vstack(q)
            z = sitio.muestrear(dtm, q[:, 0], q[:, 1]) + 1.5
            lineas.append(np.column_stack([q, z]).astype(np.float32))
            colores.append(col)
        d["zonas"] = np.array(lineas, dtype=object)
        d["zonas_color"] = np.array(colores, np.float32)
    if alertas:
        d["alertas_xyz"] = np.array([[a["x"], a["y"], float(sitio.muestrear(dtm, a["x"], a["y"])[0])] for a in alertas], np.float32)
        d["alertas_txt"] = np.array([a["titulo"][:48] for a in alertas])
        d["alertas_sev"] = np.array([a["severidad"] for a in alertas])
    np.savez(ruta, **d)
    return ruta


def main(argv):
    ruta = argv[0]
    capturas = argv[argv.index("--capturas") + 1] if "--capturas" in argv else None
    Visor(ruta).correr(capturas)


if __name__ == "__main__":
    main(sys.argv[1:])
