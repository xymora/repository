# Contrato v12: clima, portabilidad y "Recorrido" (2026-10-09)

Pedido del usuario:
1. Clima durante los trayectos: lluvia de distintos tipos, ráfagas de viento, etc. A ELEGIR y
   también AUTOMÁTICO en el entrenamiento (terrenos, circuitos y calles reales) sin que él lo ponga.
2. Portabilidad: puede copiar la carpeta a otra máquina; TODO se guarda y se lee DENTRO de la
   carpeta del proyecto sin importar su ubicación (nada de rutas absolutas guardadas, nada fuera).
3. "Demo" → "Recorrido": el usuario elige qué hacer (terreno/nivel, calles/zona/ruta A→B/circuito,
   superficie, clima) y ve ese recorrido con el MEJOR individuo de la MEJOR generación.

Reglas para TODOS: el usuario puede tener el simulador ABIERTO entrenando: NO escribir en
mejor_moto*.json, poblacion*.npz, historial*.csv, sesion.json, campeones*.json reales (usar copias
en el scratchpad). Nunca bajar la generación ni romper los checkpoints actuales (gen 967+ en calles,
74 en terrenos). Sin entrenamientos largos, sin capturas de pantalla, sin documentos: código + tests.
La red sigue siendo 35-20-3 (NO cambiar entradas/salidas: invalidaría los pesos).
Respaldo previo: ..\MotoTerminator_respaldo_v12_2026-10-09.

## clima.py + gancho en fisica.py (dueño: agente CLIMA)
```python
PRESETS = {"despejado", "llovizna", "lluvia", "tormenta", "granizo", "niebla",
           "viento_cruzado", "rafagas", "tormenta_con_rafagas", ...}   # dict nombre -> parámetros
class Clima:      # dataclass: lluvia (0..1), granizo (bool), niebla (0..1), viento_medio (m/s),
                  # direccion_viento (rad, relativo al camino o absoluto en calles), rafagas (0..1),
                  # charcos (0..1), semilla; .nombre, .descripcion()
def crear(nombre_o_clima, semilla) -> Clima
def clima_aleatorio(rng, nivel, etapa=0) -> Clima        # para entrenamiento automático
def preparar_pista(pista, clima) -> pista_mojada         # COPIA superficial con mu, mu_min, rr, rugo
                                                         # modificados (asfalto mojado, charcos con
                                                         # aquaplaning, lodo, granizo); no muta la original
```
- Simulador(pista, pesos, ..., clima=None): con None BIT A BIT igual. Con clima: viento racheado
  (proceso tipo Ornstein-Uhlenbeck/Dryden determinista por semilla, IGUAL para todas las motos) que
  empuja lateralmente (afecta lat/psi/phi) y longitudinalmente (arrastre aparente), lluvia que reduce
  agarre (vía preparar_pista), niebla/lluvia que degradan sensores (ruido extra en observaciones,
  componiéndose con filtro_obs). Atributo sim.clima y sim.viento_actual (para dibujar).
- La red NO recibe entradas nuevas: percibe el clima por sus efectos (agarre por delante ya es entrada).

## evolucion.py, paralelo.py, config.py, main.py (dueño: agente INTEGRACIÓN)
- config: CLIMA_AUTOMATICO = True (entrenamiento con clima aleatorio por pista, determinista por
  semilla de pista, probabilidad e intensidad crecientes con nivel/etapa; ~30 % de pistas despejadas
  siempre); CLIMA_MANUAL = None | nombre de preset (fija el clima de todas las pistas).
- La spec de pista para paralelo incluye el clima (resultado serie == paralelo).
- SALÓN DE LA FAMA: campeones_terreno.json / campeones_ciudad.json dentro de la carpeta del proyecto
  (o dir_datos): hasta 12 campeones de distintas generaciones con {generacion, modo, etapa, nivel,
  aptitud, llegadas_limpias, pesos}; orden de "mejor": (etapa, nivel, limpias, aptitud). Se actualiza
  al guardar cada generación (escritura atómica). API: evolucion.cargar_campeones(modo) -> lista,
  evolucion.mejor_campeon(modo) -> dict. Si no existe el archivo, se siembra con mejor_moto*.json.
- main.py: --clima PRESET (manual), --recorrido (abre directo el diálogo de recorrido).
- Con CLIMA_AUTOMATICO=False y CLIMA_MANUAL=None: comportamiento bit a bit igual a v12.

## Portabilidad (dueño: agente PORTABILIDAD): calles.py, evaluacion.py, experimentos.py,
##   reporte*.py, validacion_fisica.py, bench.py, falsificador.py, sensores.py, Iniciar_Simulador.bat
- Todo lo que se descarga/guarda va bajo la carpeta del proyecto (AQUI = carpeta de calles.py).
- Si una zona sólo existe en ..\DronEntregas\datos, se COPIA a .\datos la primera vez y desde
  entonces se usa la copia local (misma clave/tamaño de zona: el entrenamiento no cambia).
- sesion.json guarda rutas RELATIVAS a la carpeta (o ninguna ruta: se resuelve por clave de zona).
- Ningún uso de cwd: todo relativo a AQUI. El .bat debe hacer cd a su propia carpeta (%~dp0).
- Test: copiar el proyecto (código + datos) a una carpeta temporal con otro nombre/ubicación y sin
  DronEntregas al lado, abrir sesión/zona/entrenador y comprobar que todo se lee y escribe ahí.

## interfaz.py, planificador.py, graficos.py, recorrido.py nuevo (dueño: agente RECORRIDO/GUI)
- Botón "▶ Ver demo" pasa a "▶ Recorrido": diálogo para elegir modo (terrenos: nivel; calles:
  zona actual o nueva, ruta al azar / ruta A→B (planificador) / circuito misma u otra; superficie
  pavimento/irregular/variado; nivel), CLIMA (presets) y repeticiones. Al aceptar: toma candidatos del
  salón de la fama + mejor_moto*, los PRE-EVALÚA sin animación en ese recorrido (pocas semillas de
  ruido, rápido) y anima al mejor, mostrando "Generación N · nivel · etapa". Al terminar ofrece repetir
  u otro recorrido. No toca el entrenamiento (pausa y lo reanuda al salir).
- Selector de clima en la ventana ⌖ Zona y en la barra superior: "Clima: Automático / <preset>".
- Visual: gotas de lluvia/granizo, niebla (velo), indicador de viento (flecha + km/h), piso mojado
  más oscuro/charcos, en la vista lateral, mapa y panel. Sin capturas de pantalla para probar.

## tests/ (dueño: agente QA): tests/test_clima.py, tests/test_portabilidad.py, tests/test_recorrido.py
