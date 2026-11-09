# Contrato v12b: puntos de control con apuntadores láser (2026-10-09)

Pedido del usuario: puntos de control colocados AL AZAR en la ruta, circuito, terreno, etc. La moto
lleva apuntadores láser que lanzan haces de luz a cada punto de control; el ÚNICO fin es REGISTRAR
correctamente cuándo pasó por cada uno, para saber si la moto pasó de manera exitosa.
NO cambia la aptitud de entrenamiento (decisión del usuario intacta) ni las entradas de la red (35).

## puntos_control.py (dueño: agente PUNTOS DE CONTROL)
```python
class PuntoControl:   # x (m a lo largo de la pista), lado (+1 izq / -1 der), lateral (m desde el
                      # centro del camino), altura del reflector, indice, es_b (True si es el punto B
                      # de un circuito)
class PuntosControl:
    def __init__(self, pista, semilla=None, n=None)   # coloca K puntos al azar (RNG PROPIO derivado de
        # la semilla de la pista: NO consume el RNG de la pista -> pistas bit a bit iguales), uno cada
        # ~60–150 m (mínimo 3), nunca dentro de salida/meta, en circuitos siempre uno en x_b
    def enganchar(self, sim)                          # se registra como observador del Simulador
    def observar(self, sim)                           # llamado después de cada paso de control
    # Láser: la moto lleva 3 apuntadores (adelante-izquierda, adelante-derecha, frontal) con alcance
    # ~30 m y cono de ±35°. Un punto queda "fijado" cuando está en alcance, dentro de un cono y con
    # línea de vista (el perfil de alturas del terreno no tapa el haz). Se REGISTRA cuando la moto
    # cruza x del punto con el haz fijado, en pie (|phi| < 60°, sin caída) y dentro del camino; se
    # guarda t, velocidad, lateral, inclinación. Si cruza sin cumplir, ese punto queda FALLADO.
    # Orden obligatorio: saltarse uno lo marca fallado.
    registrados   # bool (n_total, K)
    fallados      # bool (n_total, K)
    tiempos       # float (n_total, K), NaN si no
    haces         # para dibujar: lista [(id_moto, k, intensidad)] de los haces activos este paso
    def resumen(self) -> dict    # por moto: pasados, total, exitosa (llegó + todos en orden), detalles
def exitosas(sim) -> bool(n_total)   # llegó a la meta Y registró todos los puntos en orden
```

## fisica.py (dueño: agente CLIMA, cambio mínimo)
- `Simulador.observadores = []` y, al final de cada `paso()` (y tras un regreso de 2 s), llamar
  `for o in self.observadores: o(self)`. Con la lista vacía, BIT A BIT igual.
- Tras un regreso de 2 s (rebobinado), el observador debe poder deshacer registros posteriores al
  instante restaurado: pasar `self._ultimo_regreso` = (ids, t_restaurado) o llamar
  `o.al_regresar(self, ids, t)` si el observador tiene ese método.

## evolucion.py / paralelo.py (dueño: agente INTEGRACIÓN)
- Cada Simulador de entrenamiento y validación lleva PuntosControl (config `PUNTOS_CONTROL = True`).
- historial.csv: columnas nuevas al final `puntos_lider` ("k/K") y `exitosas_pct` (% de motos con
  recorrido exitoso). Resumen de la generación incluye esos datos. La aptitud NO cambia.
- Salón de la fama: guardar `exitosas` del campeón; el orden puede usarlo como desempate.

## interfaz.py / recorrido.py / graficos.py (dueño: agente RECORRIDO/GUI)
- Dibujar postes/balizas de los puntos (vista lateral y mapa), haces láser (líneas rojas/verdes
  finas desde la moto al reflector cuando están fijados), punto en verde al registrarse / rojo si se
  falló; panel: "Puntos de control k/K" de la líder; Recorrido: lista de puntos con tiempo y
  velocidad de paso y "RECORRIDO EXITOSO" sólo si exitosa.

## evaluacion.py (dueño: agente PORTABILIDAD)
- Métrica `exitosa` además de llegada limpia (episodios CSV: columna `puntos` y `exitosa`).

## tests (agente PUNTOS DE CONTROL: tests/test_puntos_control.py; QA revisa todo)
