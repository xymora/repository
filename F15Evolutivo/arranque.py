import numpy as np

from fisica import N2_IDLE, N2_ENCENDIDO

CANOPY, JFS, BOMBAS, MOTOR_D, MOTOR_I, AVIONICA, CONTROLES, RODAJE, DESPEGUE, VUELO = range(10)
PASOS = (
    ("Carlinga cerrada y asegurada", "Canopy Close & Lock", ("CANOPY",)),
    ("Arrancador JFS", "Jet Fuel Starter", ("JFS",)),
    ("Bombas de combustible", "Boost pumps / Fuel master", ("BOMBAS",)),
    ("Motor derecho a ralentí", "Right Engine Crank & Idle", ("ARR_D", "COMB_D")),
    ("Motor izquierdo a ralentí", "Left Engine Crank & Idle", ("ARR_I", "COMB_I")),
    ("Generadores, aviónica, HUD y SAS", "Generators · Avionics · SAS", ("GEN", "AVIONICA", "SAS")),
    ("Flaps y prueba de superficies", "Flaps & Flight Control Check", ("FLAPS", "CHEQUEO")),
    ("Rodaje y autorización de pista", "Taxi & Runway Clearance", ("RODAJE",)),
    ("Postquemador y rotación (Vr)", "Afterburner & Rotate", ("FRENOS", "PQ")),
    ("En vuelo", "Airborne", ()),
)
INTERRUPTORES = ("CANOPY", "JFS", "BOMBAS", "ARR_D", "COMB_D", "ARR_I", "COMB_I", "GEN", "AVIONICA", "SAS", "FLAPS",
                 "CHEQUEO", "RODAJE")
ETIQUETAS = {"CANOPY": "CARLINGA", "JFS": "JFS", "BOMBAS": "BOMBAS", "ARR_D": "ARRANQUE D", "COMB_D": "COMB D",
             "ARR_I": "ARRANQUE I", "COMB_I": "COMB I", "GEN": "GENERADORES", "AVIONICA": "AVIÓNICA/HUD",
             "SAS": "SAS 3 EJES", "FLAPS": "FLAPS", "CHEQUEO": "PRUEBA MANDOS", "RODAJE": "PEDIR RODAJE",
             "FRENOS": "SOLTAR FRENOS", "PQ": "POSTQUEMADOR"}
CHEQUEOS = (("elev", 1), ("elev", -1), ("alabeo", 1), ("alabeo", -1), ("timon", 1), ("timon", -1))
ESPERA_TORRE = 3.0
PAUSA_AUTO = 1.2


class Arranque:
    def __init__(self, n, activo):
        self.n = n
        self.activo = activo
        self.estado = np.full(n, CANOPY if activo else VUELO)
        self.cheq = np.zeros((n, len(CHEQUEOS)), bool)
        self.solicitado = np.zeros(n, bool)
        self.t_torre = np.zeros(n)
        self.autorizado = np.zeros(n, bool)
        self.vuelo = np.full(n, not activo)
        self.controles_ok = np.full(n, not activo)
        self.t_paso = np.zeros(n)
        self.t_bit = np.full(n, -1.0)

    def condiciones(self, f):
        jfs_ok = (f.jfs > 0.9) | f.encendido.all(1)
        motor = f.encendido & (f.n2 >= N2_IDLE - 0.03)
        return np.stack([f.canopy >= 0.99, jfs_ok, f.bombas, motor[:, 1], motor[:, 0],
                         f.generadores & f.avionica & f.sas, self.controles_ok, self.autorizado,
                         self.vuelo], 1)

    def interruptor(self, f, j, nombre):
        if nombre == "CANOPY":
            f.cmd_canopy[j] = 0.0 if f.cmd_canopy[j] > 0.5 else 1.0
        elif nombre == "JFS":
            f.jfs_on[j] = not f.jfs_on[j]
        elif nombre == "BOMBAS":
            f.bombas[j] = not f.bombas[j]
        elif nombre in ("ARR_D", "ARR_I"):
            k = 1 if nombre == "ARR_D" else 0
            f.arrancando[j, k] = not f.arrancando[j, k] and not f.encendido[j, k]
        elif nombre in ("COMB_D", "COMB_I"):
            k = 1 if nombre == "COMB_D" else 0
            f.valvula[j, k] = not f.valvula[j, k]
        elif nombre == "GEN":
            f.generadores[j] = not f.generadores[j]
        elif nombre == "AVIONICA":
            f.avionica[j] = not f.avionica[j]
        elif nombre == "SAS":
            f.sas[j] = not f.sas[j]
        elif nombre == "CHEQUEO":
            if self.t_bit[j] < 0:
                self.t_bit[j] = 0.0
        elif nombre == "RODAJE":
            if self.estado[j] >= RODAJE and not self.solicitado[j]:
                self.solicitado[j] = True
                self.t_torre[j] = ESPERA_TORRE

    def estado_interruptor(self, f, j, nombre):
        return {"CANOPY": f.cmd_canopy[j] > 0.5, "JFS": f.jfs_on[j], "BOMBAS": f.bombas[j],
                "ARR_D": f.arrancando[j, 1], "COMB_D": f.valvula[j, 1], "ARR_I": f.arrancando[j, 0],
                "COMB_I": f.valvula[j, 0], "GEN": f.generadores[j], "AVIONICA": f.avionica[j], "SAS": f.sas[j],
                "FLAPS": f.cmd_flaps[j] > 0.5, "CHEQUEO": bool(self.cheq[j].all()),
                "RODAJE": bool(self.autorizado[j]), "FRENOS": f.entrada["freno"][j] < 0.1,
                "PQ": f.pq[j] > 0.05}.get(nombre, False)

    def pendiente(self, f, j):
        e = int(self.estado[j])
        if e >= VUELO:
            return None
        if e == MOTOR_D:
            return "ARR_D" if f.n2[j, 1] < N2_ENCENDIDO and not f.arrancando[j, 1] else (
                "COMB_D" if not f.valvula[j, 1] else None)
        if e == MOTOR_I:
            return "ARR_I" if f.n2[j, 0] < N2_ENCENDIDO and not f.arrancando[j, 0] else (
                "COMB_I" if not f.valvula[j, 0] else None)
        for nombre in PASOS[e][2]:
            if not self.estado_interruptor(f, j, nombre):
                return nombre
        return None

    def paso(self, f, dt, mandos):
        if not self.activo:
            return
        self.t_torre = np.maximum(self.t_torre - dt, 0)
        self.autorizado |= self.solicitado & (self.t_torre <= 0)
        bit = self.t_bit >= 0
        self.t_bit = np.where(bit, self.t_bit + dt, self.t_bit)
        en_cheq = (self.estado == CONTROLES) & f.en_suelo
        for k, (eje, signo) in enumerate(CHEQUEOS):
            self.cheq[:, k] |= en_cheq & (mandos[eje] * signo > 0.85)
        self.cheq |= (self.t_bit > len(CHEQUEOS) * 0.7)[:, None]
        self.controles_ok |= (f.flaps > 0.95) & self.cheq.all(1)
        self.vuelo |= ~f.en_suelo & (f.agl() > 10) & self.autorizado
        cond = self.condiciones(f)
        nuevo = np.where(cond.all(1), VUELO, np.argmin(cond, 1))
        nuevo = np.where(self.vuelo, VUELO, nuevo)
        self.t_paso = np.where(nuevo != self.estado, 0.0, self.t_paso + dt)
        self.estado = nuevo
        f.jfs_on &= ~(f.encendido.all(1) & f.generadores)

    def barrido(self, j):
        t = self.t_bit[j]
        if t < 0:
            return None
        k = int(t / 0.7)
        if k >= len(CHEQUEOS):
            return None
        eje, signo = CHEQUEOS[k]
        frac = (t % 0.7) / 0.7
        return eje, signo * float(np.sin(np.pi * frac)) * 1.0

    def automata(self, f, sel):
        if not self.activo:
            return
        listo = sel & (self.t_paso > PAUSA_AUTO) & (self.estado < DESPEGUE)
        for j in np.flatnonzero(listo):
            e = self.estado[j]
            if e == CANOPY:
                f.cmd_canopy[j] = 1.0
            elif e == JFS:
                f.jfs_on[j] = True
            elif e == BOMBAS:
                f.bombas[j] = True
            elif e in (MOTOR_D, MOTOR_I):
                k = 1 if e == MOTOR_D else 0
                if not f.encendido[j, k]:
                    f.arrancando[j, k] = True
                    f.valvula[j, k] = f.n2[j, k] >= N2_ENCENDIDO + 0.01
            elif e == AVIONICA:
                for nombre in ("generadores", "avionica", "sas"):
                    a = getattr(f, nombre)
                    if not a[j]:
                        a[j] = True
                        self.t_paso[j] = 0.0
                        break
            elif e == CONTROLES:
                if f.flaps[j] > 0.95 and self.t_bit[j] < 0:
                    self.t_bit[j] = 0.0
            elif e == RODAJE:
                if not self.solicitado[j]:
                    self.solicitado[j] = True
                    self.t_torre[j] = ESPERA_TORRE

    def bloqueo(self):
        return self.activo & (self.estado < DESPEGUE)
