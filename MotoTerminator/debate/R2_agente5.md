# R2 — Agente 5 (Industria / transferencia): réplica

**Dato que condiciona todo:** el `mejor_moto.json` actual (igual al del respaldo v9) es de **generación 7, nivel 2** (`historial.csv` tiene 7 filas) y no hay `mejor_moto_ciudad.json`. Las cifras del README ("nivel 1→6 en ~70 gen", "nivel 8 en ~30 gen de ciudad") **no tienen hoy un artefacto que las respalde**. Con la regla de "sin entrenamientos largos", el paper de hoy sólo puede reportar **aprendizaje temprano (niveles 1–3) con IC**, más la validación del simulador. Eso hay que decirlo así: es honesto y sigue siendo presentable.

## (a) Coincidencias (los 5 agentes)

1. **Suite de evaluación con pistas reservadas** (semillas disjuntas de `rng.integers(1<<30)`), separada del entrenamiento: A2-P1, A3-Fase 5, A4-P1, A5-P1.
2. **El rebobinado se queda como andamio de entrenamiento, pero fuera de las métricas**: "llegada limpia" = META con `reintentos == 0` (A2 §5.2, A4-P2, A5-P3).
3. **Incertidumbre explícita**: varias semillas, IC (Clopper-Pearson o Wilson para tasas, bootstrap para curvas), n declarado. "8/8" no prueba nada: su IC al 95 % es [63 %, 100 %] (A4-D2).
4. **Tests y regresión antes de tocar la física** (A1-P0, A3-Fase 0, A4-P10).
5. **Qué no se toca**: la simulación vectorizada, los números aleatorios comunes (CRN) por pista, la red de 35-20-3, `SUBPASOS = 6`, la GUI y el currículo terreno→calles.

## (b) Objeciones

**1. Módulo lateral Whipple+LQR (A1-P4): no para la presentación de hoy.** Son 4–6 días y obliga a reentrenar desde cero. Una empresa prefiere un modelo de orden reducido **con sus límites medidos** a uno de alta fidelidad a medio terminar. Lo que sí vale hoy, y A1 ya lo tiene casi hecho:
- reproducir el benchmark de Meijaard (weave 4.292 m/s, capsize 6.024 m/s) como **apéndice de verificación**;
- poner en Limitaciones sus tres hallazgos, que son contundentes:
  - la red no influye en el equilibrio (`wobdd` no depende de `dirc`);
  - no hay contradirección;
  - una frenada total en plano voltea la moto aun con ABS.

P4 entra en el roadmap como el paso de TRL 3 a TRL 4. Mi objeción de fondo: **arreglar la frenada sí es urgente**, pero es un cambio de física y no se hace en la misma sesión que genera los resultados.

**2. Gymnasium/PPO (A3-Fase 2, A2-P3): importa a los revisores, casi nada a las empresas.** Un OEM o un Tier-1 pregunta por FMI/FMU, Simulink/SIL, ASAM OpenSCENARIO y trazabilidad, no por Gymnasium. Para el paper basta un **baseline clásico** (controlador heurístico de carril + perfil de velocidad por curvatura) y el **azar**. PPO va a Trabajo futuro. Sí acepto de A3 el gancho `Simulador.paso(ctrl=None)`: es el mismo que necesita mi modo "comparar controladores" y no cambia el comportamiento cuando no se usa.

**3. Aptitud, A4 contra A2: gana A2 en el entrenamiento y A4 en la evaluación.** Cambiar la aptitud del usuario (premio de rapidez sólo si la llegada es limpia, castigo ≥ 50) invalida la población guardada y es una decisión de diseño suya. Mi resolución:
- **hoy**: la aptitud queda igual, se guarda desagregada por componentes, y todas las métricas reportables usan `MAX_REINTENTOS = 0` y llegada limpia;
- el **incentivo explotable que señala A4** (un choque cuesta 20 y +27 km/h de media valen +50) va al paper como **hallazgo**;
- la variante `APTITUD_ESTRICTA` (bandera, `False` por defecto) queda como **ablación futura** con varias semillas.

**4. Renombrar: no.** El usuario no lo pidió. No se tocan carpetas, archivos, el `.bat` ni la GUI. En los documentos externos el proyecto se identifica con un nombre técnico y "MotoTerminator" queda como nombre del repositorio:
- **Título del paper:** *"Curriculum Neuroevolution for Riderless Two-Wheeler Control on Procedural and OpenStreetMap Roads: A Reproducible Reduced-Order Testbed"*
- **Nombre del banco en deck y ficha:** **MT-Bench** (MotoTerminator Benchmark).
- Una nota en el deck advierte que "Terminator" es marca de terceros y que el nombre comercial se decide antes de cualquier uso fuera del ámbito académico.

**5. Numba, paralelismo, MAP-Elites, STL, Simplex/CBF y falsificación: son días de trabajo; van a Trabajo futuro.** La falsificación (A4-P6 = mi U1) es la que tiene comprador: primer sprint después de hoy.

## (c) TOP-8 para implementar HOY (una sesión, corridas cortas reales)

Regla: **ningún número entra a un documento si no sale de un archivo en `resultados/`** (con semilla, `config_hash` y fecha).

| # | Qué | Detalle | Est. |
|---|---|---|---|
| 1 | **Red de seguridad mínima** | `tests/test_determinismo.py` (misma semilla = misma aptitud; lote = individual) + regresión dorada en 4 pistas fijas. Se corre antes y después de cada paso. | 40 min |
| 2 | **`evaluacion.py` (suite reservada)** | Semillas `2**31 + 1000·nivel + j`. Parámetro `max_reintentos` del Simulador (por defecto el valor actual, de modo que el entrenamiento no cambia). KPIs: llegada limpia y llegada con reintentos, IC Clopper-Pearson (scipy 1.15 está instalado), fallas/km, motivo de falla por material, velocidad media, margen lateral mínimo, `cmg_sat` máximo. Salida CSV+JSON. | 2 h |
| 3 | **Aptitud desagregada + `llegadas_limpias` en `historial.csv`** | Sin cambiar el valor escalar de la aptitud (columnas nuevas al final; el lector acepta el formato viejo). | 40 min |
| 4 | **Gancho `ctrl` externo + 2 baselines** | `Simulador.paso(ctrl=None)`; baseline heurístico (P sobre carril/rumbo + velocidad objetivo por curvatura y μ del lidar) y política aleatoria. Habilita "comparar controladores". | 1.5 h |
| 5 | **Corridas cortas reales** (≈ 45–60 min de cómputo, en segundo plano mientras se escriben los documentos) | (i) **Curva de aprendizaje**: 5 semillas × 20 gen `--sin-gui --nuevo` en un directorio aislado (≈ 4–10 s/gen según A3, unos 15 min en total). (ii) **Evaluación**: campeona de cada semilla + `mejor_moto.json` + 2 baselines en niveles 1–3 × 50 pistas × 2 ruidos, con reintentos 0 y 3. (iii) **Verificación**: script de A1 con los eigenvalores de Meijaard + prueba de frenada (evidencia de la limitación). (iv) **Rendimiento**: tabla de A3 (µs por moto contra N). | 1 h |
| 6 | **Reporte automático** (`reporte.py` → `resultados/<fecha>_<hash>/reporte.md` + figuras matplotlib) | Curvas media ± IC 95 % (bootstrap), tabla de KPIs por controlador y nivel, histograma de motivos de falla. Es la fuente única de las figuras del paper. | 1 h |
| 7 | **Borrador del paper** (`docs/paper_MT-Bench.md`, estructura IEEE de R1 §3.1) | Abstract, I–VIII; métodos con las ecuaciones reales de `fisica.py` (modelo de orden reducido declarado); resultados **sólo** de #5/#6; sección de Limitaciones con los hallazgos de A1 y A4 y el nivel alcanzado; Trabajo futuro = roadmap TRL (Whipple/Sharp, numba, falsificación, STL/Simplex, PPO, nombre comercial). Las referencias son las verificadas en R1 de A1, A4 y A5. | 2 h |
| 8 | **Ficha técnica (1 pág.) + deck de 12 diapositivas + sección "Alcance y limitaciones" en el README** | La ficha incluye DOF simulados, DT, sensores/actuadores, rendimiento medido, licencias (ODbL de OSM; Esri sin uso comercial sin revisar). El deck sigue la estructura de R1 §3.2 con números de #6. En el README: corregir o matizar las cifras sin respaldo y añadir la lista de afirmaciones que no se hacen. | 1.5 h |

**Total:** ≈ 10 h de trabajo, con #5 corriendo en paralelo a #7–#8. Si hay que recortar, el orden de sacrificio es #4 (dejar sólo el azar como baseline) y luego el deck (la ficha y el paper son prioritarios).

**Criterio de "listo" de la sesión:**
- una tabla con n e IC por nivel y controlador, reproducible con un solo comando;
- el paper y la ficha citan esa tabla y nada más;
- las Limitaciones dicen explícitamente:
  - "aprendizaje temprano, niveles 1–3";
  - "modelo lateral de orden reducido";
  - "el rebobinado se excluye de las métricas".
