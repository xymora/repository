# Portabilidad: pendientes en archivos de otros agentes (2026-10-09)

Agente PORTABILIDAD no edita estos archivos. Todo lo demás (calles.py, evaluacion.py,
experimentos.py, reporte*.py, validacion_fisica.py, bench.py, falsificador.py, sensores.py,
Iniciar_Simulador.bat) ya resuelve las rutas contra la carpeta del proyecto (AQUI), no contra el cwd.

Regla: una ruta RELATIVA que da el usuario (p. ej. `--dir-datos resultados/mi_corrida`) se toma
relativa a la carpeta del proyecto, nunca al cwd. Helper ya disponible: `evaluacion.en_proyecto(ruta)`
(o el equivalente local `os.path.join(AQUI, ruta)` si no es absoluta).

## main.py (dueño: INTEGRACIÓN)
- L135 `kw["dir_datos"] = os.path.abspath(dir_datos)` -> resuelve contra el cwd. Cambiar a
  `os.path.join(AQUI, dir_datos)` si no es absoluta (AQUI = carpeta de main.py).
- L190 `archivo = os.path.join(os.path.abspath(a.dir_datos), nombre)` -> igual que L135.
- L208 `a.dir_datos or os.path.join(X.AQUI, "resultados", ...)` -> ya funciona: experimentos.comparar
  resuelve `salida` relativa contra AQUI (cambio hecho en experimentos.py); opcional resolverlo aquí.

## evolucion.py (dueño: INTEGRACIÓN)
- L66 `ruta()`: `os.path.join(dir_datos or AQUI, nombre)` -> con un dir_datos relativo escribe
  relativo al cwd. Usar `os.path.join(AQUI, dir_datos)` cuando no sea absoluto.
- L223 (campeones iniciales) `carpeta = dir_datos or AQUI` y `ruta_campeones()` (~L201): mismo caso.
- L386 `os.makedirs(dir_datos, exist_ok=True)` en `Entrenador.__init__`: mismo caso (mejor normalizar
  `self.dir_datos` una vez al inicio).
Con el dir_datos por defecto (None) todo ya queda dentro de la carpeta: verificado por
tests/test_portabilidad.py.
