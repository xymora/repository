# Consenso del panel (Ronda 3 — síntesis del moderador)

## Veredicto unánime
1. **Primero medir bien, después más rápido, después más fidelidad.** Una tabla con IC vale más que diez terrenos nuevos.
2. **La aptitud de entrenamiento del usuario NO cambia por defecto** (premio de rapidez, −20 por error, regreso 2 s, máx 3). La versión estricta va como flag `APTITUD_ESTRICTA=False`. La honestidad se logra en **evaluación**: llegada limpia (`max_reintentos=0`), pistas reservadas, IC.
3. **Whipple/Sharp + LQR (Agente 1 P4) NO va hoy** → roadmap y sección de limitaciones. Sí va el benchmark Meijaard 2007 como validación/apéndice.
4. **Gymnasium/PPO NO va hoy**; sólo el gancho `paso(ctrl=)` / `controlador=` que habilita baselines, escudo y API futura.
5. Numba, sep-CMA/PGPE completos, multicuerpo 3D → trabajo futuro (se deja sólo lo que no arriesgue paridad).
6. Valores por defecto = comportamiento idéntico al v9 (prueba dorada contra `..\MotoTerminator_respaldo_v9_2026-10-08`).
7. No renombrar carpetas/código. Título externo: *"Curriculum Neuroevolution for Riderless Two-Wheeler Control on Procedural and OpenStreetMap Roads: A Reproducible Reduced-Order Testbed"*; banco: **MT-Bench**.
8. No afirmar: "física realista", "el giroscopio/la red equilibra", cumplimiento ISO 26262/SOTIF, transferencia a moto real, tasas con rebobinado, resultados de 1 semilla. El README matiza cifras sin archivo de respaldo.

## Contrato de interfaz (todos lo respetan)

### `fisica.Simulador` (dueño: Implementador Física)
```python
Simulador(pista, pesos, semilla_ruido=0, *, max_reintentos=None, ruido_por_moto=False,
          filtro_obs=None, controlador=None, n=None, registrar=False)
```
- `max_reintentos=None` → usa el valor de config (comportamiento actual). `0` → el primer error termina a esa moto (fallo).
- `ruido_por_moto=True` → cada moto recibe su propia secuencia de ruido (sólo evaluación). Default: ruido compartido actual.
- `filtro_obs(obs: ndarray(n,35), sim) -> ndarray(n,35)`: perturbación de sensores (ruido/sesgo/latencia). Se aplica antes de la red o del controlador.
- `controlador(obs: ndarray(n,35), sim) -> ndarray(n,3)` en el mismo rango que la salida de la red; si se da, reemplaza a la red. `pesos` puede ser `None` si se pasa `n`.
- `paso(ctrl=None)`: si `ctrl` (n,3) se da, se usa en ese paso (API tipo Gym).
- Métodos/atributos nuevos: `llegaron()` → bool(n); `llegadas_limpias()` → bool(n) = llegó y `reintentos==0`; `componentes_aptitud()` → dict de arrays (n,) cuya suma == `aptitud()` (tolerancia 1e-9); `distancia_km()` → array (n,) recorrida; `motivo` (ya existe) documentado con nombres en `fisica.MOTIVOS` (dict código→texto).
- `registrar=True` → `sim.traza` dict de arrays (T,n) con claves: `t, x, v, lat, phi, th, cmg_sat, v_segura, en_suelo, invasion` (se llena por paso de control; `traza_arrays()` devuelve np.ndarray).
- Flags de config nuevos (todos **False** por defecto): `APTITUD_ESTRICTA`, `MSC_ACTIVO` (anti-levantamiento trasero / antiwheelie / ABS según inclinación), `FRICCION_COMBINADA` (elipse por rueda con carga real), `RUIDO_SQRT_DT`.

### `evolucion.Entrenador` (dueño: Implementador Evolución)
- Nuevos kwargs: `dir_datos=None` (carpeta de checkpoints; default la actual → los experimentos NO pisan `mejor_moto.json`/`poblacion.npz` del usuario), `procesos=1`, `guardar=True`.
- Checkpoint formato 2, escritura atómica (tmp + `os.replace`), guarda sigma, racha, estado RNG, hash de config, versión; lee formato 1 sin pérdida.
- `historial.csv`: columnas nuevas al final (compatibles): `llegadas_limpias_pct`, `reintentos_lider`, componentes de aptitud del líder.
- GA: flags en config con defaults = comportamiento actual (`SIGMA_MIN`, `PROB_CRUCE`, `MUTACION_RELATIVA`, `INMIGRANTES`), más campeona validada (`VALIDAR_CAMPEONA`, cada N gens en pistas de validación reservadas, semillas en rango propio).
- Evaluación paralela por pista (`procesos>1`, spawn de Windows) con prueba de igualdad exacta contra serial.

### Rangos de semillas
- Entrenamiento: los actuales (< 2^31).
- Validación de campeona: `2**30 + 1000*nivel + j`.
- Prueba reservada (evaluacion.py): `2**31 + 1000*nivel + j`. Ruidos de prueba: `2**31 + 7919*k`.

## Reparto de archivos (sin choques)
| Implementador | Archivos que edita/crea |
|---|---|
| Física (Agente 1) | `fisica.py`, `config.py` (bloque física), `tests/test_fisica.py`, `validacion_fisica.py` |
| Evolución (Agente 2) | `evolucion.py`, `paralelo.py`, `config.py` (bloque "Evolución v10" al final), `tests/test_evolucion.py` |
| Software (Agente 3) | `main.py`, `controladores.py`, `experimentos.py`, `tests/run_tests.py`, `tests/test_regresion.py`, `bench.py`, `requirements.txt`, `pyproject.toml`, `.github/workflows/ci.yml`, `interfaz.py` (sólo cambios mínimos: mostrar llegadas limpias) |
| Seguridad (Agente 4) | `evaluacion.py`, `sensores.py`, `stl.py`, `reporte_seguridad.py`, `falsificador.py`, `tests/test_evaluacion.py` |
| Industria (Agente 5) | `docs/` (paper, deck, ficha técnica, related work), `README.md` (al final), `reporte.py` (figuras) |

## Fase B (después de implementar)
Corridas cortas reales en `resultados/` (dir_datos aparte): ~5 semillas × 20 gens niveles 1–3, evaluación reservada, Meijaard, frenada, benchmark de rendimiento, baselines (aleatorio, PD). Los números del paper salen SÓLO de ahí.
