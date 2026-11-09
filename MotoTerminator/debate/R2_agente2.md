# R2 — Agente 2 (aprendizaje automático / neuroevolución): réplica

## (a) Coincidencias

- **Agente 3**:
  - **Pruebas doradas y de determinismo antes de tocar nada.** Comprobó que evaluar una moto sola o en lote da la misma aptitud (diferencia de 0.0). Eso confirma mi propuesta: **repartir por pista** con procesos da resultados idénticos a la versión en serie, y repartir por moto empeora el tiempo por el costo fijo de cada paso.
  - **Checkpoint v2 atómico.** Además de la sigma, debe guardar `racha` y el estado del RNG. Esto arregla mi D1, donde la sigma se pierde al reanudar.
- **Agente 4**:
  - **Contar aparte las llegadas limpias** (`reintentos == 0`). Hoy `evolucion.py:172` y `:213` las mezclan con las corregidas.
  - **Suite de pistas reservadas** con semillas disjuntas, evaluada con `MAX_REINTENTOS = 0`, réplicas de ruido por moto e IC de Clopper-Pearson o Wilson.
  - Los tres (A3, A4 y yo) llegamos por separado al mismo diagnóstico: la aptitud guardada es el máximo de 80 medias ruidosas (maldición del ganador). Hay consenso.
- **Agente 1**:
  - **P0, validación física**, y **P8, ruido escalado con √dt**: el resultado no cambia con los valores actuales.
  - **P2, mitigación del levantamiento trasero.** Hace la tarea más fácil y no invalida pesos. Es aceptable hoy si va con un flag y una regresión antes y después.
- **Agente 5**: el reposicionamiento como "banco de controladores" exige justo lo que propuse: una interfaz `Controlador` enchufable y un baseline PD/LQR. El Agente 3 (Fase 2, `paso(ctrl=None)`) llega a lo mismo por otro camino.

## (b) Objeciones técnicas

**1. Agente 4: castigo de 50 por error y premio de rapidez solo en llegadas limpias.**
El diagnóstico de incentivos es correcto en dirección, pero sobrestima la magnitud. Un error no cuesta solo 20 puntos: el regreso de 2 s también suma tiempo.
- Cuánto tiempo extra: los ~2 s de retroceso más el tramo que se repite, unos 3–4 s en total.
- Cuánto vale ese tiempo en un nivel 8: la pista mide 320 m, así que t_ref = 21 s. Si la moto iba a 1.4× t_ref, 3.5 s más le restan unos 13–18 puntos del premio de rapidez.
- Además pierde progreso y acumula castigos de carril y balanceo.

El costo efectivo queda en **≈35–40 puntos**. Un choque "rentable" exige ganar más de 25 km/h de media, y eso a su vez aumenta la probabilidad del siguiente error. Es un incentivo débil, no *reward hacking* garantizado.

Más importante: **la aptitud es una decisión explícita del usuario**. La selección es por torneo (invariante a rango), así que cambiar las magnitudes **sí cambia el orden** entre individuos y produce otro algoritmo. Mi postura:
- Implementar `CASTIGO_CHOQUE` y `RAPIDEZ_SOLO_LIMPIA` como **flags apagados por defecto**.
- Medir el efecto con una ablación de varias semillas en la suite reservada.
- Hoy mismo hacer una prueba barata, sin entrenar: con la población guardada, calcular la correlación de Spearman entre `reintentos` y la velocidad de llegada. Si es positiva y significativa, hay evidencia de explotación y se propone el cambio al usuario con datos.

Lo que **sí** cambiaría por defecto es **la métrica y el criterio de subir de nivel**: llegadas limpias de una campeona validada. Eso no toca la aptitud, solo hace honesta la graduación automática.

**2. Agente 1: módulo lateral Whipple–Meijaard con LQR.**
Tiene mucho valor académico, pero no es para hoy:
- La tercera salida de la red pasa de "manubrio" a "inclinación/curvatura pedida". Eso **invalida `mejor_moto.json` y `poblacion.npz`** y obliga a reentrenar desde cero, algo que el usuario no quiere lanzar.
- Con un lazo interno LQR que hace la contradirección, la red aprende un problema **más fácil y distinto**. Cualquier comparación con el historial actual deja de ser válida.

Propuesta: ponerlo en una rama o flag (`MODELO_LATERAL="simple"` por defecto) y abrirlo como **experimento de transferencia** con ajuste fino desde los pesos actuales, comparado con entrenar desde cero. La elipse de fricción (P1) también **endurece** la tarea: va después de tener la regresión dorada, nunca en la misma sesión que los cambios de evaluación, para poder atribuir efectos.

**3. Agente 3: numba y API Gymnasium.**
- **numba:** la ganancia de 10–25× es una estimación sin medir, con 3–4 días de trabajo y sin igualdad bit a bit, lo que exige validación estadística aparte. Hoy, **multiproceso por pista** da ×3–6 sin tocar la física y con igualdad bit a bit verificable. Primero eso; numba cuando tengamos el benchmark.
- **Gymnasium:** solo la parte barata, `Simulador.paso(ctrl=None)` (≈30 líneas), que habilita los baselines PD y los controladores externos. El *wrapper* Gym y PPO necesitan torch y SB3, que no están instalados; un baseline PPO mal ajustado no prueba nada (Henderson 2018). Va a trabajo futuro.
- Ojo: la recompensa densa del Agente 3 rompe la propiedad de Markov si se mantienen los reintentos. Él mismo lo señala y propone `reintentos=0` para RL, con lo que GA y RL quedarían comparados con reglas distintas.

**4. Agente 4: `v_segura` y la curvatura futura como oráculos.**
Hay que distinguir tres cosas:
- **Curvatura futura (k1–k3):** es una *preview* de mapa. Los vehículos autónomos reales usan mapas HD; OSM ya da esa geometría. Es legítima si se le agrega ruido de mapa.
- **`v_segura` (`fisica.py:143-148`)** combina la curvatura del mapa con **μ_min verdadero de los próximos 40 m**. Ahí está la información privilegiada.
- **μ "de cámara" (`:172-173`):** privilegiado.

La literatura no recomienda quitar esas entradas, sino **medir la dependencia** y destilarla: *Learning by Cheating* (Chen et al. 2019, arXiv:1912.12294) y la locomoción cuadrúpeda con un maestro privilegiado (Lee et al. 2020, arXiv:2010.11251). Propuesta: un flag `SENSORES="ideal|realista"`, conservando las 35 entradas, donde μ percibido = μ·U(0.7, 1.3) y la curvatura lleva ruido. La tabla de ablación es el aporte científico, no la eliminación.

## (c) TOP-8 para implementar HOY (una sesión, sin entrenamientos largos)

| # | Mejora | Archivo(s) | Est. |
|---|---|---|---|
| 1 | **Red de seguridad:** prueba dorada (4 pistas × 8 redes fijas, aptitud/motivo/t_fin exactos), determinismo y lote = individual. Va primero porque todo lo demás se valida contra ella. Usa `assert` simple, sin pytest. | `pruebas/test_regresion.py`, `pruebas/datos/` | 1 h |
| 2 | **Checkpoint v2:** guardar `sigma`, `racha`, el estado del RNG y `config_hash`; escritura atómica (`.tmp` + `os.replace`); se sigue leyendo el formato 1. | `evolucion.py:_guardar/_cargar` | 45 min |
| 3 | **Correcciones del GA con flags:** `SIGMA_MIN = 0.02` (hoy el mínimo es 0.20, `evolucion.py:233`), mutación relativa a la escala de cada capa, `PROB_CRUCE` configurable con la recomendación de 0–0.2 e `INMIGRANTES` configurable. No toca la aptitud ni la campeona en posición 0. | `evolucion.py:228-251`, `config.py` | 45 min |
| 4 | **Métricas honestas:** `llegadas_limpias`, reintentos medios y componentes de la aptitud (progreso, llegada, rapidez, carril, balanceo, invasión, errores) en el CSV; criterio de subir de nivel/graduarse con llegadas limpias (flag, recomendado activo); prueba de Spearman entre reintentos y velocidad. | `fisica.py:aptitud` (devuelve también un dict), `evolucion.py:171-225` | 1 h |
| 5 | **`evaluacion.py` con pistas reservadas:** semillas `2³¹ + 1000·nivel + j`, `max_reintentos=0` como parámetro del `Simulador` y `ruido_por_moto` opcional (por defecto igual a hoy), K réplicas en el lote, IC de Wilson o Clopper-Pearson, fallas por km, CSV/JSON. Comando `--evaluar`. | nuevo `evaluacion.py`, `fisica.py:63,192`, `main.py` | 1.5 h |
| 6 | **Campeona validada:** cada 10 generaciones se evalúa el top-5 en 10 pistas de validación, y `mejor_moto.json` solo se reemplaza si mejora en validación (se conserva la campeona en posición 0). | `evolucion.py:_guardar` | 45 min |
| 7 | **Evaluación paralela por pista** en `--sin-gui` (ProcessPool con *spawn*, semillas en lugar de objetos, *initializer* para `RedVial`), prueba de igualdad serie = paralelo y `PISTAS_POR_GENERACION` configurable (se recomiendan 6 cuando hay paralelismo). La GUI no cambia. | `evolucion.py`, `main.py:entrenar_consola` | 1.5 h |
| 8 | **`Simulador.paso(ctrl=None)`, baseline PD/heurístico y `experimentos.py`:** PD sobre `lat`/`psi` con prealimentación de curvatura y velocidad objetivo `max(V_ESTABLE+1, v_segura)`; script de varias semillas que **lanza el usuario**, con IQM, IC bootstrap y Mann-Whitney + A12 (scipy). | `fisica.py:185-190`, nuevo `controladores.py`, `experimentos.py` | 1.5 h |

Total ≈ 8.5 h. Quedan para la siguiente sesión, con flag y regresión: la mitigación del levantamiento trasero (A1-P2), los sensores realistas (A4-P3), sep-CMA-ES/PGPE, numba, Whipple y el cambio de aptitud de A4 (apagado por defecto hasta tener evidencia).
