# Notas de INTEGRACIÓN (para QA y demás agentes) — 2026-10-09

## Clima en el entrenamiento
- config.py: `CLIMA_AUTOMATICO = True`, `CLIMA_MANUAL = None`, `CAMPEONES_MAX = 12`, `PUNTOS_CONTROL = True`.
- Con el clima automático por defecto, cualquier test que compare contra v9/v12 bit a bit
  (tests/test_evolucion.py, test_circuito.py, test_superficies.py, test_regresion.py...) debe
  fijar `C.CLIMA_AUTOMATICO = False` y `C.CLIMA_MANUAL = None` (p. ej. en setUp / fixture, o con la
  clase `Banderas` de test_evolucion.py). Con ambos apagados: mismas motos, mismo historial y
  `evolucion.hash_config()` idéntico a v12 (las claves de clima sólo entran a la huella si el
  clima está activo; CAMPEONES_MAX y PUNTOS_CONTROL nunca).
- Los subprocesos de tests que importan el código actual en limpio (sin pasar por el config del
  proceso principal) también verían el clima: hay que apagarlo dentro del script del subproceso.
- Clima por pista: `evolucion.clima_de_pista(semilla, nivel, etapa)` → `clima.Clima` o None
  (despejado puro = None, no se pasa al Simulador). RNG propio: `default_rng([semilla, 0xC11A7E])`;
  no consume el RNG del GA. Etapa = la de la pista (repaso usa su etapa anterior; terrenos 0).
- `Entrenador.climas[i]` = nombre del clima de la pista i (interfaz); `Entrenador.climas_obj[i]` el objeto.
- paralelo: la spec lleva el `Clima` en la posición 6 (`P.con_clima(spec, clima)`); terrenos se
  rellena `(…, None, None, clima)`. `P.simulador(pista, pesos, semilla, clima)` crea el Simulador
  (sin clima: llamada idéntica a v12) y engancha los puntos de control.

## Salón de la fama
- `campeones_terreno.json` / `campeones_ciudad.json` en dir_datos (o la carpeta del proyecto).
- `evolucion.cargar_campeones(modo, dir_datos=None)` → lista (mejor primero);
  `evolucion.mejor_campeon(modo, dir_datos=None)` → dict o None. Campos: generacion, modo, etapa,
  nivel, aptitud, limpias (= llegadas_limpias), exitosas, terminadas, pistas, puntos, clima_visto, pesos.
- Orden: (etapa, nivel, limpias, exitosas, aptitud). Una por (etapa, nivel) cada 5 generaciones
  (la nueva reemplaza sólo si es mejor). Si el archivo no existe se siembra desde mejor_moto*.json
  (incluye mejor_moto_ciudad_<superficie>.json viejos) sin escribir hasta la siguiente generación.

## Puntos de control (v12b)
- Si existe puntos_control.py y fisica.Simulador tiene `observadores`: cada Simulador de
  entrenamiento/validación lleva `sim.puntos_control`. Resumen: `puntos_lider` ("k/K"),
  `exitosas_pct`, `exitosas_lider`; historial.csv agrega `puntos_lider`, `exitosas_pct` al final.
  La aptitud no cambia.

## main.py
- `--clima PRESET` (o `auto`) y `--recorrido` (interfaz.ejecutar(recorrido=True) si existe; si no, demo).

## Portabilidad (pedido de PORTABILIDAD_pendientes.md) — hecho
- `evolucion.carpeta_datos(dir_datos)`: None → carpeta del proyecto; relativa → relativa a la
  carpeta del proyecto (nunca al cwd). La usan ruta(), ruta_campeones(), la siembra del salón y
  Entrenador.__init__ (self.dir_datos queda normalizado). main.py: `en_proyecto()` para --dir-datos
  (entrenador, --evaluar, --comparar, --experimento).
