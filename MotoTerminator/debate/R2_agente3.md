# R2 — Agente 3 (software científico y rendimiento): réplica

## (a) Coincidencias (5 de 5 o 4 de 5)
1. **Hace falta una suite reservada con semillas disjuntas** (A2 P1, A4 P1, A5 P1, A3 F5). Es lo primero que una empresa pide.
2. **El costo es overhead fijo de Python, no aritmética.** A2 midió lo mismo que yo de forma independiente (1→80 motos ≈ 1.7×). Consecuencia compartida: **paralelizar por pista, no por moto**, y una población más grande sale casi gratis.
3. **Se conserva el ruido común (CRN) en entrenamiento** (A1 D13, A2, A4 D5, A3). En evaluación se usa ruido por moto (A4).
4. **El rebobinado se queda como andamio, pero fuera de las métricas** (A2, A4 P2, A5 P3).
5. **Checkpoint incompleto**: σ y racha no se guardan (A2 D1, A3 D6).
6. **Tests de física y de convergencia en DT antes de cambiar la física** (A1 P0, A4 P10, A3 F0).
7. **No migrar a JAX ni a 3D, y conservar la red 35-20-3.**

## (b) Objeciones técnicas

**1. La paridad numérica de numba y SUBPASOS=12 (A1 P9).** A1 pide numba "bit a bit o 1e-12" para que salga gratis subir a 12 subpasos. Eso **no se puede cumplir sobre una trayectoria**: numba y numpy difieren en el último ulp (tanh, interp, orden de suma), y con contactos rígidos la dinámica es caótica, así que las trayectorias divergen en cientos de pasos. A 1e-12 solo se puede verificar *un paso aislado*; el resto exige regresión estadística (KS y tasa de llegada). Además, SUBPASOS=12 **cambia la dinámica**: la propia tabla de A1 da 2–6 % de diferencia en frenado. Los pesos entrenados con 6 rendirían distinto. Mi postura:
- 6 se queda como valor por defecto (es decisión del usuario).
- 12 y 24 solo como flag para el test de convergencia.
- **Numba no va hoy**: es de riesgo medio en una sola sesión. Hoy van mejoras sin ningún riesgo numérico, como el paralelismo por pista, que da resultados **bit-idénticos**: verifiqué que evaluar en lote o individualmente da diferencia 0.0. Eso da unas 3× con 3 pistas, o permite 8 pistas en el mismo tiempo de reloj.

**2. ¿Gymnasium/PPO hoy, o la suite del A4?** Primero la suite del A4. gymnasium, SB3 y torch **no están instalados**, y un PPO sin protocolo de evaluación no prueba nada. Lo que sí vale hacer hoy es la **pieza habilitadora barata: `Simulador.paso(ctrl=None)`**. Con ella se puede inyectar un control externo, y sirve a la vez para:
- el baseline heurístico (A2, baseline 4);
- el `Controlador` enchufable (A5 P2);
- el escudo Simplex (A4 P7);
- la futura `MotoEnv`.

La clase Gymnasium completa se deja para la siguiente sesión.

**3. Conflicto de aptitud entre A4 y A2.** A4 quiere un castigo de 50 o más por choque y el premio de rapidez solo si la llegada es limpia. A2 quiere no tocar la aptitud del usuario. Decido por la regla del usuario: la **aptitud de entrenamiento no cambia por defecto**.
- Se agregan `llegadas_limpias`, los componentes desagregados de la aptitud (A2 P5) y una columna nueva en el CSV.
- `APTITUD_ESTRICTA=False` en config, para que el experimento A/B lo decida con varias semillas.
- El criterio de subir de nivel tampoco cambia hoy: también es diseño del usuario. Queda como flag `SUBIR_CON_LIMPIAS=False`.
- El *reward hacking* que señala A4 es real, pero se demuestra con datos (la suite) antes de imponer el cambio.

**4. Modelo lateral físico de A1 (P4).** Tiene el mayor valor académico y también el mayor riesgo:
- son 4–6 días;
- invalida los pesos guardados;
- cambia el significado de la salida 3;
- choca con la decisión del usuario sobre el equilibrio.

**No va hoy.** Lo que sí va hoy, sin tocar la simulación, es el benchmark de Meijaard como validación independiente que documenta que el modelo actual es "de orden reducido" (la misma postura de A4 D6 y A5 §5.2). La mitigación de levantamiento trasero (A1 P2) corrige un vuelco real con ABS activo, pero cambia la física. Propongo un flag apagado hasta capturar las referencias doradas y comparar con la suite.

**5. Ruido por moto en evaluación (A4).** Estoy de acuerdo, con una condición: el valor por defecto `False` mantiene el entrenamiento bit-idéntico. Debe existir un test que lo garantice.

## (c) TOP-8 para implementar HOY (en orden)

Reglas de propiedad para evitar conflictos de edición:
- **Impl. A** es el único que edita `fisica.py` y `config.py`.
- **Impl. B** es el único que edita `evolucion.py`.
- **Impl. C** solo crea archivos nuevos y es el único que edita `main.py`.
- Nadie toca `interfaz.py`, `graficos.py`, `planificador.py` ni el `.bat`.

| # | Ítem | Impl. | Archivos | Est. |
|---|---|---|---|---|
| 1 | **Referencias doradas + determinismo + benchmark, ANTES de cualquier cambio.** 4 pistas con semilla fija (niveles 1/3/5/8) × 8 redes fijas: aptitud, motivo, t_fin y trayectoria del líder. Tests: lote = individual, repetición idéntica, carga de los `mejor_moto.json`/`poblacion.npz` actuales. Corren con pytest si está instalado, o con `python tests/correr.py` como respaldo, porque pytest no está instalado. | C | `tests/` nuevo, `tests/datos/doradas.npz`, `bench/bench_fisica.py` | 1.5 h |
| 2 | **Checkpoint formato 2 atómico.** Guarda σ, racha, estado del RNG, `config_hash` y `formato`. Sigue leyendo el formato 1. Escritura con `tmp`+`os.replace`, copia `.bak`, y aviso (sin bloquear) si cambió config. | B | `evolucion.py` (`_guardar`, `_cargar`, `reiniciar`) | 1.5 h |
| 3 | **Hooks del simulador:** `paso(ctrl=None)`, `Simulador(max_reintentos=None, ruido_por_moto=False)`, `componentes_aptitud()` (dict) y `llegadas_limpias`. Con los valores por defecto el resultado es bit-idéntico, verificado contra el ítem 1. | A | `fisica.py` (constructor, `paso` 185-193, `_revisar` 399, junto a `aptitud`), `config.py` (flags `APTITUD_ESTRICTA`, `SUBIR_CON_LIMPIAS`, `MITIGA_LEVANTAMIENTO`, todos `False`) | 1.5 h |
| 4 | **Suite reservada (`--evaluar`).** Semillas desde 2³¹+1000·nivel+j, sin reintentos, ruido por moto, K réplicas de la campeona en el lote. Métricas: llegada limpia con Clopper-Pearson, fallas/km con Garwood, desglose por motivo y rasgo/material, TLC mínimo. Salida en CSV/JSON. Depende del ítem 3. | C | `evaluacion.py` nuevo, `main.py` (argumento `--evaluar`) | 2.5 h |
| 5 | **Métricas limpias en el historial** (llegadas limpias + componentes; la aptitud y el currículo quedan igual) y un **gancho de validación**: la campeona solo se reemplaza en `mejor_moto.json` si mejora en las semillas de validación. El gancho va con flag; por defecto se mantiene el comportamiento actual. | B | `evolucion.py` (`_evolucionar`, CSV con columnas nuevas al final para que los lectores viejos sigan funcionando) | 1 h |
| 6 | **Evaluación paralela por pista en `--sin-gui`.** `ProcessPoolExecutor` con `spawn`, `initializer` para `RedVial`, y un test de que sale bit-idéntico al secuencial. Va con `--procesos N`; por defecto es 1 si no se pide, para no cambiar el uso actual. | C (módulo) y B (gancho de ~5 líneas) | `paralelo.py` nuevo, `evolucion.py` (`correr_generacion`), `main.py` | 2 h |
| 7 | **Validación física sin tocar código:** caída libre, compresión estática ≈ mg/2k, frenada contra g·b/h, simetría izquierda/derecha, convergencia con SUBPASOS 6/12/24 (parcheando `C.DT` y `fisica._LIM_FRIC` en el test) y benchmark de Meijaard independiente (weave 4.2924 m/s, capsize 6.0243 m/s). | C (o A1) | `tests/test_fisica.py`, `validacion/meijaard.py` nuevos | 2 h |
| 8 | **Controlador de referencia + reporte automático.** PD heurístico (lat/psi + velocidad objetivo `v_segura`) mediante `paso(ctrl=)`, evaluado con la misma suite que la red. Genera `reportes/AAAA-MM-DD.md` con el ODD, las métricas con IC, red contra baseline, hashes y limitaciones declaradas. Más un `requirements.txt` con versiones. | C | `controladores.py`, `reporte_seguridad.py`, `requirements.txt` nuevos | 2 h |

**Orden de integración:**
1. El ítem 1 se integra primero y se congela.
2. Los ítems 2, 3 y 7 van en paralelo.
3. Después los ítems 4, 5 y 6.
4. Al final el ítem 8.

Cada merge debe pasar las referencias doradas exactas. **Fuera de hoy**, en este orden para la siguiente sesión: numba, `MotoEnv` de Gymnasium, sep-CMA/PGPE, sensores y latencia, MSC activado, modelo lateral Whipple.
