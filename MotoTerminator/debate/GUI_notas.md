# Notas del agente RECORRIDO/GUI (v12 / v12b)

## Para PORTABILIDAD (calles.py: guardar_sesion / cargar_sesion)
La GUI cambia el clima del entrenamiento SOLO vía config y luego llama a `K.guardar_sesion(...)`
(misma firma de siempre). Pido que `guardar_sesion` guarde y `cargar_sesion` restaure el clima
leyendo/escribiendo config, igual que hoy con superficie/circuito/plan:
- guardar: `datos["clima"] = C.CLIMA_MANUAL if C.CLIMA_MANUAL else ("automatico" if C.CLIMA_AUTOMATICO else "despejado")`
- cargar: "automatico" -> `C.CLIMA_AUTOMATICO, C.CLIMA_MANUAL = True, None`;
  "despejado" -> `False, None`; otro valor que esté en `clima.PRESETS` -> `False, valor`;
  sin el campo: no tocar config (queda el valor de config.py).
La GUI ya lee `C.CLIMA_AUTOMATICO / C.CLIMA_MANUAL` al arrancar (texto del botón «☁ Clima: …»).

## Para INTEGRACIÓN (main.py --recorrido)
`interfaz.ejecutar(..., recorrido=True)` (y `App(..., recorrido=True)`) abre el diálogo de
Recorrido 0.3 s después de arrancar. La firma anterior sigue igual (parámetro opcional al final).

## Lo que la GUI espera de los demás (ya verificado contra las versiones actuales)
- `sim.clima` (clima.Clima o None), `sim.viento_actual` = (m/s, rad hacia donde sopla, marco del clima).
- `sim.puntos_control` (lo deja `PuntosControl.enganchar`), con registrados/fallados/tiempos/
  velocidades (m/s)/haces/puntos. En demo/recorrido la GUI lo engancha si no viene.
- `evolucion.cargar_campeones(modo)` (lista de dicts con pesos) y `cargar_mejor(modo)`.
- `paralelo.simulador(pista, pesos, semilla, clima)` para crear simuladores con clima.
