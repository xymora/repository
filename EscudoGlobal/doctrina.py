import config as C


class Doctrina:
    nombre = "Doctrina del instructor"

    def __init__(self):
        self.ultima = None

    def decidir(self, ep, cands, ctx):
        filas = []
        for am, sol in cands:
            if sol is None:
                continue
            val = ep.valor_amenaza(am)
            if val <= 0:
                continue
            p = am.p_ojiva()
            if p < C.P_SENUELO and (sol["posteriores"] > 0 or p < 0.25):
                continue
            filas.append((-val * p, am.t_impacto, am, sol, val, p))
        filas.sort(key=lambda f: (f[0], f[1]))
        ordenes = []
        for _, _, am, sol, val, p in filas:
            pk, ventana, capa, post = sol["pk"], sol["ventana"], sol["capa"], sol["posteriores"]
            stock = ctx["stock"].get(capa, 0.0)
            ultima = sol.get("resto", 0.0) < C.T_REINTENTO
            uno = ep.m.get("salva", "una") != "doble"
            if am.fijada and getattr(am, "fallos", 0) > 0 and p >= C.P_SENUELO:
                ordenes.append((am, 1 if uno else (2 if ultima and stock > 0.1 else 1)))
                continue
            if post > 0 and ventana > 40 and pk < 0.85 * C.CAPAS[capa]["pk"] * am.p["pk"]:
                continue
            if capa == "exo" and post > 0 and p < 0.7 and ventana > 30:
                continue
            if stock < 0.2 and post > 0 and val < 3:
                continue
            if ep.m.get("salva", "una") == "doble":
                doble = (post == 0 or (val >= 3 and post <= 1) or am.ojivas() > 1) and stock > 0.2
            else:
                doble = False
            ordenes.append((am, 2 if doble else 1))
        return ordenes


class ControladorManual:
    nombre = "Operador humano"

    def __init__(self, apoyo=None):
        self.cola = []
        self.apoyo = apoyo
        self.ultima = None

    @property
    def automatico(self):
        return self.apoyo is not None

    def ordenar(self, ident, n):
        self.cola.append((ident, n))

    def decidir(self, ep, cands, ctx):
        por_id = {am.id: (am, sol) for am, sol in cands}
        ordenes = []
        for ident, n in self.cola:
            if ident in por_id and por_id[ident][1] is not None:
                ordenes.append((por_id[ident][0], n))
        self.cola = [(i, n) for i, n in self.cola if i not in por_id or por_id[i][1] is None]
        self.cola = [(i, n) for i, n in self.cola if any(a.id == i and a.viva for a in ep.activas)]
        if self.apoyo is not None:
            ya = {am.id for am, _ in ordenes}
            pend = {i for i, _ in self.cola}
            ordenes += [(am, n) for am, n in self.apoyo.decidir(ep, cands, ctx) if am.id not in ya and am.id not in pend]
        return ordenes
