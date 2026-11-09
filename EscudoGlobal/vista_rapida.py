import threading
import time

import numpy as np

import cerebro as B
import config as C
import misiones as MS
import mundo as M
from simulacion import Episodio

FONDO_MAPA = "#12151c"
TARJETA2 = "#1c2029"
REJILLA = "#262c39"
TEXTO = "#e8ebf1"
TENUE = "#8a93a6"
SUTIL = "#5a6275"
VERDE = "#38d39f"
ROJO = "#ff5f5f"
ACENTO = "#f5b400"
AZUL = "#5aaaff"
AMARILLO = "#ffe13c"
FUENTE = "Segoe UI"
COLOR_ACTIVO = {"buque": "#ffa04d", "exo": "#b48cff", "alta": "#3dd6f5", "terminal": "#38d39f", "radar": "#e1e1eb"}
COLOR_TIPO = {"corto": "#ffd166", "medio": "#ffa04d", "intermedio": "#ff7a59", "icbm": "#ff5f5f", "planeador": "#ff78c8"}
COLOR_CAPA = {"impulso": "#ffa04d", "exo": "#b48cff", "alta": "#3dd6f5", "baja": "#38d39f"}


def mezclar(a, b, t):
    t = min(max(t, 0.0), 1.0)
    ca = [int(a[i:i + 2], 16) for i in (1, 3, 5)]
    cb = [int(b[i:i + 2], 16) for i in (1, 3, 5)]
    return "#" + "".join(f"{round(x + (y - x) * t):02x}" for x, y in zip(ca, cb))


def mmss(t):
    t = max(0, int(t))
    return f"{t // 60:02d}:{t % 60:02d}"


class EpisodioVivo:
    def __init__(self, hilo):
        self.hilo = hilo
        self.ep = None
        self.gen = None
        self.n = None
        self.w = None
        self.rastros = {}

    def reiniciar(self):
        self.ep = None

    def avanzar(self, presupuesto=0.03):
        inst = self.hilo.instantanea
        if inst is None:
            return
        if self.ep is None or self.ep.terminado or inst[0] != self.n or (inst[3] != self.gen and self.ep.t > 900):
            n, w, sem, g, cfg = inst
            mis, extra = MS.preparar(n, cfg)
            self.ep = Episodio(mis, B.ControladorRed(w), sem, **extra)
            self.gen, self.n, self.w = g, n, w
            self.rastros = {}
        t0 = time.perf_counter()
        while not self.ep.terminado and time.perf_counter() - t0 < presupuesto:
            self.ep.paso()
        for am in self.ep.activas:
            r = self.rastros.setdefault(am.id, [])
            la, lo, _ = am.latlon(self.ep.t)
            if not r or abs(r[-1][0] - la) + abs(r[-1][1] - lo) > 0.4:
                r.append((la, lo))
                del r[:-40]
        vivos = {am.id for am in self.ep.activas}
        for i in [i for i in self.rastros if i not in vivos]:
            del self.rastros[i]


class PanelRed:
    def __init__(self, canvas, vivo, k):
        self.c = canvas
        self.vivo = vivo
        self.k = k
        self._firma = None

    def dibujar(self):
        c, k = self.c, self.k
        w, h = c.winfo_width(), c.winfo_height()
        if w < 60 or h < 60:
            return
        ep = self.vivo.ep
        pesos = self.vivo.w
        ult = getattr(ep.controlador, "ultima", None) if ep is not None else None
        firma = (id(pesos), id(ult), w, h)
        if firma == self._firma:
            return
        self._firma = firma
        c.delete("all")
        if pesos is None:
            c.create_text(w / 2, h / 2, text="La red aparece cuando empieza la primera generación", fill=SUTIL,
                          font=(FUENTE, 9))
            return
        capas = B.desempacar(np.asarray(pesos))
        x = np.zeros(B.N_ENTRADAS)
        titulo = "Sin amenazas que evaluar todavía: se muestra la red en reposo"
        if ult:
            cands, X, Y = ult
            i = int(np.argmax(Y[:, 0]))
            x = X[i]
            am, sol = cands[i]
            capa = C.CAPAS[sol["capa"]]["corto"] if sol else "sin solución"
            titulo = f"Evaluando #{am.id} {am.nombre()} · capa {capa}"
        salida, ocultas = B.activar(capas, x, con_ocultas=True)
        valores = [x] + list(ocultas) + [salida]
        tam = list(B.CAPAS)
        izq = 128 * k
        der = 128 * k
        arriba = 22 * k
        abajo = 8 * k
        xs = [izq + (w - izq - der) * i / (len(tam) - 1) for i in range(len(tam))]
        pos = []
        for i, n in enumerate(tam):
            alto = h - arriba - abajo
            paso = alto / max(n, 1)
            pos.append([(xs[i], arriba + paso * (j + 0.5)) for j in range(n)])
        c.create_text(8 * k, 4 * k, text=titulo[:90], anchor="nw", fill=ACENTO, font=(FUENTE, 8, "bold"))
        for li, (W, _) in enumerate(capas):
            mag = np.abs(W)
            tope = float(mag.max()) or 1.0
            orden = np.argsort(mag, axis=None)[-90:]
            act = np.abs(valores[li])
            for idx in orden:
                a, b = np.unravel_index(idx, W.shape)
                v = float(W[a, b])
                fuerza = abs(v) / tope * (0.35 + 0.65 * min(1.0, float(act[a])))
                col = mezclar(TARJETA2, VERDE if v > 0 else ROJO, 0.15 + 0.85 * fuerza)
                p0, p1 = pos[li][a], pos[li + 1][b]
                c.create_line(p0[0], p0[1], p1[0], p1[1], fill=col, width=max(1.0, 2.2 * fuerza * k))
        for li, n in enumerate(tam):
            r = max(2.5, min(7.0 * k, (h - arriba - abajo) / max(n, 1) * 0.36))
            for j, (px, py) in enumerate(pos[li]):
                a = float(np.clip(valores[li][j], -1.0, 1.0)) if li else float(np.tanh(valores[li][j]))
                col = mezclar(TARJETA2, VERDE if a > 0 else ROJO, abs(a))
                c.create_oval(px - r, py - r, px + r, py + r, fill=col, outline=REJILLA)
        for j, (px, py) in enumerate(pos[0]):
            c.create_text(px - 8 * k, py, text=B.NOMBRES_ENTRADAS[j], anchor="e", fill=TENUE, font=(FUENTE, 7))
        for j, (px, py) in enumerate(pos[-1]):
            v = float(salida[j])
            txt = f"{B.NOMBRES_SALIDAS[j]} {v:+.2f}"
            c.create_text(px + 10 * k, py - 6 * k, text=txt, anchor="w", fill=VERDE if v > 0 else ROJO,
                          font=(FUENTE, 8, "bold"))
            c.create_text(px + 10 * k, py + 7 * k, text=("sí" if v > 0 else "no"), anchor="w", fill=TENUE,
                          font=(FUENTE, 7))
        for i, n in enumerate(tam[1:-1], start=1):
            c.create_text(xs[i], h - 2 * k, text=f"oculta {i} · {n}", anchor="s", fill=SUTIL, font=(FUENTE, 7))


class PanelTeatro:
    def __init__(self, canvas, vivo, k):
        self.c = canvas
        self.vivo = vivo
        self.k = k
        self.mundo = None
        self._foto = None
        self._vista = None
        self._clave_fondo = None
        threading.Thread(target=self._cargar_mundo, daemon=True).start()

    def _cargar_mundo(self):
        try:
            from PIL import Image
            import geo as G
            z = 3
            n = 2 ** z
            img = Image.new("RGB", (256 * n, 256 * n), (18, 21, 28))
            for tx in range(n):
                for ty in range(n):
                    img.paste(G.tesela("base", z, tx, ty), (256 * tx, 256 * ty))
            tri = Image.new("RGB", (img.width * 3, img.height))
            for i in range(3):
                tri.paste(img, (img.width * i, 0))
            self.mundo = tri
        except Exception:
            self.mundo = None

    def _calcular_vista(self, ep, w, h):
        pts = [(z.lat, z.lon) for z in ep.zonas]
        pts += [M.centro_origen(o) for o in ep.origen_bando]
        pts += [(a.lat, a.lon) for a in ep.activos]
        if not pts:
            pts = [(20.0, 0.0)]
        ref = pts[0][1]
        lons = [M.desenvolver(lo, ref) for _, lo in pts]
        ys = [M.merc_y(la) for la, _ in pts]
        x0, x1, y0, y1 = min(lons), max(lons), min(ys), max(ys)
        cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
        ancho = max(x1 - x0, 12.0) * 1.25
        alto = max(y1 - y0, 8.0) * 1.3
        if ancho / alto > w / h:
            alto = ancho * h / w
        else:
            ancho = alto * w / h
        ancho = min(ancho, 360.0)
        alto = min(alto, 300.0)
        return (cx - ancho / 2, cx + ancho / 2, cy - alto / 2, cy + alto / 2, ref)

    def xy(self, lat, lon):
        x0, x1, y0, y1, ref = self._vista
        w, h = self._wh
        L = M.desenvolver(lon, (x0 + x1) / 2)
        return (L - x0) / (x1 - x0) * w, (y1 - M.merc_y(lat)) / (y1 - y0) * h

    def _fondo(self, w, h):
        clave = (self._vista, w, h, self.mundo is not None)
        if clave == self._clave_fondo:
            return
        self._clave_fondo = clave
        self.c.delete("fondo")
        if self.mundo is None:
            self.c.create_rectangle(0, 0, w, h, fill=FONDO_MAPA, width=0, tags="fondo")
            x0, x1, y0, y1, _ = self._vista
            for lo in range(-540, 541, 30):
                if x0 <= lo <= x1:
                    X = (lo - x0) / (x1 - x0) * w
                    self.c.create_line(X, 0, X, h, fill=REJILLA, tags="fondo")
            return
        from PIL import ImageTk
        x0, x1, y0, y1, _ = self._vista
        W = self.mundo.width / 3
        px0 = (x0 + 180) / 360 * W + W
        px1 = (x1 + 180) / 360 * W + W
        py0 = (180 - y1) / 360 * self.mundo.height
        py1 = (180 - y0) / 360 * self.mundo.height
        img = self.mundo.crop((int(px0), int(py0), int(px1), int(py1))).resize((max(w, 1), max(h, 1)))
        self._foto = ImageTk.PhotoImage(img)
        self.c.create_image(0, 0, image=self._foto, anchor="nw", tags="fondo")
        self.c.tag_lower("fondo")

    def dibujar(self):
        c, k = self.c, self.k
        w, h = c.winfo_width(), c.winfo_height()
        ep = self.vivo.ep
        c.delete("din")
        if ep is None or w < 60 or h < 60:
            if ep is None:
                c.delete("fondo")
                self._clave_fondo = None
                c.create_text(w / 2, h / 2, text="El mapa aparece cuando empieza la primera generación", fill=SUTIL,
                              font=(FUENTE, 9), tags="din")
            return
        if self._vista is None or getattr(self, "_ep_vista", None) is not ep or self._wh != (w, h):
            self._wh = (w, h)
            self._vista = self._calcular_vista(ep, w, h)
            self._ep_vista = ep
        self._fondo(w, h)
        km = w / max((self._vista[1] - self._vista[0]) * 111.0, 1.0)
        for o, b in ep.origen_bando.items():
            la0, la1, lo0, lo1 = M.ORIGENES[o]["caja"]
            p0, p1 = self.xy(la1, lo0), self.xy(la0, lo1)
            if p1[0] < p0[0]:
                p1 = (p0[0] + abs(p1[0] - p0[0]), p1[1])
            c.create_rectangle(*p0, *p1, outline=ROJO, dash=(3, 3), tags="din")
            c.create_text(p0[0] + 3, p0[1] + 2, text=M.ORIGENES[o]["nombre"], anchor="nw", fill=ROJO,
                          font=(FUENTE, 7), tags="din")
        for z in ep.zonas:
            x, y = self.xy(z.lat, z.lon)
            r = max(4.0 * k, z.r * km)
            col = VERDE if z.activa else ROJO
            c.create_oval(x - r, y - r, x + r, y + r, outline=col, width=2, tags="din")
            c.create_text(x, y + r + 2, text=z.nombre + ("" if z.activa else " · arrasada"), anchor="n", fill=col,
                          font=(FUENTE, 7), tags="din")
        for a in ep.activos:
            x, y = self.xy(a.lat, a.lon)
            col = COLOR_ACTIVO.get(a.tipo, TEXTO) if not a.destruida else SUTIL
            r = 3.5 * k
            c.create_rectangle(x - r, y - r, x + r, y + r, fill=col, outline="", tags="din")
        for la, lo, alt, te, tipo in ep.explosiones:
            edad = ep.t - te
            if 0 <= edad < 25:
                x, y = self.xy(la, lo)
                r = (5 + edad * 0.6) * k * (3 if tipo == "nuclear" else 1)
                col = {"derribo": "#fff0aa", "impacto": "#ff6e28", "nuclear": "#fffad2", "contra": AZUL}.get(tipo, TENUE)
                c.create_oval(x - r, y - r, x + r, y + r, outline=col, width=2, tags="din")
        for am in ep.activas:
            pts = self.vivo.rastros.get(am.id, [])
            col = COLOR_TIPO.get(am.tipo, TEXTO)
            if am.respuesta:
                col = AZUL
            elif not am.detectada:
                col = SUTIL
            elif am.senuelo and am.p_ojiva() < 0.25:
                col = "#9696a0"
            if len(pts) > 1:
                xy = [v for p in pts for v in self.xy(*p)]
                c.create_line(*xy, fill=mezclar(FONDO_MAPA, col, 0.6), width=1, tags="din")
            la, lo, _ = am.latlon(ep.t)
            x, y = self.xy(la, lo)
            r = 3 * k
            c.create_oval(x - r, y - r, x + r, y + r, fill=col, outline="", tags="din")
            if am.nuclear:
                c.create_oval(x - 6 * k, y - 6 * k, x + 6 * k, y + 6 * k, outline=AMARILLO, width=2, tags="din")
            if am.fijada:
                c.create_rectangle(x - 7 * k, y - 7 * k, x + 7 * k, y + 7 * k, outline=ROJO, dash=(2, 2), tags="din")
        for it in ep.interceptores:
            if not it.activo or ep.t < it.t_lanz:
                continue
            la, lo, _ = M.latlon(it.pos(ep.t))
            x, y = self.xy(la, lo)
            a0 = self.xy(it.activo_lanz.lat, it.activo_lanz.lon)
            col = COLOR_CAPA.get(it.capa, TEXTO)
            c.create_line(a0[0], a0[1], x, y, fill=mezclar(FONDO_MAPA, col, 0.5), dash=(2, 3), tags="din")
            c.create_oval(x - 2.5 * k, y - 2.5 * k, x + 2.5 * k, y + 2.5 * k, fill="#ebfaff", outline=col, tags="din")
        st = ep.st
        txt = (f"Misión {self.vivo.n}. {MS.NOMBRES[self.vivo.n - 1]} · generación {self.vivo.gen} · "
               f"reloj {mmss(ep.t)}")
        txt2 = (f"lanzados {st['lanzadas']} · derribados {st['interceptadas']} · impactos en ciudad {st['impactos_zona']} · "
                f"interceptores {st['usados']}")
        for i, t in enumerate((txt, txt2)):
            c.create_rectangle(4, 4 + i * 17 * k, 10 + len(t) * 5.6 * k, 4 + (i + 1) * 17 * k, fill=FONDO_MAPA,
                               outline="", stipple="gray75", tags="din")
            c.create_text(8, 6 + i * 17 * k, text=t, anchor="nw", fill=ACENTO if i == 0 else TEXTO,
                          font=(FUENTE, 8, "bold" if i == 0 else "normal"), tags="din")
        if ep.terminado:
            c.create_text(w / 2, h - 10 * k, text="Escenario terminado · el siguiente empieza con la generación nueva",
                          fill=TENUE, font=(FUENTE, 8), tags="din")
