# R1 — Agente 3: Arquitectura de software científico y rendimiento

Autor: Agente 3 (arquitecto de software científico / rendimiento) · Ronda 1 · 2026-10-08
Alcance: diagnóstico con mediciones y plan incremental. No modifiqué ningún archivo del proyecto. Los perfiles se corrieron desde el scratchpad, importando los módulos y con `Entrenador._guardar` anulado para no tocar `mejor_moto.json`, `poblacion.npz` ni `historial.csv`.

---

## 1. Mediciones (Windows 10, Python 3.10, numpy 2.2, 1 núcleo)

### 1.1 Costo de una generación
| Medición | Valor |
|---|---|
| Generación completa, 80 motos, nivel 1, población al azar (`correr_generacion`) | **3.7–3.8 s** |
| Pista nivel 1 con población cercana a la campeona (77/80 llegan) | 933 pasos de control, **2.56 s**, 2.75 ms/paso |
| Pista nivel 5 (ninguna llega, todas agotan reintentos o tiempo) | 1267 pasos, **3.28 s**, 2.59 ms/paso |
| Generación estimada en niveles altos (3 pistas de 280–320 m, más motos vivas) | **≈ 9–12 s** |
| Construir `Pista(8, …)` | 2.9 ms (no importa) |

### 1.2 Dónde se va el tiempo (cProfile, pista nivel 5, 80 motos)
- `Simulador._fisica`: **0.765 s de 1.264 s propios (≈ 60 %)**, más 0.28 s en ufuncs/clip que se llaman desde ahí, así que la física sola es **≈ 83 %**.
- `observar` + `red.adelante` + `_revisar` + `_tomar_foto`: ≈ 15 %.
- `np.clip` se llama **29 051 veces** en 433 pasos (≈ 67 por paso) y cada llamada pasa por `fromnumeric._wrapfunc`, que solo agrega costo de Python.

### 1.3 Escalamiento con el tamaño de población (el hallazgo central)
| N motos | `_fisica` µs/subpaso | µs por moto | observar+red µs | foto µs |
|---:|---:|---:|---:|---:|
| 1 | 333 | 333 | 155 | 34 |
| 10 | 342 | 34 | 170 | 38 |
| 80 | 406 | **5.1** | 239 | 48 |
| 320 | 591 | 1.85 | 471 | 79 |
| 1280 | 1953 | 1.5 | 1515 | 220 |

**Diagnóstico:** con N = 80, el simulador está **dominado por el costo fijo del intérprete** y no por la aritmética. Cada subpaso cuesta ≈ 330 µs aunque haya una sola moto, porque `_fisica` (fisica.py:219-375) lanza unas 150 operaciones numpy de 2 a 3 µs cada una sobre arreglos de 80 elementos. Hay dos consecuencias:
1. Pasar de 80 a 320 motos cuesta solo 1.45×. La población de 80 es pequeña por inercia histórica, no porque el cómputo obligue.
2. El modo demo (1 moto) gasta ≈ 2.5 ms por paso de control en costo fijo. Con la animación x16 eso ya son ≈ 40 ms por cuadro.

### 1.4 Prototipo numba (solo la parte de contacto, en el scratchpad)
- Contacto rueda-suelo (9 puntos × 2 ruedas, interpolación y argmax): **numba 11.9 µs contra numpy 49.6 µs con N = 80**; con N = 1280, 197 µs contra 485 µs.
- Primera compilación ≈ 1.9 s. Con `cache=True` la segunda ejecución reutiliza el caché. `import numba` tarda 0.5–1.0 s.
- Extrapolación: fusionar los 6 subpasos, la red y las reglas en **un solo kernel por paso de control** quita ≈ 900 llamadas numpy por paso. Mi estimación es **2.6 ms → 0.1–0.25 ms por paso con N = 80 (10–25×)**, y más si el kernel corre episodios completos con `prange` sobre los pares (pista, moto). Es una estimación todavía no medida: la Fase 3 la tiene que confirmar con el benchmark.

### 1.5 Propiedades verificadas que habilitan el plan
- **Determinismo:** la misma población y la misma semilla dan aptitudes idénticas (`array_equal` = True).
- **Independencia entre individuos:** evaluar cada moto sola o todas en lote da **exactamente** la misma aptitud (diferencia máxima 0.0). El ruido `empujon/deriva` es **un escalar por paso compartido por toda la población** (fisica.py:192-193). Eso equivale a *common random numbers*: es metodológicamente bueno y además permite **repartir la población entre procesos sin cambiar resultados**.
- `Pista` es *picklable* (352 KB en nivel 8), lo que sirve para multiprocessing con `spawn`.
- Checkpoints actuales: `poblacion.npz` = {pob (80, 783), generacion, nivel}; `mejor_moto.json` = {capas, generacion, modo, nivel, aptitud, pistas_terminadas, pesos[783]}.
- No están instalados: gymnasium, stable-baselines3, pytest, torch, hypothesis, mypy ni ruff.

---

## 2. Debilidades concretas (con archivo y línea)

### Rendimiento
- **D1. Física "vectorizada" con costo fijo dominante** (fisica.py:219-375). Ver 1.3. Es el cuello de botella número 1.
- **D2. Repetición de `pista.indice`** (≈ 22 llamadas por paso). `observar` (fisica.py:136-162) y `paso` (fisica.py:191, 199, 201) recalculan `p.indice(self.px)` hasta 5 veces en el mismo paso.
- **D3. Re-indexado de pesos en cada paso:** `[(W[self.ids], b[self.ids]) ...]` (fisica.py:188) copia N×35×20 flotantes en cada paso de control cuando alguna moto ya terminó. Es barato en N = 80, pero crece con N.
- **D4. `einsum` con pesos distintos por moto** (red.py:29): a N = 1280 la red cuesta casi lo mismo que la física. Con numba o `np.matmul` en lote (`x[:, None, :] @ W`) se resuelve.
- **D5. Entrenamiento en el hilo de la GUI:** en turbo se presupuestan 45 ms por cuadro (interfaz.py:517-519) y en modo animado se avanza `VELOCIDADES[i]` pasos por cuadro (interfaz.py:513). El dibujo de tkinter y la física compiten en el mismo hilo, así que la GUI nunca usa más de 1 de los 8 núcleos.

### Reproducibilidad y ciencia
- **D6. Checkpoint incompleto:** `np.savez` (evolucion.py:125) no guarda `sigma`, `racha`, el estado del RNG, el hash de `config` ni una versión de formato. Al hacer `--continuar`, `racha` vuelve a 0, `sigma` vuelve al valor de config y el RNG se re-siembra (con `None` si no hay `--semilla`). Por eso **una corrida interrumpida y reanudada no es reproducible**.
- **D7. Configuración global mutable sin versionar** (config.py). Hay constantes derivadas en tiempo de importación (`_LIM_FRIC`, fisica.py:33; `V_CRITICA`, config.py:118), de modo que barrer `SUBPASOS` o `SUELO_K` desde código no se propaga. Nada registra con qué parámetros se entrenó una moto: un `mejor_moto.json` puede cargarse con una física distinta sin aviso. Solo se valida `capas` (evolucion.py:40).
- **D8. Escrituras no atómicas** (evolucion.py:120-138). Si el proceso muere a mitad de `json.dump` o de `np.savez`, el archivo queda corrupto, y `_cargar` traga el error en silencio (evolucion.py:85-86, 43-44). Ese caso **reinicia el entrenamiento sin avisar**.
- **D9. Excepciones silenciadas y sin logging:** todo es `print` o `except: pass`. No hay niveles de log, ni archivo de log, ni un registro de experimento (commit, semilla, parámetros, tiempos).
- **D10. Evaluación ruidosa:** 3 pistas por generación (config.py:153). La élite se re-evalúa en pistas nuevas (eso es correcto: evita aptitudes viejas), pero no hay un **conjunto de validación fijo** de pistas con semilla para medir el progreso real. La curva de `historial.csv` mezcla dificultad y habilidad.

### Arquitectura y mantenibilidad
- **D11. `Simulador.paso` acopla control y física** (fisica.py:190): la red se evalúa adentro. Por eso no se puede inyectar una acción externa (RL, teclado, controlador PID de referencia), y ese es el obstáculo principal para una API Gymnasium.
- **D12. `_quedarse` reduce los arreglos** (fisica.py:454-460). Es una buena optimización para el GA, pero choca con un entorno vectorizado con autoreset, que necesita forma fija y máscaras.
- **D13. `Entrenador.reiniciar` llama a `self.__init__`** (evolucion.py:146). Es un antipatrón y además pierde `semilla`.
- **D14. `interfaz.py` monolítico** (1385 líneas) que muta globales de layout (`ajustar_tamano`, interfaz.py:42-52) y mezcla lógica de entrenamiento (interfaz.py:490-539) con dibujo.
- **D15. No hay paquete, ni tests, ni tipado, ni CI, ni `requirements`/`pyproject`.** El `.bat` instala numpy y pillow sin versión fija (Iniciar_Simulador.bat:20-27).

---

## 3. Plan priorizado e incremental

Principio rector: **cada fase deja el `.bat`, los comandos de `main.py` y los archivos guardados funcionando igual.** El backend numpy actual se conserva siempre como **oráculo de referencia**.

### Fase 0 — Red de seguridad (esfuerzo: 1 día · riesgo: nulo)
**Qué:** tests y benchmark *antes* de tocar nada.
- `tests/` con pytest (agregarlo a `requirements-dev.txt`, no al `.bat`):
  - `test_determinismo.py`: misma semilla dos veces da aptitudes idénticas (bit a bit); lote igual a individual (sección 1.5).
  - `test_regresion_dorada.py`: 4 pistas con semilla fija (niveles 1, 3, 5, 8) × 8 redes fijas guardadas en `tests/datos/redes_doradas.npz`. Se guarda `aptitud`, `motivo`, `t_fin`, `progreso` y la trayectoria del líder cada 30 pasos. Tolerancia **exacta** para el backend numpy y **estadística** para backends acelerados (ver Fase 3).
  - `test_fisica_invariantes.py`: moto sin control sobre plano en reposo (equilibrio estático de la suspensión: compresión ≈ m·g/(2k) ± 5 %); energía no creciente sin motor y con amortiguamiento; caída libre sin contacto (vy = −g·t); `estabilidad(v)` monótona; `_tope_direccion` acotada por `DIR_MAX`; conservación de la forma de los arreglos tras `_regresar`.
  - `test_checkpoint.py`: carga de los `mejor_moto.json`/`poblacion.npz` actuales (fixtures copiados del respaldo v9) y ida y vuelta guardar-cargar.
  - `test_cli.py`: `python main.py --help` y `main.py --sin-gui 1 --nuevo --semilla 1` contra un directorio temporal (requiere D-ruta, Fase 1).
  - `test_gui_smoke.py`: crea `tk.Tk()`, `raiz.withdraw()`, instancia `App` con un `Entrenador` de 4 motos y ejecuta `ciclo()` 30 veces llamando a `raiz.update()`; verifica que no haya excepciones, que el canvas tenga >0 ítems (`cv.find_all()`) y que se pueda alternar `turbo`, `demo` y `pausa`. Sin capturas de pantalla. Se marca `@pytest.mark.gui` y se omite si no hay display.
- `bench/bench_fisica.py`: tabla como la de 1.3 (N ∈ {1, 10, 80, 320, 1280}) y pasos/s por moto, en salida JSON para comparar entre commits.
- `git init` con un `.gitignore` que excluya `poblacion*.npz`, `historial*.csv`, `datos/*.jpg` y `__pycache__`.

### Fase 1 — Higiene sin cambio de comportamiento (1–2 días · riesgo: bajo)
1. **Checkpoints versionados y atómicos (D6, D8).** Se agrega a `poblacion.npz` lo siguiente: `formato=2`, `sigma`, `racha`, `rng_state` (JSON de `bit_generator.state`), `config_hash` y `config_json`. A `mejor_moto.json` se le agregan `"formato": 2`, `"config_hash"` y `"fisica"` (subconjunto de parámetros). La **lectura acepta el formato 1** (las claves que faltan toman los valores actuales por defecto) y por lo tanto la migración es implícita. La escritura va a `*.tmp` y luego `os.replace`, y antes de sobrescribir se rota a `*.bak`. Si `config_hash` difiere, se **avisa** pero se carga igual, para no romper el flujo del usuario.
2. **Logging (D9).** Un módulo `registro.py` con `logging` para consola (mismo texto que hoy, de modo que el usuario no ve diferencia) y un archivo `registros/moto_YYYYMMDD.log` rotativo. Las excepciones que hoy se tragan pasan a `log.warning` con la causa.
3. **Ruta de datos inyectable.** `evolucion.ruta()` acepta un `dir_datos` (por defecto `AQUI`, como hoy). Eso permite tests y experimentos en directorios aislados.
4. **`reiniciar` sin `__init__` (D13).** Se extrae `_estado_inicial()`.
5. Se cachean `i_px = p.indice(self.px)` y `kappa` en `paso` y `observar` (D2). Es trivial y no cambia los resultados bit a bit.
6. Agregar `requirements.txt` (`numpy>=2.0,<2.3`, `pillow`, `numba>=0.60` opcional) y hacer que el `.bat` lo use con `pip install -r` solo si falta algo. Mismo comportamiento.

### Fase 2 — Separar control de física: núcleo reutilizable (2 días · riesgo: medio-bajo)
- `Simulador.paso(ctrl=None)`: si `ctrl` es `None`, la red calcula el control como hoy. Si viene, se usa el control externo. Equivale a separar `politica(obs) → ctrl` de `dinamica(ctrl)` (D11).
- Nuevo parámetro `Simulador(..., compactar=True)`. Con `False` no se reducen los arreglos: se usa una máscara `vivo` y las motos terminadas se congelan (D12). El GA sigue usando `True`, así que el rendimiento actual no cambia.
- `ParamsFisica`: `dataclass(frozen=True)` construido **desde** `config.py` (que se queda igual como "panel de perillas" del usuario). Las constantes derivadas (`_LIM_FRIC`, `V_CRITICA`, `DT`) se calculan en `ParamsFisica.__post_init__`. `Simulador(params=...)` es opcional; por defecto se usa `ParamsFisica.desde_config()`. Con esto se obtienen barridos de parámetros sin editar archivos y un `config_hash` estable (sha256 de `json.dumps(asdict(p), sort_keys=True)`).
- **API Gymnasium opcional** en `entorno_gym.py`, **sin requerir gymnasium**:
  ```python
  try:
      import gymnasium as gym; from gymnasium import spaces; _Base = gym.Env
  except ImportError:
      gym = spaces = None; _Base = object
  class MotoEnv(_Base):
      metadata = {"render_modes": ["rgb_array", None], "render_fps": 30}
      # obs Box(35,) float32 (la misma de Simulador.observar)
      # action Box(-1, 1, (3,)) float32
      def reset(self, *, seed=None, options=None) -> (obs, info)
      def step(self, a) -> (obs, reward, terminated, truncated, info)
  ```
  - Recompensa densa = Δ(aptitud parcial): `100·Δprogreso/largo − PENAL_CARRIL·|lat−LAT_CARRIL|·dt·peso − PENAL_BALANCEO·|φ−φ_nec|°·dt`, más bonos y castigos terminales idénticos a `Simulador.aptitud`. Se prueba que **la suma de recompensas del episodio = `aptitud()`** con tolerancia de 1e-6, lo que deja GA y RL comparables en la misma métrica.
  - `terminated` = META o error sin reintentos; `truncated` = TIEMPO o ATASCADO. Opción `reintentos=0|3` (por defecto 0 para RL, porque el retroceso rompe la propiedad de Markov), `nivel`, `modo` y `pista_fija`.
  - Espacios en float32 (requisito práctico de `check_env` de SB3). Si gymnasium no está instalado, la clase funciona igual con tuplas, y los tests la ejercitan sin la dependencia.
  - `MotoVecEnv`: una clase **nativamente vectorizada** que aprovecha que `Simulador` ya corre N motos (con `compactar=False`), autoreset `NEXT_STEP` (el valor por defecto de Gymnasium ≥ 1.1) y `metadata["autoreset_mode"]`. Además, un adaptador fino a `stable_baselines3.common.vec_env.VecEnv` en `contrib/sb3.py`, importado solo si SB3 existe. Script de ejemplo `experimentos/ppo_sb3.py` (no forma parte del `.bat`).
  - Riesgo: en la variante vectorizada todas las motos comparten pista. El reset de una sub-moto la devuelve a la salida de la **misma** pista, y la pista se cambia cada K episodios. Así queda documentado.

### Fase 3 — Backend acelerado con numba (3–4 días · riesgo: medio)
- Archivo `fisica_nb.py` con un kernel `@njit(cache=True, fastmath=False)` `paso_control(estado SoA, pista arrays, pesos, ruido_t, params) → estado` que fusiona los 6 subpasos, `observar`, la red (34×20×3, bucles explícitos) y `_revisar` (salvo `_regresar`, que se queda en Python porque ocurre pocas veces). El estado se organiza en un arreglo estructurado `float64[n_campos, N]`, lo que además **simplifica `_tomar_foto`/`_regresar` a una sola copia de bloque** (hoy son 27 `getattr` y asignaciones).
- Para la pista se exponen `xs, hs, mu, rr, rugo, kappa, kmax, mu_min` como arreglos contiguos. Es la misma interfaz para `Pista` y `PistaCalle`; `PistaCalle.altura` = 0 se trata como `hs` de ceros.
- **Selección:** `config.BACKEND = "auto"` (numba si importa, si no numpy). Si numba falla al compilar → `log.warning` y vuelta a numpy, para que el `.bat` siga funcionando en cualquier PC. Compilar al arranque en un hilo (≈ 2 s la primera vez y luego caché) mientras se dibuja la ventana.
- **Validación (lo crítico):** numba y numpy **no** coinciden bit a bit (tanh, interp y el orden de suma difieren en el último ulp), y la dinámica con contactos es caótica: las trayectorias divergen tras cientos de pasos. Se exige entonces lo siguiente:
  (a) un paso aislado coincide con `rtol=1e-10` en todos los campos;
  (b) 100 pasos sobre plano sin contactos duros coinciden con `rtol=1e-6`;
  (c) **regresión estadística**: sobre 32 pistas × 64 redes doradas, la distribución de aptitudes y la tasa de llegada no difieren (KS p > 0.01, |Δmedia| < 1 %).
  El backend numpy queda como referencia y como `--backend numpy`.
- Ganancia esperada: 10–25× por paso con N = 80 (a medir con `bench/`). Una generación de niveles altos bajaría de ≈ 10 s a < 1 s, lo que deja subir la población a 200–400 o las pistas por generación a 6–8 (reduce D10), con el mismo tiempo de reloj.

### Fase 4 — Paralelismo (2 días · riesgo: medio)
Hay dos opciones, en orden de preferencia:
1. **Kernel de episodio completo con `numba.prange`** sobre los pares (pista, moto): 3 pistas × 80 motos = 240 tareas independientes, ruido CRN precomputado por pista (`ruido[pista, paso, 2]`, generado con el mismo `default_rng(semilla)` actual, de modo que los valores son idénticos). Usa los 8 núcleos **sin multiprocessing y sin el problema del `spawn` en Windows**. Lo usan `--sin-gui` y el turbo de la GUI. El modo animado sigue paso a paso.
2. **Alternativa sin numba:** `concurrent.futures.ProcessPoolExecutor` con `mp_context=spawn`, un `initializer` que recibe la `RedVial`/pistas una sola vez, reparto **por pista** (no por moto, porque con costo fijo dominante partir la población empeora: ver 1.3) y `main.py` ya protegido por `if __name__ == "__main__"`. Hay que evitar que los workers importen `tkinter` (importación perezosa de `interfaz`), y gracias a la independencia demostrada en 1.5 los resultados son idénticos a la versión serial.
- La GUI en turbo puede correr el entrenamiento en un `threading.Thread`: numba libera el GIL con `nogil=True`. La comunicación usa `queue.Queue` y `after()` hace *polling*, el mismo patrón que ya usa `_preparar_ciudad` (interfaz.py:403-414). Eso resuelve D5 sin reescribir la GUI.

### Fase 5 — Harness de experimentos y presentación (2–3 días · riesgo: bajo)
- `python -m moto.experimento run --config experimentos/base.toml --semillas 0-9 --generaciones 200 --salida resultados/` (o `python experimento.py ...`, para no exigir el paquete). Cada corrida escribe `resultados/<fecha>_<hash>/` con `config.json`, `meta.json` (commit git, versiones de numpy/numba, CPU, semilla, backend), `historial.parquet|csv`, `checkpoints/gen_XXXX.npz` cada K generaciones y `validacion.csv`.
- **Conjunto de validación fijo:** 20 pistas por nivel con semillas reservadas (por ejemplo 10⁹ + i). La campeona se evalúa en ese conjunto cada 10 generaciones. Es la métrica reportable (D10).
- `python experimento.py comparar resultados/A resultados/B`: curvas media ± IC 95 % sobre semillas (matplotlib) y prueba de Mann-Whitney sobre la aptitud de validación final. Así se vuelven comparables GA contra CMA-ES (fácil de agregar como `Optimizador` intercambiable) contra PPO-SB3 (vía Fase 2).
- `python experimento.py bench` corre el benchmark de 1.3 y lo anexa a `bench/historial.jsonl`.

### Fase 6 — Empaquetado, tipado y CI (1–2 días · riesgo: bajo si se hace con *shims*)
- Estructura `src/moto_terminator/{fisica,red,evolucion,terreno,calles,...}.py` + `pyproject.toml` (extras `[rapido]` = numba, `[rl]` = gymnasium y stable-baselines3, `[dev]` = pytest, ruff, mypy, hypothesis). **Los archivos planos de la raíz se quedan como *shims* de una línea** (`from moto_terminator.fisica import *`) y `main.py` sigue en la raíz, así que el `.bat` no cambia. Es opcional: si el panel prefiere no mover archivos, basta con `pyproject.toml` + `tests/` en la raíz plana.
- Anotaciones de tipos en las firmas públicas (`numpy.typing.NDArray[np.float64]`) y `mypy --strict` solo en `fisica`, `red`, `evolucion` y `entorno_gym`.
- `ruff` (lint + formato) con una configuración tolerante a nombres en español.
- GitHub Actions: matriz `windows-latest` y `ubuntu-latest` × Python 3.10/3.12; jobs `pytest -m "not gui"`, `pytest -m gui` bajo `xvfb-run` en Linux, `ruff`, `mypy` y un benchmark de 10 s que solo informa (no falla). Si se publica, un badge en el README.

### Resumen de prioridades
| # | Fase | Valor | Esfuerzo | Riesgo |
|---|---|---|---|---|
| 1 | 0 Tests + benchmark | habilita todo lo demás | 1 d | nulo |
| 2 | 1 Checkpoints v2 atómicos + logging | reproducibilidad real, no perder entrenamientos | 1–2 d | bajo |
| 3 | 3 Numba | 10–25× (estimado) → población y pistas mayores | 3–4 d | medio |
| 4 | 2 Separar control + Gymnasium | RL comparables, "interfaz estándar" ante empresas | 2 d | medio-bajo |
| 5 | 5 Harness + validación fija | resultados con IC, presentables | 2–3 d | bajo |
| 6 | 4 Paralelismo | ×5–7 adicional en 8 núcleos | 2 d | medio |
| 7 | 6 Paquete, tipado, CI | percepción profesional | 1–2 d | bajo |

(La Fase 2 puede ir antes que la 3 si el panel prioriza RL. Yo pongo numba primero porque reduce el costo de todos los experimentos posteriores.)

---

## 4. Qué NO cambiar
1. **El modelo físico y sus constantes** (config.py, fisica.py). Cualquier refactor de rendimiento debe pasar la regresión dorada (numpy, exacto) o la estadística (numba). Ningún "arreglo" de física se mezcla con un cambio de rendimiento en el mismo commit.
2. **`SUBPASOS = 6`** (el mínimo estable) y `DT_CONTROL = 1/30`. Numba no es excusa para bajar subpasos. Si sobra rendimiento, se puede *subir* para medir convergencia temporal (test: aptitudes con 6 contra 12 subpasos estadísticamente iguales).
3. **El ruido CRN escalar por paso** (fisica.py:192-193): es la razón por la que la comparación entre individuos es justa y por la que se puede paralelizar sin cambiar resultados. En el backend numba se precomputa con el mismo generador.
4. **La re-evaluación de la élite en pistas nuevas cada generación** (evolucion.py:202-204, 235) y el currículo por niveles.
5. **Los comandos de `main.py`, el `.bat`, los nombres `mejor_moto.json`/`poblacion.npz`/`historial.csv` y sus variantes `_ciudad`.** Los formatos nuevos son superconjuntos que se leen hacia atrás.
6. **La GUI tkinter y su estética** (interfaz.py, graficos.py, planificador.py). Solo extraería la lógica de entrenamiento a un hilo y la haría probable en *smoke tests*; no la reescribiría ni la migraría a otro framework.
7. **numpy como dependencia obligatoria única** (más pillow). numba, gymnasium y SB3 son siempre opcionales con *fallback*.
8. **La compactación de arreglos (`_quedarse`)** en la ruta del GA con numpy: es una optimización válida. Solo se desactiva para la API vectorizada.

---

## 5. Puntos para el debate con los demás agentes
- Si el agente de algoritmos propone CMA-ES/ES de Salimans o poblaciones grandes, **depende de la Fase 3**: con numpy puro, 400 motos × 6 pistas ≈ 40–60 s por generación; con numba, ≈ 2–5 s (estimado).
- Si el agente de física propone más subpasos o un integrador semi-implícito, la Fase 0 (regresión dorada) debe existir antes. El costo por subpaso con numba haría asumible subir a 8–12.
- La API Gymnasium hace falta para que el proyecto sea comparable contra una línea base estándar (PPO). Sin ella, la afirmación "la neuroevolución funciona" no tiene contra qué compararse.

Referencias consultadas: [Gymnasium — Vector API](https://gymnasium.farama.org/api/vector/), [Farama — Deep Dive: VectorEnv Autoreset](https://farama.org/Vector-Autoreset-Mode), [gymnasium.vector.vector_env (código)](https://gymnasium.farama.org/_modules/gymnasium/vector/vector_env), [SB3 — Custom Environments](https://stable-baselines3.readthedocs.io/en/v2.7.0/_sources/guide/custom_env.rst.txt), [SB3 — Env Checker](https://stable-baselines3.readthedocs.io/en/v2.1.0/common/env_checker.html), [Gymnasium env_checker](https://gymnasium.farama.org/_modules/gymnasium/utils/env_checker/).
