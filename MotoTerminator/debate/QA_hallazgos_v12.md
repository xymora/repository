# QA v12 / v12b — hallazgos (agente QA, 2026-10-09)

Tests del QA: `tests/test_integracion_clima.py`, `tests/test_recorrido.py`.

## B1 (ALTA) — El salón de la fama NUNCA se escribe con la configuración por defecto
`Entrenador._evolucionar` guarda `mejor_moto.json` (misma generación) ANTES de `_guardar_campeon`.
`cargar_campeones` siembra desde ese `mejor_moto.json` (generación g, misma clave) y
`actualizar_campeones` exige `k_nuevo > clave(rival)` estrictamente para la misma generación →
devuelve `None` → no se escribe `campeones_*.json`. Resultado: el salón queda siempre con 1 entrada
(la de mejor_moto) y nunca acumula "12 campeones de distintas generaciones".
Reproducción (tmp, no toca nada del usuario):
```python
import tempfile, os, evolucion as E, config as C
C.PISTAS_POR_GENERACION = 1; C.CLIMA_AUTOMATICO = False
d = tempfile.mkdtemp(); e = E.Entrenador(4, semilla=3, dir_datos=d)
for _ in range(25): r = e.correr_generacion()
print(os.listdir(d), r.get("salon_fama"))   # sin campeones_terreno.json; salon_fama None
```
Arreglo sugerido: al sembrar, si `nuevo["generacion"]` coincide con un sembrado, reemplazarlo
(`>=`), o sembrar/escribir el archivo la primera vez antes de comparar.
Test: `test_salon_orden_tope_distintas_generaciones_y_atomico`, `test_salon_escritura_atomica_ante_fallo`.

## B2 (MEDIA) — Siembra de calles: el legado `mejor_moto_ciudad_variado.json` (gen 24) queda como "mejor"
`_sembrar_campeones("ciudad")` asigna etapa = `etapa_de("variado","mixto")` = 3 al archivo viejo
de superficie (gen 24, nivel 7) y etapa 0 a `mejor_moto_ciudad.json` (gen 967; `poblacion_ciudad.npz`
no tiene clave `etapa`). Orden (etapa, …) → `mejor_campeon("ciudad")` = generación 24.
Lectura sola del estado real: `E.cargar_campeones("ciudad")` → [gen 24 etapa 3, gen 967 etapa 0].
El Recorrido pre-evalúa (elige bien), pero el "mejor" del salón y su orden son engañosos y,
con B1, ninguna campeona nueva de etapa 0 lo superará nunca. Sugerido: a los archivos viejos
`mejor_moto_ciudad_<sup>.json` darles etapa 0 (no dominaron el plan) o excluirlos del orden por etapa.

## B3 (BAJA, contrato) — Campeones sembrados sin `llegadas_limpias`
El contrato pide {generacion, modo, etapa, nivel, aptitud, llegadas_limpias, pesos}; las entradas
sembradas sólo traen `limpias` (el `setdefault` sólo se aplica cuando se lee el archivo).
Test: `test_salon_se_siembra_desde_mejor_moto`.

## B4 (ALTA, datos del usuario) — `tests/test_software.py::TestInterfazHumo` sobrescribe el `sesion.json` REAL
`interfaz.App(raiz, entrenador=e)` llama `_recordar_sesion()` → `calles.guardar_sesion("terreno", None, None)`
sobre `<proyecto>/sesion.json`. A las 09:06:37 el sesion.json del usuario quedó como
`{"modo":"terreno",...}` sin zona ni ruta (antes: modo ciudad, Monterrey · Centro, ruta A→B
(25.685106079042512,-100.32521212981435)→(25.683290277111503,-100.3229998103575), ruta_circuito "otra").
Mis tests de GUI redirigen `calles.ARCHIVO_SESION` a tmp (verificado: mtime intacto). Arreglo:
en ese test `monkeypatch`/asignar `calles.ARCHIVO_SESION` a la carpeta temporal y vigilar
`sesion.json` en `_huella`. Hasta entonces correr la suite completa en una COPIA del proyecto.

## B5 (BAJA, pruebas) — `graficos._CIELO` cachea PhotoImage de una raíz Tk anterior
Dos `tk.Tk()` en el mismo proceso (varios tests de GUI) → `TclError: image "pyimage1" doesn't exist`
en `dibujar_cielo`. En la app real hay una sola raíz; en pruebas hay que vaciar `graficos._CIELO`
(lo hace mi fixture). Sugerido: invalidar la caché si `imagen.tk` no es el intérprete del lienzo.

## Revisión escéptica del clima (medido con las campeonas, SOLO LECTURA)
- Aquaplaning: `V_ini = 85 − 3·prof` ≥ 61 km/h (charcos ≤ 8 mm) → a 30–40 km/h factor 1.0. No hace
  imposible ninguna pista (test `test_sin_aquaplaning_a_la_velocidad_minima`).
- Piso de factibilidad: con TODOS los presets el μ mojado alcanza para cada curva a V_ESTABLE
  (test `test_toda_curva_factible_a_30_kmh_con_cualquier_clima`, niveles 1/4/8).
- Viento: peor caso (tormenta_con_rafagas, ráfaga + 3σ turbulencia + 30 km/h) ≈ 1.7 rad/s² de alabeo
  < CMG_MAX 8 (test `test_viento_peor_caso_no_supera_al_estabilizador`).
- Despejado (nombre o Clima) es bit a bit igual a `clima=None`.
- Campeona de terrenos, 12 pistas (niveles 1–8) × 3 ruidos, llegadas / limpias de 36:
  despejado 28/23 · llovizna 26/24 · lluvia 23/22 · tormenta 26/22 · granizo 22/17 · niebla 28/23 ·
  viento_cruzado 28/19 · rafagas 26/21 · tormenta_con_rafagas 26/22. Ningún preset es imposible.
- Campeona de calles (zona 20.1217,-98.7358, 12 pistas sólo ida/misma/otra × 2 ruidos, de 24):
  despejado 24 (23 limpias) · lluvia 14 (13) · viento_cruzado 24 (24) · tormenta_con_rafagas 10 (7).
  La lluvia (charcos) es la que más
  cuesta a la campeona actual (nunca entrenó mojado), pero sigue siendo factible.
- "Trampa": la red no recibe entradas nuevas; el clima es igual para toda la población (mismo
  ProcesoViento por semilla) y determinista; serie == paralelo con clima automático y manual.
  No se encontró vía de explotación.

## Puntos de control (v12b), medido
- Con/sin `PuntosControl`: aptitudes y motivos idénticos en 24 pistas (0 diferencias); Entrenador con
  PUNTOS_CONTROL True vs False → mismas aptitudes y población.
- 30/30 llegadas limpias de la campeona (niveles 1–8, con lomas/saltos) registraron TODOS los puntos;
  en calles 23/23, 13/13, 24/24, 7/7 (incluye circuitos con punto en B). Sin registros por delante del
  avance (rebobinado correcto).
- Costo: 75.6 s sin vs 75.5 s con (≈ 0 %), los haces se calculan a pedido.
- GUI: postes `tags="punto"` en el mapa del Recorrido, gotas `tags="lluvia"` con lluvia.

## Portabilidad
- No quedan `getcwd/chdir` ni rutas absolutas guardadas; `sesion.json` guarda `carpeta` relativa y
  la zona de DronEntregas se copia a `.\datos`. `expanduser` sólo en rutas que el usuario pasa por CLI.
