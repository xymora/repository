import config as C


class Doctrina:
    nombre = "Doctrina del instructor"

    def __init__(self):
        self.ultima = None

    def decidir(self, ep, cands, ctx):
        ordenes = []
        filas = []
        for am, sol in cands:
            if sol is None:
                continue
            bx, by = am.impacto_est()
            val_imp = ep.valor_en(bx, by, am.sigma() * 0.6)
            val = val_imp
            if val_imp <= 0:
                val = ep.valor_ruta(am) or (1.0 if am.fijada else 0.0)
            if val > 0:
                filas.append((val_imp <= 0, am.t_impacto, am, sol, val, val_imp))
        filas.sort(key=lambda f: (f[0], f[1]))
        for _, _, am, sol, val, val_imp in filas:
            _, p, ventana, pk = sol
            if pk < 0.8 * am.p["pk"] and ventana > 3.0:
                continue
            doble = val_imp > 0 and (val >= 3 or pk < 0.7 or am.tipo == "mortero" or ventana < 3.0) and ctx["stock"] > 0.3
            doble = doble or (val_imp <= 0 and am.disparos > 0 and ventana < 6.0 and ctx["stock"] > 0.15)
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
