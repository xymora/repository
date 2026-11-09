from dataclasses import dataclass


@dataclass(frozen=True)
class Nivel:
    numero: int
    nombre: str
    descripcion: str
    filas: int
    meta: int
    basura_inicial: int = 0
    basura_cada: int = 0

    @property
    def max_piezas(self):
        return self.meta * 4 + 100


NIVELES = (
    Nivel(1, "Primeras líneas", "tablero normal: limpia 20 líneas", 20, 20),
    Nivel(2, "Constancia", "tablero normal: limpia 80 líneas sin ahogarte", 20, 80),
    Nivel(3, "Escombros", "empieza con 10 filas de basura llenas de huecos", 20, 60, basura_inicial=10),
    Nivel(4, "Techo bajo", "sólo 14 filas de alto: no hay margen para errores", 14, 120),
    Nivel(5, "Marea", "cada 14 piezas sube una fila de basura", 20, 150, basura_inicial=4, basura_cada=14),
    Nivel(6, "Pasillo", "apenas 11 filas de alto", 11, 150),
    Nivel(7, "Diluvio", "16 filas y la basura sube cada 13 piezas", 16, 200, basura_inicial=4, basura_cada=13),
    Nivel(8, "Maratón", "1000 líneas con basura cada 16 piezas", 20, 1000, basura_cada=16),
)


def nivel(numero):
    return NIVELES[max(1, min(numero, len(NIVELES))) - 1]
