import threading
import tkinter as tk
from tkinter import ttk

import numpy as np

import config as C
import calles as K
import red as R
from terreno import Pista

SEMILLAS_PREEVALUACION = 3
TIPOS_CALLES = (("azar", "Ruta al azar"), ("ab", "Ruta A → B (elegirla en el mapa)"),
                ("misma", "Circuito A → B → A por la misma ruta"),
                ("otra", "Circuito A → B → A por otra ruta"))


def modulo_clima():
    try:
        import clima
        return clima
    except ImportError:
        return None


def presets_clima():
    m = modulo_clima()
    return [k for k in getattr(m, "PRESETS", {}) if k != "despejado"] if m else []


def texto_clima(nombre):
    if nombre in (None, "", "despejado"):
        return "Despejado"
    especiales = {"aleatorio": "Aleatorio", "automatico": "Automático"}
    if nombre in especiales:
        return especiales[nombre]
    etiquetas = getattr(modulo_clima(), "_ETIQUETAS", None) or {}
    return etiquetas.get(nombre) or str(nombre).replace("_", " ").capitalize()


def nombre_de(clima):
    return "despejado" if clima is None else str(getattr(clima, "nombre", "clima"))


def crear_clima(nombre, semilla, rng=None):
    m = modulo_clima()
    if m is None or nombre in (None, "", "despejado"):
        return None
    if nombre == "aleatorio":
        opciones = presets_clima()
        if not opciones:
            return None
        rng = rng if rng is not None else np.random.default_rng()
        nombre = opciones[int(rng.integers(len(opciones)))]
    try:
        return m.crear(nombre, int(semilla))
    except Exception:
        return None


def simulador(pista, pesos, semilla, clima=None):
    try:
        import paralelo as P
        if hasattr(P, "simulador"):
            return P.simulador(pista, pesos, semilla, clima)
    except ImportError:
        pass
    from fisica import Simulador
    return Simulador(pista, pesos, semilla_ruido=semilla)


def viento_relativo(sim, x=None):
    cl = getattr(sim, "clima", None)
    if cl is None or not (getattr(cl, "viento_medio", 0) or getattr(cl, "rafagas", 0)):
        return None
    va = getattr(sim, "viento_actual", None)
    try:
        if callable(va):
            va = va()
        vel, ang = float(va[0]), float(va[1])
    except (TypeError, ValueError, IndexError):
        vel, ang = float(cl.viento_medio), float(getattr(cl, "direccion_viento", 0.0))
    p = sim.pista
    if hasattr(p, "zona") and hasattr(p, "rumbo"):
        try:
            ang -= float(p.rumbo[p.indice(p.salida if x is None else x)])
        except (IndexError, TypeError, ValueError):
            pass
    rafaga = vel > float(cl.viento_medio) * 1.2 + 1.0
    return vel * 3.6, ang, rafaga


def puntos_de(sim):
    if sim is None:
        return None
    pc = getattr(sim, "puntos_control", None)
    if pc is not None:
        return pc
    for o in getattr(sim, "observadores", None) or ():
        o = getattr(o, "__self__", o)
        if hasattr(o, "registrados") and hasattr(o, "fallados"):
            return o
    return None


def enganchar_puntos(sim):
    pc = puntos_de(sim)
    if pc is not None:
        return pc
    try:
        import puntos_control as PC
        if not hasattr(sim, "observadores"):
            return None
        pc = PC.PuntosControl(sim.pista, semilla=getattr(sim.pista, "semilla", None))
        pc.enganchar(sim)
    except Exception:
        return None
    if getattr(sim, "puntos_control", None) is None:
        try:
            sim.puntos_control = pc
        except AttributeError:
            pass
    return pc


def lista_puntos(pc):
    for nombre in ("puntos", "lista", "pcs"):
        v = getattr(pc, nombre, None)
        if v is not None:
            return list(v)
    return []


def exitosa(pc, sim, i=0):
    if pc is None:
        return None
    try:
        import puntos_control as PC
        if hasattr(PC, "exitosas"):
            return bool(PC.exitosas(sim)[i])
    except Exception:
        pass
    try:
        from fisica import META
        return bool(sim.motivo[i] == META and np.asarray(pc.registrados)[i].all())
    except Exception:
        return None


def detalle_puntos(pc, i=0):
    if pc is None:
        return []
    try:
        reg = np.asarray(pc.registrados)[i]
        fal = np.asarray(pc.fallados)[i]
        tie = np.asarray(pc.tiempos, dtype=float)[i]
    except Exception:
        return []
    vel = None
    for nombre in ("velocidades", "vel_paso", "velocidad"):
        v = getattr(pc, nombre, None)
        if v is not None:
            try:
                vel = np.asarray(v, dtype=float)[i]
                break
            except Exception:
                vel = None
    out = []
    for k in range(len(reg)):
        estado = "ok" if reg[k] else "falló" if fal[k] else "pendiente"
        t = float(tie[k]) if np.isfinite(tie[k]) else None
        kmh = (float(vel[k]) * 3.6 if vel is not None and k < len(vel) and np.isfinite(vel[k])
               and reg[k] else None)
        out.append((k, estado, t, kmh))
    return out


def candidatos(modo, dir_datos=None):
    import evolucion as E
    n_param = R.n_parametros(C.CAPAS)
    lista, vistos = [], set()

    def agregar(pesos, datos, origen):
        try:
            p = np.asarray(pesos, dtype=float).ravel()
        except (TypeError, ValueError):
            return
        if p.size != n_param:
            return
        clave = np.round(p, 9).tobytes()
        if clave in vistos:
            return
        vistos.add(clave)
        lista.append({"pesos": p, "generacion": int(datos.get("generacion", 0) or 0),
                      "nivel": int(datos.get("nivel", 1) or 1),
                      "etapa": int(datos.get("etapa", 0) or 0),
                      "aptitud": float(datos.get("aptitud", 0.0) or 0.0),
                      "origen": datos.get("origen", origen)})

    cargar = getattr(E, "cargar_campeones", None)
    if cargar is not None:
        try:
            for c in cargar(modo, dir_datos):
                agregar(c.get("pesos"), c, "salón de la fama")
        except Exception:
            pass
    m = E.cargar_mejor(modo, dir_datos)
    if m is not None:
        agregar(m[0], m[1], "mejor_moto")
    return lista


def armar_pista(cfg, semilla):
    nivel = int(cfg["nivel"])
    if cfg["modo"] != "ciudad":
        return Pista(nivel, semilla)
    from evolucion import pista_calle
    sup = cfg.get("superficie") or "pavimento"
    tipo = cfg.get("tipo", "azar")
    if tipo == "ab":
        return pista_calle(cfg["red"], nivel, semilla, ruta=cfg["ruta"], superficie=sup)
    return pista_calle(cfg["red"], nivel, semilla, superficie=sup,
                       circuito=tipo if tipo in ("misma", "otra") else "no")


def etapa_recorrido(cfg):
    if cfg["modo"] != "ciudad":
        return 0
    try:
        from evolucion import etapa_de
        tipo = cfg.get("tipo", "azar")
        circ = (cfg.get("info") or {}).get("circuito", "no") if tipo == "ab" else (
            tipo if tipo in ("misma", "otra") else "no")
        return int(etapa_de(cfg.get("superficie") or "pavimento", circ))
    except Exception:
        return 0


def clave_resultado(r):
    return (r["limpias"], r["llegadas"], r["progreso"], r["aptitud"])


def preevaluar(cands, pista, clima, semillas, cancelado=lambda: False):
    pesos = np.stack([c["pesos"] for c in cands])
    n = len(cands)
    limpias, llegadas = np.zeros(n), np.zeros(n)
    progreso, aptitud = np.zeros(n), np.zeros(n)
    largo = max(pista.meta - pista.salida, 1e-6)
    for s in semillas:
        sim = simulador(pista, pesos, int(s), clima)
        while not sim.terminado:
            sim.correr(400)
            if cancelado():
                return None
        limpias += sim.llegadas_limpias()
        llegadas += sim.llegaron()
        progreso += sim.progreso / largo
        aptitud += sim.aptitud()
    k = len(semillas)
    res = [{"limpias": int(limpias[i]), "llegadas": int(llegadas[i]),
            "progreso": float(progreso[i] / k), "aptitud": float(aptitud[i] / k)}
           for i in range(n)]
    mejor = max(range(n), key=lambda i: clave_resultado(res[i]))
    return mejor, res


class Eleccion:

    def __init__(self, cands, pista, clima, semillas, extra=None):
        self.cands, self.pista, self.clima, self.semillas = cands, pista, clima, semillas
        self.extra = extra
        self.listo = False
        self.resultado = None
        self.datos_extra = None
        self.error = None
        self._cancelar = False
        self.hilo = threading.Thread(target=self._trabajo, daemon=True)
        self.hilo.start()

    def cancelar(self):
        self._cancelar = True

    def _trabajo(self):
        try:
            if self.extra is not None:
                try:
                    self.datos_extra = self.extra()
                except Exception:
                    self.datos_extra = None
            self.resultado = preevaluar(self.cands, self.pista, self.clima, self.semillas,
                                        lambda: self._cancelar)
        except Exception as ex:
            self.error = repr(ex)
        finally:
            self.listo = True


class DialogoRecorrido(tk.Toplevel):

    def __init__(self, app, al_cancelar=None):
        import interfaz as I
        self.I = I
        super().__init__(app.raiz, bg=I.TARJETA)
        self.app = app
        self.al_cancelar = al_cancelar
        self.title("Recorrido")
        self.transient(app.raiz)
        self.resizable(False, False)
        self.red = app.red_vial
        self.ruta_ab = None
        self._cargando = None
        T = I.TARJETA
        estilo = dict(bg=T, fg=I.TEXTO, selectcolor="#0c1118", activebackground=T,
                      activeforeground=I.TEXTO, font=(I.FUENTE, 9), anchor="w")
        self._estilo = estilo

        tk.Label(self, text="¿Qué recorrido quieres ver?", bg=T, fg=I.ORO,
                 font=(I.FUENTE, 12, "bold")).pack(anchor="w", padx=16, pady=(14, 0))
        tk.Label(self, text="Lo recorrerá la mejor moto del salón de la fama: antes se prueban "
                            "todas en ese mismo recorrido y clima.", bg=T, fg=I.TENUE,
                 font=(I.FUENTE, 8)).pack(anchor="w", padx=16, pady=(0, 8))

        self.modo = tk.StringVar(value=app.modo)
        fila = tk.Frame(self, bg=T)
        fila.pack(anchor="w", padx=16)
        for valor, texto in (("terreno", "▲  Terrenos"), ("ciudad", "◈  Calles reales")):
            tk.Radiobutton(fila, text=texto, value=valor, variable=self.modo,
                           command=self._actualizar, **dict(estilo, font=(I.FUENTE, 10, "bold"))
                           ).pack(side="left", padx=(0, 18))

        fila = tk.Frame(self, bg=T)
        fila.pack(anchor="w", padx=16, pady=(8, 0))
        tk.Label(fila, text="Nivel del recorrido:", bg=T, fg=I.TENUE,
                 font=(I.FUENTE, 9)).pack(side="left")
        nivel = (app.e.nivel if app.e is not None else 1)
        self.nivel = tk.IntVar(value=max(1, min(C.NIVEL_MAX, int(nivel))))
        tk.Spinbox(fila, from_=1, to=C.NIVEL_MAX, textvariable=self.nivel, width=4,
                   bg="#0c1118", fg=I.TEXTO, buttonbackground="#18202b", relief="flat",
                   insertbackground=I.TEXTO, font=(I.FUENTE, 10)).pack(side="left", padx=8)
        tk.Label(fila, text=f"(1 a {C.NIVEL_MAX})", bg=T, fg=I.TENUE,
                 font=(I.FUENTE, 8)).pack(side="left")

        self.marco_calles = tk.Frame(self, bg=T, highlightthickness=1, highlightbackground=I.BORDE)
        self.marco_calles.pack(fill="x", padx=16, pady=(10, 0))
        mc = self.marco_calles
        fila = tk.Frame(mc, bg=T)
        fila.pack(fill="x", padx=10, pady=(8, 0))
        self.lbl_zona = tk.Label(fila, text="", bg=T, fg=I.TEXTO, font=(I.FUENTE, 9, "bold"),
                                 anchor="w")
        self.lbl_zona.pack(side="left")
        self.b_zona = app._boton(fila, "⌖  Otra zona…", self._otra_zona, ciudad=True,
                                 expandir=False)
        self.b_zona.pack(side="right")
        tk.Label(mc, text="Ruta:", bg=T, fg=I.TENUE, font=(I.FUENTE, 9)).pack(
            anchor="w", padx=10, pady=(6, 0))
        self.tipo = tk.StringVar(value="azar")
        for valor, texto in TIPOS_CALLES:
            tk.Radiobutton(mc, text=texto, value=valor, variable=self.tipo,
                           command=self._actualizar, **estilo).pack(anchor="w", padx=16)
        fila = tk.Frame(mc, bg=T)
        fila.pack(fill="x", padx=34)
        self.b_ab = app._boton(fila, "⚑  Elegir A y B…", self._elegir_ab, ciudad=True,
                               expandir=False)
        self.lbl_ab = tk.Label(fila, text="", bg=T, fg=I.TENUE, font=(I.FUENTE, 8), anchor="w")
        self.lbl_ab.pack(side="left", padx=6)
        tk.Label(mc, text="Superficie:", bg=T, fg=I.TENUE, font=(I.FUENTE, 9)).pack(
            anchor="w", padx=10, pady=(6, 0))
        self.superficie = tk.StringVar(value=(app.e.superficie if app.e is not None and
                                              getattr(app.e, "modo", "") == "ciudad" else
                                              getattr(C, "CALLES_SUPERFICIE", "pavimento")))
        for clave, texto in K.SUPERFICIES.items():
            tk.Radiobutton(mc, text=texto, value=clave, variable=self.superficie,
                           **estilo).pack(anchor="w", padx=16)
        tk.Frame(mc, bg=T, height=6).pack()

        fila = tk.Frame(self, bg=T)
        fila.pack(fill="x", padx=16, pady=(10, 0))
        tk.Label(fila, text="Clima:", bg=T, fg=I.TENUE, font=(I.FUENTE, 9)).pack(side="left")
        self.climas = ["despejado"] + presets_clima() + ["aleatorio"]
        self.clima = tk.StringVar(value=texto_clima("despejado"))
        self.combo_clima = ttk.Combobox(fila, textvariable=self.clima, state="readonly", width=26,
                                        values=[texto_clima(c) for c in self.climas])
        self.combo_clima.pack(side="left", padx=8)
        fila = tk.Frame(self, bg=T)
        fila.pack(fill="x", padx=16, pady=(8, 0))
        tk.Label(fila, text="Repeticiones:", bg=T, fg=I.TENUE, font=(I.FUENTE, 9)).pack(side="left")
        self.repeticiones = tk.IntVar(value=3)
        tk.Spinbox(fila, from_=1, to=50, textvariable=self.repeticiones, width=4, bg="#0c1118",
                   fg=I.TEXTO, buttonbackground="#18202b", relief="flat", insertbackground=I.TEXTO,
                   font=(I.FUENTE, 10)).pack(side="left", padx=8)
        tk.Label(fila, text="(el entrenamiento queda en pausa mientras tanto)", bg=T, fg=I.TENUE,
                 font=(I.FUENTE, 8)).pack(side="left")

        self.error = tk.Label(self, text="", bg=T, fg=I.ACENTO, font=(I.FUENTE, 9), anchor="w",
                              justify="left", wraplength=420)
        self.error.pack(fill="x", padx=16, pady=(8, 0))
        fila = tk.Frame(self, bg=T)
        fila.pack(fill="x", padx=12, pady=12)
        self.b_cancelar = app._boton(fila, "Cancelar", self.cancelar)
        self.b_aceptar = app._boton(fila, "▶  Ver recorrido", self.aceptar, ciudad=True)
        self.protocol("WM_DELETE_WINDOW", self.cancelar)
        self.bind("<Escape>", lambda _: self.cancelar())
        self.bind("<Return>", lambda _: self.aceptar())
        self.vars = {"modo": self.modo, "nivel": self.nivel, "tipo": self.tipo,
                     "superficie": self.superficie, "clima": self.clima,
                     "repeticiones": self.repeticiones, "aceptar": self.b_aceptar,
                     "cancelar": self.b_cancelar, "zona": self.b_zona, "ab": self.b_ab,
                     "error": self.error}
        self._actualizar()
        try:
            self.grab_set()
        except tk.TclError:
            pass

    def _actualizar(self):
        I = self.I
        calles = self.modo.get() == "ciudad"
        estado = "normal" if calles else "disabled"
        for w in self.marco_calles.winfo_children():
            for x in (w, *w.winfo_children()):
                try:
                    x.config(state=estado)
                except tk.TclError:
                    pass
        if self._cargando:
            texto = f"Zona: cargando {self._cargando}…"
        elif self.red is not None:
            texto = f"Zona: {self.red.zona.nombre}"
        else:
            texto = "Zona: (elige una ciudad)"
        self.lbl_zona.config(text=texto, fg=I.TEXTO if calles else I.TENUE)
        self.b_ab.config(state="normal" if calles and self.tipo.get() == "ab" else "disabled")
        if self.ruta_ab is not None:
            info = self.ruta_ab[2]
            circ = info.get("circuito", "no")
            self.lbl_ab.config(text=f"{info.get('largo', 0) / 1000:.2f} km" +
                               (" · circuito" if circ in ("misma", "otra") else ""))
        else:
            self.lbl_ab.config(text="(sin ruta)")

    def _otra_zona(self):
        self.app.elegir_zona(al_elegir=self._zona_elegida)

    def _zona_elegida(self, zona):
        estado = {"red": None, "error": None}

        def trabajo():
            try:
                estado["red"] = K.RedVial(zona, avisar=lambda _: None)
            except Exception as ex:
                estado["error"] = str(ex)

        def revisar():
            if not self.winfo_exists():
                return
            if estado["red"] is None and estado["error"] is None:
                self.after(200, revisar)
                return
            self._cargando = None
            if estado["error"]:
                self.error.config(text=f"No se pudo cargar la zona: {estado['error']}")
            else:
                self.red, self.ruta_ab = estado["red"], None
                self.error.config(text="")
            self._actualizar()

        self._cargando = zona.nombre
        self.modo.set("ciudad")
        self._actualizar()
        self._hilo_zona = threading.Thread(target=trabajo, daemon=True)
        self._hilo_zona.start()
        self.after(200, revisar)

    def _elegir_ab(self):
        from planificador import Planificador
        actual = None
        if self.ruta_ab is not None:
            actual = self.ruta_ab[2]
        self.planificador = Planificador(self.app.raiz, self.red, self._ruta_elegida, actual)

    def _ruta_elegida(self, red, ruta, info):
        self.ruta_ab = (red, ruta, dict(info))
        self.red = red
        self.modo.set("ciudad")
        self.tipo.set("ab")
        self._actualizar()
        try:
            self.lift()
            self.grab_set()
        except tk.TclError:
            pass

    def configuracion(self):
        try:
            nivel = int(self.nivel.get())
            reps = int(self.repeticiones.get())
        except (tk.TclError, ValueError):
            return "Nivel y repeticiones deben ser números."
        texto = self.clima.get()
        clima = next((c for c in self.climas if texto_clima(c) == texto), "despejado")
        cfg = {"modo": self.modo.get(), "nivel": max(1, min(C.NIVEL_MAX, nivel)),
               "repeticiones": max(1, min(50, reps)), "clima": clima}
        if cfg["modo"] == "ciudad":
            if self._cargando:
                return "Espera a que termine de cargar la zona."
            tipo = self.tipo.get()
            if tipo == "ab":
                if self.ruta_ab is None:
                    return "Elige la salida A y la llegada B («Elegir A y B…»)."
                red, ruta, info = self.ruta_ab
                cfg.update(red=red, ruta=ruta, info=info)
            else:
                if self.red is None:
                    return "Elige primero una zona de calles reales («Otra zona…»)."
                cfg["red"] = self.red
            cfg.update(tipo=tipo, superficie=self.superficie.get())
        return cfg

    def aceptar(self):
        cfg = self.configuracion()
        if isinstance(cfg, str):
            self.error.config(text=cfg)
            return
        self.destroy()
        self.app.iniciar_recorrido(cfg)

    def cancelar(self):
        self.destroy()
        if self.al_cancelar is not None:
            self.al_cancelar()


def describir(cfg):
    if cfg["modo"] != "ciudad":
        return f"Terrenos · nivel {cfg['nivel']}"
    tipo = cfg.get("tipo", "azar")
    if tipo == "ab":
        circ = (cfg.get("info") or {}).get("circuito", "no")
        ruta = "tu circuito A → B → A" if circ in ("misma", "otra") else "tu ruta A → B"
    else:
        ruta = dict(TIPOS_CALLES)[tipo].lower().replace("a → b → a ", "")
    zona = cfg["red"].zona.nombre if cfg.get("red") is not None else "?"
    return f"{zona} · {ruta} · {cfg.get('superficie', 'pavimento')} · nivel {cfg['nivel']}"
