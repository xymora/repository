# R1 — Agente 2: Aprendizaje automático, neuroevolución y RL

**Rol:** investigador (nivel doctorado) en neuroevolución, estrategias evolutivas y aprendizaje por refuerzo.
**Alcance:** diagnóstico de `evolucion.py`, `red.py`, `config.py`, `main.py` y de la interfaz de aprendizaje de `fisica.py` (observación y aptitud), más una propuesta priorizada con diseño experimental. No modifiqué archivos del proyecto.

---

## 0. Medición previa: ¿dónde está el costo?

Antes de proponer nada medí el simulador (población aleatoria, sin GUI):

| Caso | Tiempo |
|---|---|
| 1 moto, 300 pasos de control (nivel 5) | 0.456 s |
| 80 motos, 300 pasos de control (nivel 5) | 0.782 s |
| Pista completa de 80 motos (niv. 1 / niv. 5, aleatorias) | 1.26 s / 0.99 s |

**Conclusión clave:** el costo lo domina el *overhead* de Python por paso (~1.5 ms/paso), no el número de motos. Pasar de 1 a 80 motos solo multiplica el tiempo por 1.7. Por eso:

1. **Una población más grande sale casi gratis** (80 → 256 debería costar ~1.3–1.5×). Hoy el algoritmo está limitado sin necesidad.
2. **Paralelizar repartiendo la población entre procesos es mala idea** (cada proceso paga el overhead completo). Lo correcto es **paralelizar por pista** (y por semilla experimental): con 8 núcleos se pueden evaluar 6–8 pistas por generación en el mismo tiempo de reloj que hoy cuestan 1–2.

---

## 1. Diagnóstico del algoritmo actual (con líneas)

**D1. La sigma de mutación nunca baja de su valor inicial** — `evolucion.py:230-233`:
`self.sigma = max(self.sigma * 0.97, C.SIGMA_MUTACION)`. La sigma vive en [0.20, 0.40] para siempre, así que no hay fase de ajuste fino. Además 0.20 es **mayor que la escala de los pesos** de la capa de entrada (`red.py:37`, σ_init = 1/√35 ≈ 0.17) y similar a la de la capa oculta (1/√20 ≈ 0.22). Cada gen mutado se perturba en ~100 % de su magnitud típica. Ningún método moderno (CMA-ES, ES de Salimans, PGPE) mantiene un paso fijo y grande. Encima, la sigma no se guarda en `poblacion.npz` (`evolucion.py:125`), así que se pierde al reanudar.

**D2. El cruce uniforme entre MLP no emparentados es destructivo** — `evolucion.py:240-243`. Es el problema de las "convenciones en competencia" (permutation problem): dos redes equivalentes con neuronas ocultas permutadas producen hijos sin sentido. NEAT lo resolvió con marcas históricas (Stanley & Miikkulainen, 2002), y Such et al. (2017) mostraron que un GA **sin cruce**, solo con mutación gaussiana, es competitivo en redes profundas. Con `PROB_CRUCE = 0.7`, ~70 % de la descendencia sale de un operador que, sin alineamiento, se porta casi como una macro-mutación.

**D3. La aptitud es muy ruidosa y se estima con solo 3 pistas** — `config.py:472`, `evolucion.py:196`. La selección por torneo (`:191-193`) y la élite (`:235`) usan la media de 3 pistas aleatorias, con perturbaciones estocásticas (`fisica.py:192-193`). Con 80 individuos el líder es el *máximo de 80 variables ruidosas*: hay un sesgo optimista claro (maldición del ganador; Jin & Branke, 2005). Lo bueno: la élite se reevalúa en pistas nuevas cada generación, así que no arrastra aptitudes viejas.

**D4. El criterio para subir de nivel es frágil y sesgado** — `evolucion.py:213-217`, `RACHA_PARA_SUBIR = 2`. Basta que el *argmax* termine 3/3 pistas dos generaciones seguidas. El `historial.csv` lo confirma: en la gen. 1 un individuo aleatorio ya terminó 3/3 (66 km/h), subió al nivel 2 en la gen. 3 y la aptitud media cayó a −93 con 0 % de llegadas. Un criterio que mira a un solo individuo con n = 3 tiene una tasa de falsos positivos alta y no dice nada de la robustez.

**D5. El "mejor" guardado es el líder ruidoso de cada generación** — `evolucion.py:119-124`. `mejor_moto.json` se sobrescribe en cada generación con el argmax sobre 3 pistas, sin validar contra un conjunto fijo de pistas reservadas. La moto que se presenta puede ser peor que una de hace 50 generaciones.

**D6. Los inmigrantes aleatorios desperdician evaluaciones** — `evolucion.py:237, 249-250`. En niveles ≥ 2 un MLP aleatorio no compite nunca (su aptitud es ≈ −60) y muere en el primer torneo: es 4 % del presupuesto sin aporte de diversidad real. La diversidad útil viene del espacio de **comportamientos** (Novelty Search / QD), no de pesos al azar.

**D7. La adaptación de sigma usa una señal que no es estacionaria** — `evolucion.py:229-230`. Compara la media de "mejor" entre ventanas de 10 generaciones, pero las pistas cambian en cada generación y "mejor" es un máximo ruidoso. La regla reacciona a ruido.

**D8. La aptitud mezcla escalas y castigos** — `fisica.py:463-476`. Progreso (0–100) + llegada (50) + rapidez (≤150) − carril − balanceo − invasión − 20·errores. Hay un salto discontinuo de +50 a +200 al cruzar la meta: es un paisaje engañoso (deceptive), con una meseta antes de la meta. Para el GA la escala da igual porque el torneo es invariante a rango. **Para ES/CMA sí importa**, y por eso hay que usar *fitness shaping* por rangos centrados (Salimans et al., 2017; Wierstra et al., NES).

**D9. Política reactiva sin memoria** — `red.py:22-26`. Es un MLP 35-20-3 tanh sin recurrencia y sin la acción previa como entrada. La observación (`fisica.py:149-181`) es rica y casi markoviana (incluye tasas como `incld`, `om` y `vy`), así que **no** veo la recurrencia como cuello de botella principal. Sí conviene estudiarla en una ablación (hielo, saltos y la latencia del filtro `TAU_DIRECCION`).

**D10. No hay protocolo experimental** — `main.py:534-553`. Una sola corrida, sin semilla obligatoria (`--semilla` es opcional), sin conjunto de prueba, sin varias semillas ni intervalos de confianza. Ante una empresa o un comité, la pregunta "¿cuánto de esto es suerte?" hoy no tiene respuesta.

**D11. Transferencia terreno → calles sin repaso** — `evolucion.py:95-103`. Al graduarse, toda la población pasa a ciudad y las pistas de terreno desaparecen, con riesgo de olvido catastrófico. Los niveles de terreno sí acumulan rasgos (`terreno.py:48-56`, buen diseño), pero ciudad y terreno no se mezclan.

---

## 2. Estado del arte relevante (resumen crítico)

- **ES de Salimans** (Salimans et al., 2017, arXiv:1703.03864): estima el gradiente de la aptitud suavizada con perturbaciones gaussianas antitéticas, *fitness shaping* por rangos, Adam y *weight decay*. Escala casi linealmente con CPUs y en MuJoCo es competitivo con TRPO. Le falta mecanismo de exploración dirigida.
- **NES** (Wierstra et al., 2014, arXiv:1106.4487): marco teórico con gradiente natural. ES de Salimans es un caso particular de covarianza isotrópica.
- **CMA-ES** (Hansen, tutorial arXiv:1604.00772): adapta la covarianza completa y el paso por *cumulative step-size adaptation*. Es el estándar en caja negra para unas pocas decenas o cientos de parámetros. Nuestra red tiene **783 parámetros** (35·20+20+20·3+3); la covarianza completa (783² ≈ 613 k elementos, O(n³) cada eigendescomposición) es viable pero lenta en adaptación. **sep-CMA-ES** (Ros & Hansen, PPSN 2008) usa covarianza diagonal, O(n), y aprende más rápido en dimensión alta: es la elección natural aquí.
- **PGPE** (Sehnke et al., 2010, *Neural Networks* 23(4)): ES diagonal con muestreo simétrico y adaptación de σ por parámetro. En la práctica rinde parecido a sep-CMA y es muy simple de implementar en numpy (~40 líneas).
- **ARS** (Mania et al., 2018, arXiv:1803.07055): búsqueda aleatoria con normalización de estados; políticas *lineales* resuelven locomoción MuJoCo. Es un baseline obligatorio y barato: si una política lineal llega igual de lejos, el MLP no aporta.
- **Deep Neuroevolution / GA** (Such et al., 2017, arXiv:1712.06567): un GA simple solo con mutación y truncamiento compite con DQN/A3C/ES en Atari. Justifica mantener el GA como baseline, pero **sin cruce uniforme**.
- **NEAT / HyperNEAT** (Stanley & Miikkulainen, 2002, *Evol. Comput.* 10(2); Stanley et al., 2009, *Artificial Life* 15(2)): evolucionan la topología, con especiación y marcas históricas. Para un control de 35 entradas y topología fija aportan poco frente a su complejidad. Conviene **citarlos, no adoptarlos**.
- **Novelty Search** (Lehman & Stanley, 2011, *Evol. Comput.* 19(2)) y **NS-ES / NSR-ES** (Conti et al., 2018, arXiv:1712.06560): premian la novedad del comportamiento, útil en paisajes engañosos como el escalón de la meta (D8). NSR-ES (recompensa + novedad) es la variante práctica.
- **MAP-Elites / Quality-Diversity** (Mouret & Clune, 2015, arXiv:1504.04909; Cully et al., 2015, *Nature* 521, arXiv:1407.3501): un archivo de élites por celdas de un descriptor de comportamiento. Da un **repertorio** de estilos de manejo (agresivo/conservador, carril/velocidad). Es muy vistoso para presentar y sirve de adaptación rápida a daños.
- **POET / Enhanced POET** (Wang et al., 2019, arXiv:1901.01753; 2020, arXiv:2003.08536): co-evolucionan entornos y agentes con transferencia entre parejas, usando ES como optimizador interno. El generador procedural de `terreno.py` está parametrizado justo como el "BipedalWalkerHardcore" de POET (rugosidad, troncos, escalones, zanjas), así que es un análogo directo y defendible.
- **PAIRED** (Dennis et al., 2020, arXiv:2012.02096) y **PLR / Robust PLR** (Jiang et al., 2020, arXiv:2010.03934; 2021, arXiv:2110.02439): currículos automáticos por *regret*. PLR re-muestrea niveles (semillas) con alto potencial de aprendizaje. Su versión evolutiva es barata: guardar semillas de pista con alta varianza o baja tasa de éxito y re-muestrearlas con prioridad.
- **Currículo y DR**: revisión de Narvekar et al. (2020, JMLR, arXiv:2003.04960); *Domain Randomization* (Tobin et al., 2017, arXiv:1703.06907); *Automatic DR* (Akkaya et al., 2019, arXiv:1910.07113). La ADR amplía rangos de parámetros físicos cuando el rendimiento supera un umbral: es una generalización continua del currículo de 8 niveles.
- **RL con gradiente**: PPO (Schulman et al., 2017, arXiv:1707.06347) y SAC (Haarnoja et al., 2018, arXiv:1801.01290) son el estándar en locomoción. Suelen ser más eficientes en muestras; ES/GA son más eficientes en reloj con CPUs, más robustos al horizonte largo y a recompensas dispersas, y triviales de paralelizar (Salimans 2017, §4). Un comparativo con PPO pide PyTorch (dependencia pesada), así que lo dejo como trabajo futuro opcional, no como prioridad.
- **Redes recurrentes/continuas**: LTC (Hasani et al., 2020, arXiv:2006.04439) y Neural Circuit Policies (Lechner et al., 2020, *Nat. Mach. Intell.*) son controladores compactos e interpretables que se evolucionan bien. Una CTRNN o una GRU mínima es una ablación interesante.
- **JAX**: EvoJAX (Tang et al., 2022, arXiv:2202.05008) y evosax (Lange, 2022, arXiv:2212.04180) ofrecen más de 30 estrategias con API *ask-evaluate-tell*. Usarlos exigiría reescribir la física en JAX, que es costoso. Recomiendo **copiar su API ask/tell en numpy**, no adoptar la librería.
- **Rigor estadístico**: Henderson et al. (2018, arXiv:1709.06560, "Deep RL that Matters"), Colas et al. (2018, arXiv:1806.08295, "How many random seeds?") y Agarwal et al. (2021, arXiv:2108.13264, "rliable": IQM, IC bootstrap estratificado, perfiles de desempeño).

---

## 3. Propuestas priorizadas

Formato: **qué / por qué / cómo / archivo / riesgo / esfuerzo**. Todas usan solo numpy (y `multiprocessing` de la librería estándar).

### P1 (crítica). Protocolo de evaluación con pistas reservadas y "campeona validada"
- **Qué:** un conjunto fijo de pistas de **prueba** por nivel (p. ej. 20 semillas reservadas, disjuntas de las de entrenamiento) y otro de **validación** (10 semillas).
- **Por qué:** corrige D3, D5 y D10. Es la base de cualquier afirmación cuantitativa.
- **Cómo:** cada K = 10 generaciones (o al subir de nivel) se evalúan el top-5 de la élite en validación. `mejor_moto.json` solo se reemplaza si la nueva supera a la guardada en validación. Al cerrar se reporta en **prueba**: tasa de éxito, velocidad media de llegada, errores por km e invasión de carril. Las semillas reservadas se toman de un rango aparte (p. ej. `10**9 + i`) para que nunca coincidan con `rng.integers(1<<30)`.
- **Archivo:** nuevo `experimentos.py` (evaluador puro, sin GUI) más un gancho mínimo en `evolucion.py:_guardar`.
- **Riesgo:** bajo. Cuesta unos segundos extra cada 10 generaciones.
- **Esfuerzo:** 0.5–1 día.

### P2 (crítica). Evaluación paralela por pista y más pistas por generación
- **Qué:** `multiprocessing.Pool(processes=min(8, n_pistas))`. Cada trabajador recibe `(nivel, semilla_pista, pesos)` y devuelve `aptitud`, `llegadas` y `t_fin`.
- **Por qué:** por la medición de §0, el paralelismo útil es por pista. Con 6–8 pistas por generación el ruido de la estimación (D3) baja ~√(8/3) ≈ 1.6× sin costo de reloj.
- **Cómo:** solo en el modo `--sin-gui` (la GUI conserva `avanzar()` paso a paso para animar). En Windows hay que usar `if __name__ == "__main__"` (ya existe en `main.py:119`) y pasar semillas, no objetos `Pista`. La serialización de `RedVial` en modo ciudad se resuelve con un `initializer` del pool que la carga una vez por proceso. Las semillas de ruido (`fisica.py:69`) se mantienen por pista, así que el resultado es **determinista e idéntico** al secuencial, y eso se puede verificar con una prueba.
- **Archivo:** `evolucion.py` (método `evaluar_paralelo`) y `main.py:entrenar_consola`.
- **Riesgo:** medio-bajo (en Windows el arranque de procesos cuesta ~1 s; el pool se reutiliza).
- **Esfuerzo:** 1 día.

### P3 (alta). Optimizador intercambiable con API ask/tell: GA corregido, sep-CMA-ES / PGPE y ES de Salimans
- **Qué:** una clase base `Optimizador` con `pedir() -> (N, P)` y `informar(aptitudes)`, y tres implementaciones:
  1. **GA-v2** (baseline mejorado): sin cruce uniforme (o cruce solo entre élites emparentadas), mutación gaussiana de **todos** los genes con σ relativa a la escala de la capa, **σ autoadaptativa** por individuo (regla log-normal de las ES clásicas: σ' = σ·exp(τ·N(0,1)), τ = 1/√(2√P)) y truncamiento al top-20 %.
  2. **sep-CMA-ES** (Ros & Hansen 2008) o **PGPE** (Sehnke 2010): covarianza diagonal y σ por parámetro, ~80–120 líneas de numpy, λ = 64–128 con muestreo espejado.
  3. **ES de Salimans** (Salimans 2017): perturbaciones antitéticas, rangos centrados, Adam, *weight decay* y σ ≈ 0.02–0.05.
- **Por qué:** D1, D2 y D7. CMA/PGPE adaptan el paso de forma fundamentada (CSA). Por la §0, λ = 128 cuesta poco más que 80.
- **Cómo:** `config.OPTIMIZADOR = "ga" | "sepcma" | "pgpe" | "oes"`. El `Entrenador` solo llama a `pedir`/`informar`. Hay que conservar la decisión del usuario **"campeona en la posición 0 re-corre las pistas"**: en ES se inyecta la media θ (o la mejor validada) como individuo 0 evaluado pero **excluido** de la actualización del gradiente/covarianza, para no sesgarla. Para CMA, la "élite" equivalente es la media de la distribución.
- **Archivo:** nuevo `optimizadores.py`; `evolucion.py:_evolucionar` se reduce a pedir/informar más el currículo.
- **Riesgo:** medio. Las ES pueden progresar más lento al inicio de cada nivel si σ quedó pequeña; se mitiga reiniciando σ al subir de nivel (IPOP-style; Auger & Hansen, 2005).
- **Esfuerzo:** 2–3 días con pruebas unitarias en funciones de prueba (esfera, Rastrigin) antes de usarlo en la moto.

### P4 (alta). Criterio de subida de nivel estadístico y currículo con repaso (PLR-lite)
- **Qué:** (a) subir de nivel cuando la **campeona validada** tenga una tasa de éxito ≥ 80 % en las pistas de validación del nivel, con cota inferior de Wilson al 95 % ≥ 0.6, en lugar de "argmax 3/3 dos veces". (b) En cada generación, 25 % de las pistas vienen de **niveles anteriores** (repaso contra el olvido) y 25 % de un **búfer de pistas difíciles**: semillas donde la población tuvo éxito parcial, con prioridad por la varianza de la aptitud entre individuos, que es el análogo evolutivo del "potencial de aprendizaje" de PLR (Jiang et al., 2020).
- **Por qué:** D4 y D11. Mantiene la **graduación automática terreno → calles** que pidió el usuario, solo la hace confiable. En ciudad se aplica igual: 20 % de pistas de terreno nivel 8 como repaso.
- **Archivo:** `evolucion.py:_preparar_generacion` y `:212-225`.
- **Riesgo:** bajo-medio (el currículo será más lento, pero honesto).
- **Esfuerzo:** 1 día.

### P5 (media). Aptitud: conservar los términos y reportarlos desagregados
- **Qué:** no cambiar la función de aptitud del usuario (premio por rapidez, −20 por error, regreso 2 s). Sí guardar sus **componentes por separado** (progreso, llegada, rapidez, carril, balanceo, invasión y errores) y, para las ES, usar transformación por rangos centrados.
- **Por qué:** D8. La escala deja de importar y los componentes permiten analizar *trade-offs* (velocidad contra seguridad) y construir el descriptor QD de P7.
- **Archivo:** `fisica.py:463` (devolver un dict además del escalar) e `historial.csv` (columnas nuevas).
- **Riesgo:** bajo. **Esfuerzo:** 0.5 día.

### P6 (media). Arquitectura: ablación MLP contra lineal contra recurrente
- **Qué:** tres variantes en `red.py` con la misma interfaz: lineal (35→3), MLP actual (35-20-3) y **Elman/GRU mínima o CTRNN** de 12 neuronas, con la acción previa como entrada.
- **Por qué:** D9, y es la ablación que pide cualquier revisor ("¿hace falta la red?", siguiendo a Mania et al. 2018). Si la lineal llega al nivel 4–5 es un hallazgo publicable, no un fracaso.
- **Cómo:** hoy `R.adelante` no tiene estado; para la recurrente, `Simulador` guardaría `h` (N × H) y lo incluiría en `_ESTADO` para que el regreso de 2 s restaure también la memoria. **Este detalle es indispensable para la coherencia con la regla de reintentos.**
- **Archivo:** `red.py`, `fisica.py:188-190, 36-38`.
- **Riesgo:** medio (la recurrente complica el `_quedarse` y las fotos). **Esfuerzo:** 1.5 días.

### P7 (media, alto valor de presentación). Quality-Diversity: MAP-Elites o NSR-ES
- **Qué:** un archivo MAP-Elites 2D con descriptor (velocidad media de llegada normalizada, desviación media del carril) o (fracción de tiempo frenando, inclinación media), de 10 × 10 celdas.
- **Por qué:** produce un **repertorio** de conductores (de "chofer prudente" a "piloto agresivo") que se puede mostrar en un mapa de calor. Es diversidad real, que reemplaza a los inmigrantes aleatorios (D6), y ayuda a cruzar la meseta engañosa de la meta (Lehman & Stanley 2011; Conti et al. 2018).
- **Cómo:** modo opcional `--qd`, que reusa el evaluador paralelo de P2. La selección se hace uniforme sobre celdas ocupadas, con mutación gaussiana (y el operador *iso+line*, Vassiliades & Mouret 2018, arXiv:1804.03906).
- **Archivo:** nuevo `qd.py` más una gráfica en `graficos.py`.
- **Riesgo:** bajo (es un modo aparte). **Esfuerzo:** 1.5–2 días.

### P8 (media-baja). *Domain randomization* física y prueba de robustez
- **Qué:** al evaluar, muestrear por pista multiplicadores en ±10–20 % de `MASA_CHASIS`, `PAR_MOTOR`, mu del material, `TAU_DIRECCION` y `PERTURBACION` (Tobin 2017), y medir la tasa de éxito en prueba **fuera de distribución** (p. ej. mu × 0.8).
- **Por qué:** es la pregunta de una empresa: "¿qué pasa si la llanta está gastada?". Una curva de robustez con y sin DR vale más que cualquier demo.
- **Cómo:** hoy `fisica.py` lee constantes globales de `config`, así que habría que pasar un vector de parámetros (N o escalar por pista) al `Simulador`. Con un escalar por pista basta, y es poco invasivo.
- **Archivo:** `fisica.py` (constructor y unos 6 usos). **Riesgo:** medio (toca la física; coordinarlo con el agente de dinámica). **Esfuerzo:** 1 día.

### P9 (baja; opcional). numba para el paso de física
Compilar `_fisica` con `@njit` en bucle explícito por moto podría bajar el overhead por paso 5–20× y hacer viables poblaciones de 500+ y 16 pistas. Es invasivo y cuesta mantenerlo. Solo vale la pena si P2 no basta.

---

## 4. Diseño experimental (lo que convierte esto en tesis)

**Preguntas de investigación**
- **RQ1:** ¿qué optimizador (GA actual, GA-v2, sep-CMA/PGPE, ES de Salimans) llega más lejos en el currículo con el mismo presupuesto de evaluaciones?
- **RQ2:** ¿el currículo (y el repaso/PLR-lite) mejora la generalización frente a entrenar directo en el nivel 8?
- **RQ3:** ¿cuánto aportan la capa oculta y la recurrencia?
- **RQ4:** ¿qué tan robusta es la política a cambios físicos (OOD) con y sin DR?

**Baselines obligatorios**
1. GA actual (tal cual, como referencia histórica).
2. Búsqueda aleatoria pura (mismo número de evaluaciones).
3. ARS/política lineal.
4. Un controlador heurístico escrito a mano (PD sobre `lat`, velocidad objetivo = `v_segura`). Da una referencia de "ingeniería clásica" que las empresas entienden.

**Ablaciones (una cosa a la vez)**
- Con/sin cruce.
- σ fija contra autoadaptativa.
- 3 contra 8 pistas por generación.
- Con/sin currículo.
- Con/sin repaso.
- MLP contra lineal contra recurrente.
- Con/sin DR.
- Con/sin la regla de regreso de 2 s, **solo en evaluación**: se mide el éxito "sin segundas oportunidades" como métrica de seguridad, y el entrenamiento conserva la regla del usuario.

**Presupuesto y semillas**
- Presupuesto fijo en **evaluaciones de episodio** (p. ej. 3×10⁵) y también en tiempo de reloj. Ambos se reportan.
- **≥ 10 semillas** por condición (Colas et al. 2018 muestran que 5 suelen no bastar para detectar diferencias medianas; idealmente 20 en la comparación principal).
- Con 8 núcleos y P2, las semillas se paralelizan entre procesos. El usuario lanza el lote, con un script `experimentos.py --condicion X --semillas 0-9` que escribe un CSV por corrida.

**Métricas**
- Tasa de éxito en prueba por nivel (las 20 pistas reservadas).
- Nivel máximo alcanzado.
- **Área bajo la curva** nivel/éxito contra evaluaciones.
- Velocidad media de llegada.
- Errores por km.
- Invasión de carril.
- Éxito OOD.
- Para ciudad: éxito en rutas OSM reservadas de **otra zona** (generalización geográfica).

**Estadística**
- Curvas con la media (o el IQM, Agarwal 2021) e **IC 95 % por bootstrap** (10 000 remuestreos sobre semillas).
- Comparaciones de pares con **Mann-Whitney U** (no paramétrica) más el tamaño de efecto **A12 de Vargha-Delaney** o Cliff's δ.
- Corrección de **Holm-Bonferroni** para comparaciones múltiples.
- Para tasas de éxito por política: IC de Wilson.
- Perfiles de desempeño (rliable).
- Todo con `scipy.stats` (`mannwhitneyu`, `bootstrap`), que ya está disponible.

**Reproducibilidad**
- Semilla obligatoria en modo experimento.
- Volcado de `config` y del commit/hash del código en cada CSV.
- Las pistas de prueba se identifican por semilla.
- Prueba unitaria de que la evaluación paralela coincide bit a bit con la secuencial.

---

## 5. Qué NO cambiar

1. **El simulador vectorizado por población** (`fisica.py`): es eficiente y correcto para ES/GA. No hay que reescribirlo en JAX.
2. **La aptitud con premio por rapidez, el castigo de −20 por error y el regreso de 2 s con máximo 3 reintentos**: son decisiones del usuario. Solo propongo desagregarla y medir además el éxito sin reintentos.
3. **La campeona en la posición 0 re-corriendo las mismas pistas**: es una buena práctica (evaluación con números aleatorios comunes y elitismo honesto). En ES se conserva como individuo testigo que no entra a la actualización.
4. **El currículo terreno → calles con graduación automática y niveles acumulativos** (`terreno.py:48-56`): solo hago más robusto el criterio (P4) y agrego repaso.
5. **El mínimo de 30 km/h y la física de estabilidad**: no son terreno de este agente.
6. **El ruido común por pista** (una sola `semilla_ruido` compartida por toda la población): da comparaciones justas y menor varianza. Hay que mantenerlo.
7. **El tamaño de la red (783 parámetros)**: es adecuado. Agrandarla sin evidencia de la ablación P6 solo complica las ES.
8. **La GUI paso a paso**: el paralelismo va solo en el modo consola o experimento.

---

## 6. Orden de implementación sugerido

**P1 → P2 → P5 → P3 (GA-v2 primero, luego sep-CMA/PGPE, luego ES de Salimans) → P4 → P6 → P7 → P8 → (P9).**

Con P1–P4 (≈ 5–6 días) el proyecto pasa de "demo que aprende" a "estudio comparativo reproducible con validación estadística", que es el umbral que una empresa o un comité doctoral exigen.

---

## Referencias

- Salimans, T. et al. (2017). *Evolution Strategies as a Scalable Alternative to Reinforcement Learning*. arXiv:1703.03864 — https://arxiv.org/abs/1703.03864
- Wierstra, D. et al. (2014). *Natural Evolution Strategies*. JMLR 15. arXiv:1106.4487 — https://arxiv.org/abs/1106.4487
- Hansen, N. (2016). *The CMA Evolution Strategy: A Tutorial*. arXiv:1604.00772 — https://arxiv.org/abs/1604.00772
- Ros, R. & Hansen, N. (2008). *A Simple Modification in CMA-ES Achieving Linear Time and Space Complexity*. PPSN X, LNCS 5199.
- Auger, A. & Hansen, N. (2005). *A Restart CMA Evolution Strategy with Increasing Population Size*. IEEE CEC 2005.
- Sehnke, F. et al. (2010). *Parameter-exploring policy gradients*. Neural Networks 23(4):551–559.
- Mania, H., Guy, A. & Recht, B. (2018). *Simple random search provides a competitive approach to RL*. arXiv:1803.07055 — https://arxiv.org/abs/1803.07055
- Such, F. P. et al. (2017). *Deep Neuroevolution: Genetic Algorithms Are a Competitive Alternative for Training Deep Neural Networks for RL*. arXiv:1712.06567 — https://arxiv.org/abs/1712.06567
- Conti, E. et al. (2018). *Improving Exploration in ES for Deep RL via a Population of Novelty-Seeking Agents*. arXiv:1712.06560 — https://arxiv.org/abs/1712.06560
- Stanley, K. O. & Miikkulainen, R. (2002). *Evolving Neural Networks through Augmenting Topologies*. Evolutionary Computation 10(2).
- Stanley, K. O., D'Ambrosio, D. & Gauci, J. (2009). *A Hypercube-Based Encoding for Evolving Large-Scale Neural Networks*. Artificial Life 15(2).
- Lehman, J. & Stanley, K. O. (2011). *Abandoning Objectives: Evolution Through the Search for Novelty Alone*. Evolutionary Computation 19(2).
- Mouret, J.-B. & Clune, J. (2015). *Illuminating search spaces by mapping elites*. arXiv:1504.04909 — https://arxiv.org/abs/1504.04909
- Cully, A., Clune, J., Tarapore, D. & Mouret, J.-B. (2015). *Robots that can adapt like animals*. Nature 521. arXiv:1407.3501 — https://arxiv.org/abs/1407.3501
- Vassiliades, V. & Mouret, J.-B. (2018). *Discovering the Elite Hypervolume by Leveraging Interspecies Correlation*. arXiv:1804.03906 — https://arxiv.org/abs/1804.03906
- Wang, R. et al. (2019). *Paired Open-Ended Trailblazer (POET)*. arXiv:1901.01753 — https://arxiv.org/abs/1901.01753
- Wang, R. et al. (2020). *Enhanced POET*. ICML 2020. arXiv:2003.08536 — https://arxiv.org/abs/2003.08536
- Dennis, M. et al. (2020). *Emergent Complexity and Zero-shot Transfer via Unsupervised Environment Design (PAIRED)*. arXiv:2012.02096 — https://arxiv.org/abs/2012.02096
- Jiang, M., Grefenstette, E. & Rocktäschel, T. (2020). *Prioritized Level Replay*. arXiv:2010.03934 — https://arxiv.org/abs/2010.03934
- Jiang, M. et al. (2021). *Replay-Guided Adversarial Environment Design*. arXiv:2110.02439 — https://arxiv.org/abs/2110.02439
- Narvekar, S. et al. (2020). *Curriculum Learning for RL Domains: A Framework and Survey*. JMLR. arXiv:2003.04960 — https://arxiv.org/abs/2003.04960
- Tobin, J. et al. (2017). *Domain Randomization for Transferring Deep Neural Networks from Simulation to the Real World*. arXiv:1703.06907 — https://arxiv.org/abs/1703.06907
- Akkaya, I. et al. (2019). *Solving Rubik's Cube with a Robot Hand* (ADR). arXiv:1910.07113 — https://arxiv.org/abs/1910.07113
- Schulman, J. et al. (2017). *Proximal Policy Optimization Algorithms*. arXiv:1707.06347 — https://arxiv.org/abs/1707.06347
- Haarnoja, T. et al. (2018). *Soft Actor-Critic*. arXiv:1801.01290 — https://arxiv.org/abs/1801.01290
- Hasani, R. et al. (2020). *Liquid Time-constant Networks*. arXiv:2006.04439 — https://arxiv.org/abs/2006.04439
- Lechner, M. et al. (2020). *Neural circuit policies enabling auditable autonomy*. Nature Machine Intelligence 2.
- Tang, Y., Tian, Y. & Ha, D. (2022). *EvoJAX: Hardware-Accelerated Neuroevolution*. arXiv:2202.05008 — https://arxiv.org/abs/2202.05008
- Lange, R. T. (2022). *evosax: JAX-based Evolution Strategies*. arXiv:2212.04180 — https://arxiv.org/abs/2212.04180
- Jin, Y. & Branke, J. (2005). *Evolutionary Optimization in Uncertain Environments — A Survey*. IEEE Trans. Evol. Comput. 9(3).
- Henderson, P. et al. (2018). *Deep Reinforcement Learning that Matters*. arXiv:1709.06560 — https://arxiv.org/abs/1709.06560
- Colas, C., Sigaud, O. & Oudeyer, P.-Y. (2018). *How Many Random Seeds? Statistical Power Analysis in Deep RL Experiments*. arXiv:1806.08295 — https://arxiv.org/abs/1806.08295
- Agarwal, R. et al. (2021). *Deep RL at the Edge of the Statistical Precipice* (rliable). arXiv:2108.13264 — https://arxiv.org/abs/2108.13264
