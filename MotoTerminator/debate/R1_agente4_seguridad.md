# Ronda 1 · Agente 4: seguridad funcional, robustez, sim-to-real y evaluación científica

**Rol:** soy el escéptico del panel. La pregunta que me toca es: *¿por qué el equipo de validación de una empresa real (automotriz, robótica, Tier-1) NO se creería hoy los resultados de MotoTerminator, y qué hay que hacer para que sí se los crea?*

**Veredicto corto:** el simulador está bien hecho y es rápido, y el currículo es elegante. Pero hoy lo que hay es una **demostración**, todavía no una **evaluación**. Tiene cinco problemas que un revisor encuentra en menos de una hora: (1) sensores omniscientes y sin retardo, (2) "llegar a la meta" se cuenta como éxito aunque la moto se haya estrellado hasta 3 veces y haya "viajado en el tiempo", (3) la aptitud premia cambiar choques por velocidad, (4) no hay un conjunto de prueba separado del de entrenamiento, y (5) ninguna métrica trae intervalo de confianza. Todo se arregla con numpy, sin tocar la arquitectura.

---

## 1. Marco normativo y científico (lo que un evaluador tiene en la cabeza)

| Referente | Qué exige o aporta | Relevancia aquí |
|---|---|---|
| **ISO 26262:2018** (seguridad funcional, fallas de E/E) | Fallas aleatorias y sistemáticas de hardware y software, ASIL | Poca de forma directa: aquí no hay hardware. Sirve de lenguaje para la arquitectura de *fallback*. |
| **ISO 21448:2022 SOTIF** | Riesgo **sin falla**: insuficiencias de especificación y de desempeño (percepción, ML) y escenarios "desconocidos-inseguros" | **Es la norma central para este proyecto**: la red no "falla", decide mal ante escenarios no vistos. |
| **UL 4600 (Ed. 3, 2023)** | *Safety case* de tipo afirmación-argumento-evidencia para productos autónomos, con métricas de desempeño de seguridad (SPI) y monitoreo | Plantilla para el reporte de seguridad automático (P8). |
| **ISO 34502:2022** | Evaluación de seguridad basada en escenarios para ADS ([iso.org/standard/78951](https://www.iso.org/standard/78951.html)) | Justifica la suite de escenarios parametrizados y la búsqueda en el espacio de parámetros. |
| **ASAM OpenSCENARIO 1.x/2.0** ([asam.net](https://www.asam.net/standards/detail/openscenario/)) | Formato estándar de escenarios | Exportar los escenarios críticos con una estructura parecida (JSON) los hace legibles para la industria. |
| **Kalra & Paddock (2016)**, *Driving to Safety*, Transp. Res. A 94:182-193, DOI 10.1016/j.tra.2016.09.010 ([informe RAND](https://ivds.dependability.org/wg10.4/ivdswiki/images/7/72/Rand_report-Miles_to_demo_failure_rate.pdf)) | Probar fiabilidad solo acumulando kilómetros es estadísticamente inviable. Hacen falta pruebas aceleradas y por escenarios | Hay que reportar **fallas/km con IC** y declarar cuántas pruebas harían falta para cada afirmación. |
| **Koopman & Wagner (2016)**, SAE Int. J. Transp. Safety, DOI 10.4271/2016-01-0128 | Retos de validar sistemas con ML: el entrenamiento como especificación implícita | Mismo diagnóstico de "la aptitud es la especificación". |
| **Maler & Nickovic (2004)**, STL, DOI 10.1007/978-3-540-30206-3_12; **Donzé & Maler (2010)**, robustez de STL, FORMATS, LNCS 6246:92-106, DOI 10.1007/978-3-642-15297-9_9 | Requisitos temporales formales con semántica cuantitativa ρ (margen de cumplimiento) | Monitores de requisitos (P5) y objetivo de la falsificación (P6). |
| **S-TaLiRo** (Annpureddy et al., TACAS 2011, DOI 10.1007/978-3-642-19835-9_21); **Breach** (Donzé, CAV 2010, DOI 10.1007/978-3-642-14295-6_17) | Falsificación: minimizar ρ sobre el espacio de entradas o escenarios | P6. |
| **Corso et al. (2021)**, *Survey of Algorithms for Black-Box Safety Validation of CPS*, JAIR 72:377-428, DOI 10.1613/jair.1.12716 ([jair.org](https://jair.org/index.php/jair/article/view/12716)) | Tres tareas distintas: falsificación, falla más probable y **estimación de la probabilidad de falla** | Estructura de P6. |
| **Lee et al. (2020)**, *Adaptive Stress Testing*, JAIR 69, DOI 10.1613/jair.1.12190 | Búsqueda de la secuencia de perturbaciones de falla más probable | Variante de P6. |
| **Feng et al. (2023)**, *Dense RL for safety validation of AVs*, Nature 615:620-627, DOI 10.1038/s41586-023-05732-2; **Zhao et al. (2017)**, evaluación acelerada por *importance sampling*, IEEE T-ITS, DOI 10.1109/TITS.2016.2582208 | Estimación insesgada de eventos raros con muchas menos pruebas | Estimador de P(falla) en P6. |
| **Sha (2001)**, *Using Simplicity to Control Complexity* (Simplex), IEEE Software, DOI 10.1109/MS.2001.936213 | Controlador complejo + controlador simple verificado + monitor de conmutación | P7. |
| **Ames et al. (2019)**, *Control Barrier Functions: Theory and Applications*, ECC, arXiv:1903.11199; **Alshiekh et al. (2018)**, *Safe RL via Shielding*, AAAI, arXiv:1708.08611 | Filtros de seguridad mínimamente invasivos | P7. |
| **Tobin et al. (2017)** domain randomization, IROS, arXiv:1703.06907; **Peng et al. (2018)** dynamics randomization, ICRA, arXiv:1710.06537 | Randomizar la dinámica y los sensores para cerrar la brecha sim2real | P3/P4. |
| **Cobbe et al. (2020)**, Procgen, ICML, arXiv:1912.01588 | Con generación procedural hay que separar niveles de entrenamiento y de prueba para medir generalización | P1. |
| **Agarwal et al. (2021)**, *Deep RL at the Edge of the Statistical Precipice*, NeurIPS, arXiv:2108.13264 | Varias semillas de entrenamiento, IQM e IC por bootstrap | P9. |
| **Amodei et al. (2016)**, *Concrete Problems in AI Safety*, arXiv:1606.06565 | *Reward hacking* y especificación incompleta | Diagnóstico de la aptitud. |
| **Meijaard et al. (2007)**, benchmark de la bicicleta de Whipple, Proc. R. Soc. A 463:1955-1982, DOI 10.1098/rspa.2007.1857; **Sharp (1971)**, J. Mech. Eng. Sci. 13(5) | Modelos lateral y de dirección de referencia (modos *weave*, *wobble*, *capsize*) | Validar o acotar el modelo lateral fenomenológico (P10). |
| **Shalev-Shwartz et al. (2017)**, RSS, arXiv:1708.06374 | Distancias seguras formalizadas | Inspiración para requisitos de margen (TTC/TLC). |

---

## 2. Diagnóstico: qué falla hoy (con líneas)

### D1. Percepción omnisciente, perfecta y sin retardo (brecha sim2real n.º 1)
- `fisica.py:135` el "lidar" lee la altura **exacta** del mapa (`p.altura`), sin ruido, oclusión ni resolución.
- `fisica.py:140-148` la red recibe la **curvatura futura exacta** (k1..k3) y una **`v_segura` ya calculada** con la curvatura máxima de los próximos 40 m y el agarre mínimo futuro (`p.kmax`, `p.mu_min`). Eso es un **oráculo**: la parte difícil del problema, que es saber qué tan rápido entrar, viene resuelta dentro de una entrada (`fisica.py:178`).
- `fisica.py:172-174` la "cámara" da el μ **verdadero** del material, aquí y 5 m adelante. En la realidad estimar μ es uno de los problemas abiertos más duros. Si se percibe mal (hielo negro), cae justo en el núcleo de SOTIF.
- `fisica.py:159-161` la posición lateral `lat` y el rumbo relativo `psi` son exactos, sin error de GNSS o visión.
- `fisica.py:190`: `observar()` se calcula y se aplica **en el mismo paso** (latencia cero). Solo la dirección tiene dinámica (`fisica.py:318-320`, τ = 0.15 s y límite de velocidad). Acelerador, freno y par de cabeceo actúan instantáneamente (`fisica.py:274-306`).

**Consecuencia:** una política que depende de entradas privilegiadas puede desplomarse con 50-100 ms de retardo o con 10 % de error en μ. Hoy nadie puede afirmar lo contrario porque nunca se ha medido.

### D2. El éxito incluye choques "corregidos" viajando en el tiempo
- `fisica.py:398-402`: ante una caída, salida, vuelco o choque, la moto **regresa 2 s** y sigue, hasta 3 veces.
- `evolucion.py:172` cuenta `llegadas = motivo == META` **sin mirar `reintentos`**. `evolucion.py:213` sube de nivel con esas llegadas. `resumen["llegaron"]` y `terminadas_lider` también.
- El README (`README.md:285`) afirma "8 de 8 sin errores". Aun si fuera estrictamente limpio, **8/8 da un IC de Clopper-Pearson al 95 % de [63 %, 100 %]**, y por la regla del tres la tasa de falla puede llegar a ~37 %. Ningún evaluador acepta "8 de 8" como evidencia de seguridad.

### D3. La aptitud es explotable: le conviene cambiar choques por velocidad
`fisica.py:463-476` y `config.py:110-117`:
- Llegar da 50 puntos, más un premio de rapidez de hasta 100 × 1.5 = 150. Cada error con reintento cuesta solo **20** (`CASTIGO_CHOQUE`).
- Pasar de 54 a 81 km/h de media vale +50 puntos, o sea **2.5 choques "gratis"**. El GA va a seleccionar políticas que arriesgan, porque el rebobinado convierte un choque en un *checkpoint* barato. Es *reward hacking* de manual (Amodei 2016). En la realidad, un choque no se compensa con rapidez.
- `fisica.py:474`: agotar el tiempo (`TIEMPO`) no recibe castigo, mientras que atascarse sí.
- Invadir el carril contrario es solo una penalización proporcional (`fisica.py:469`, `config.py:122`). No es una violación dura, porque no hay tráfico contra el cual chocar.
- **En calles reales** se premia lo mismo, hasta 81 km/h (`config.py:116-117`), **sin límite de velocidad**, sin intersecciones, semáforos, peatones ni otros vehículos (`calles.py:457-511`: asfalto plano, μ = 1, rugosidad × 0.5, esquinas suavizadas a ~14 m de radio en `calles.py:480`). El "modo ciudad" es un circuito de geometría real, no un escenario urbano. Así hay que decirlo para no perder credibilidad.

### D4. No hay separación entrenamiento/prueba y la selección está sesgada
- `evolucion.py:151-152`: cada generación usa 3 pistas nuevas. Eso evita memorizar, lo cual es bueno, pero **no existe una suite fija y reservada**. La aptitud que se guarda en `mejor_moto.json` (`evolucion.py:122`) es el máximo entre 80 medias ruidosas de 3 pistas, así que tiene **sesgo optimista por "maldición del ganador"**.
- `evolucion.py:153-154`: en modo ciudad, la ruta del usuario **siempre entra al entrenamiento**. Si luego se muestra esa misma ruta como resultado, se está evaluando sobre el conjunto de entrenamiento.
- La "graduación" (`evolucion.py:224`) se decide con 2 generaciones × 3 pistas = **6 pistas**, con reintentos permitidos.

### D5. El ruido es de una sola realización, compartida y blanca
- `fisica.py:192-193`: `self.ruido.normal()` devuelve **un escalar**, igual para las 80 motos y constante durante los 6 subpasos. Para *ordenar* individuos esto es correcto (números aleatorios comunes). Para *estimar* robustez no lo es: cada pista se prueba con **una sola** secuencia de perturbaciones, y la semilla del ruido es la de la pista (`evolucion.py:159,180`). El resultado es determinista por pista, así que no hay varianza Monte Carlo que reportar.
- Faltan ráfagas laterales correlacionadas (viento cruzado), baches que golpeen una sola rueda y fallas de sensor.

### D6. La física no está identificada ni validada contra referencias
- La dinámica lateral es fenomenológica: `estabilidad()` en `fisica.py:48-51`, el péndulo con `GIRO_W`/`GIRO_Z`, y el CMG con saturación heurística (`fisica.py:359-363`). No es el modelo de Whipple/Sharp ni sale de datos. **Eso es aceptable si se declara.** Lo que no se puede afirmar es transferencia sim2real. La afirmación honesta es *robustez ante variaciones del simulador* (y para eso existe P4).
- No hay pruebas de convergencia con respecto a `DT` ni pruebas unitarias de invariantes físicos. La estabilidad del integrador en el contacto se ve razonable: ω = √(150000/18) ≈ 91 rad/s, ω·dt ≈ 0.5 con Euler semi-implícito. Aun así hay que demostrarlo con una prueba, no suponerlo.

### D7. Métricas sin incertidumbre y de una sola semilla
`historial.csv` guarda `mejor`, `promedio` y `llegaron_%` de **una sola corrida de entrenamiento**. Faltan varias semillas, IC, tasa de fallas por km, tipos de falla, márgenes mínimos (TLC, el análogo del TTC sin otros agentes) y tasas por material o rasgo del terreno.

---

## 3. Propuestas priorizadas (todas en numpy y opcionales con banderas)

> Orden pensado para la máxima credibilidad por hora de trabajo. P1, P2 y P8 son el **mínimo publicable**. Ninguna exige reentrenar para *medir*. Sí hará falta reentrenar para *mejorar* después de P2, P3 y P4.

### P1. Suite de evaluación reservada con semillas fijas (`evaluacion.py`, nuevo). **Prioridad 1**
- **Qué:** un modo `python main.py --evaluar [--nivel k] [--ciudad]` que corra a la campeona sobre pistas que el entrenamiento nunca genera.
- **Cómo:** el entrenamiento usa semillas en `[0, 2³⁰)` (`evolucion.py:151`). La suite usa `semilla = 2³¹ + 1000·nivel + j`, disjuntas por construcción. Por nivel: **M = 200 pistas × K = 5 realizaciones de ruido**. Para que salga barato se aprovecha el lote: se replica la campeona K veces dentro de `Simulador` (`pesos = np.repeat(w[None], K, 0)`) y se agrega `ruido_por_moto=True`, que en `fisica.py:192-193` cambia a `self.ruido.normal(len(self.ids))`. Ese es el único cambio en `fisica.py` y no altera el entrenamiento si el valor por defecto queda en `False`.
- **Protocolo estricto:** en evaluación, `MAX_REINTENTOS = 0` (parámetro del simulador, no cambio global) y "éxito" significa **llegada limpia**.
- **Métricas:** tasa de llegada limpia con **IC de Clopper-Pearson** (`scipy.stats.beta.ppf`); **fallas por km** con IC exacto de Poisson (Garwood); desglose por `MOTIVOS` y por **rasgo/material** donde ocurrió la falla (cruzando `x` con `pista.secciones`); velocidad media; margen lateral mínimo; **TLC mínimo** (*time-to-line-crossing* = distancia al borde / velocidad lateral, el análogo del TTC mientras no haya tráfico); `cmg_sat` máximo.
- **Tamaño de muestra declarado:** para afirmar p_falla < 1 % al 95 % con cero fallas hacen falta n ≥ ln(0.05)/ln(0.99) ≈ **299** episodios. El reporte imprime qué afirmación permite el n usado.
- **Riesgo:** bajo. **Esfuerzo:** 1 día.

### P2. Separar "llegó" de "llegó sin errores" y cerrar el hueco de la aptitud (`evolucion.py`, `fisica.py:aptitud`). **Prioridad 1**
- **Qué:** (a) agregar `llegadas_limpias = (motivo == META) & (reintentos == 0)` y una columna nueva en `historial.csv`; (b) la subida de nivel y la graduación usan **llegadas limpias**; (c) el premio de rapidez **solo se paga si la llegada fue limpia** (o se multiplica por `0.25**reintentos`), y `CASTIGO_CHOQUE` se calibra para que un choque nunca sea rentable: castigo > premio de rapidez máximo menos el de referencia, es decir ≥ 50; (d) castigo por `TIEMPO` igual al de `ATASCADO`.
- **Por qué:** elimina el incentivo D3. El rebobinado se queda como **andamio de aprendizaje**, pero ya no infla las métricas.
- **Riesgo:** medio. El aprendizaje puede ir más lento en niveles altos. Se mitiga dejando (c) como opción en `config.py` y comparando ambas versiones con varias semillas. **Esfuerzo:** 2-3 h.

### P3. Modelo de sensores y actuadores realista + ablación de entradas privilegiadas (`sensores.py`, nuevo, enganchado en `observar()`). **Prioridad 2**
- **Qué:** con la bandera `C.SENSORES = "ideal" | "realista"`:
  - ruido gaussiano por canal (σ en una tabla: velocidad ±0.2 m/s, `lat` ±0.3 m tipo GNSS-RTK degradado o visión, `psi` ±1°, lidar ±3 cm con *dropout* del 2 %);
  - **sesgo por episodio** (constante desconocida, más dañina que el ruido blanco);
  - **error de percepción de μ** (factor ×U(0.7, 1.3) entre el μ que se percibe y el real), que es el caso SOTIF por excelencia;
  - **latencia** de L pasos de control (buffer `deque`, L ∈ {0, 1, 2, 3} → 0-100 ms);
  - **dinámica de actuadores:** acelerador y freno con primer orden τ ≈ 50/80 ms y límite de tasa.
- **Ablación (aporte científico):** entrenar y evaluar con y sin `v_segura` y sin curvatura exacta (curvatura del mapa con ruido). Se publica una tabla de "cuánto depende la política de información privilegiada".
- **Compatibilidad:** la dimensión de entrada no cambia (35), así que `mejor_moto.json` sigue cargando. **Riesgo:** medio (habrá que reentrenar para el modo realista). **Esfuerzo:** 1 día.

### P4. Randomización de dinámica por episodio y curvas de fragilidad (`fisica.py`, escalas por moto). **Prioridad 2**
- **Qué:** multiplicadores por moto, muestreados al crear `Simulador`: masa ±10 %, `PAR_MOTOR` ±15 %, μ ±20 %, `SUSP_K` ±20 %, `CMG_MAX` ±25 %, `PAR_FRENO` ±15 %, `TAU_DIRECCION` ±30 %. Se implementan como arreglos `(n,)` que reemplazan a los escalares de `config` dentro de `_fisica` y se reducen en `_quedarse` (se agregan a `_CAMPOS` y `_ESTADO`).
- **Uso:** (i) en entrenamiento, *domain randomization* opcional (Tobin 2017; Peng 2018); (ii) en evaluación, **curvas de fragilidad**: tasa de llegada limpia (con IC) contra la magnitud de la perturbación, un parámetro a la vez. Eso es análisis de sensibilidad, y responde la pregunta de qué parámetro mal identificado rompe la política.
- **Riesgo:** medio, porque toca el bucle caliente (hay que medir el costo, que se espera <5 %). **Esfuerzo:** 1-1.5 días.

### P5. Requisitos formales en STL con robustez cuantitativa (`stl.py`, nuevo). **Prioridad 2**
- **Qué:** un mini evaluador de STL sobre trazas discretas en numpy, con G, F y U acotados, ∧, ∨ y ¬, más un registro opcional de trazas en `Simulador` (`registrar=True`, que guarda por paso `lat, psi, v, phi, derrape, cmg_sat, v_segura, kappa`).
- **Requisitos propuestos** (ρ > 0 = se cumple; el valor es el margen):
  - R1 carril: `G(|lat − LAT_CARRIL| < 1.0)`
  - R2 borde: `G(|lat| < ANCHO/2 − 0.3)`
  - R3 velocidad mínima: `G[t₀,T](v ≥ 8.33)`
  - R4 velocidad segura: `G(v ≤ v_segura + 1.0)`
  - R5 invasión acotada: `G(lat > 0 → F[0,2] lat < 0)`
  - R6 inclinación: `G(|phi| < 0.6)`
  - R7 reserva de estabilizador: `G(|cmg_sat| < 0.9)`
  - R8 tarea: `F[0,T_max](x ≥ meta)`
- **Por qué:** convierte "manejar bien" en una especificación auditable y da una señal continua para la falsificación (P6). Las violaciones se reportan con tiempo y lugar.
- **Riesgo:** bajo. **Esfuerzo:** 1 día.

### P6. Falsificación adversarial y estimación de eventos raros (`falsificador.py`, nuevo). **Prioridad 3**
- **Espacio de escenarios θ:** parámetros del generador (amplitud, `curva_max`, secuencia de materiales, posición del hielo justo después de una curva), ráfagas laterales (instante, magnitud, duración), error de μ percibido, latencia y multiplicadores de P4.
- **Truco de rendimiento:** las perturbaciones que no cambian la pista (ráfagas, μ percibido, latencia, dinámica) se ponen **en la dimensión del lote**: 80 variantes de θ por pista se simulan a la vez, igual que hoy se simulan 80 motos.
- **Algoritmo:** método de entropía cruzada o un CMA-ES simple (~60 líneas de numpy) que **minimiza min_i ρ(R_i)**. Produce un **catálogo de escenarios críticos** (semilla + θ, en JSON con estructura parecida a OpenSCENARIO) que se vuelven **pruebas de regresión** permanentes.
- **Estimación:** usar la distribución sesgada que encuentra el CE como propuesta de *importance sampling* para estimar P(falla) bajo la distribución nominal, con error estándar (Zhao 2017; Corso 2021, §5).
- **Cuidado:** si los escenarios adversariales se meten al entrenamiento, se reportan **aparte** y se evalúa sobre un catálogo adversarial distinto, para no sobreajustar al atacante.
- **Riesgo:** medio. **Esfuerzo:** 2 días.

### P7. Escudo de seguridad opcional: Simplex + CBF (`escudo.py`, nuevo). **Prioridad 3**
- **Controlador de respaldo (simple y analizable):** velocidad objetivo `max(V_ESTABLE + 1, min(v_segura, v))` con PI sobre acelerador y freno; dirección por *pure pursuit* o retroalimentación lineal sobre `(lat − LAT_CARRIL, psi)` más prealimentación de curvatura `atan(κ·L)`.
- **Filtro CBF para el carril:** h = 1 − (lat − L_c)². Con `lat' = v sin ψ` y `ψ' = v tanδ/L − vκ` el grado relativo es 2. Una CBF exponencial (ḧ + k₁ḣ + k₀h ≥ 0) da una **restricción lineal en tanδ**, y el "QP" de una variable se resuelve **recortando** el comando de la red (forma cerrada, sin solver).
- **Conmutación Simplex:** el respaldo toma el control si TLC < 0.8 s, |phi| > 0.5, `cmg_sat` > 0.85 o v > v_segura + 2.
- **Métrica honesta:** **intervenciones por km** y "fallas evitadas". Se reporta siempre la red **sin escudo** y **con escudo**, porque el escudo no debe esconder lo que la red no aprendió. Por defecto queda apagado en el entrenamiento.
- **Límite que hay que declarar:** la garantía de la CBF vale solo para el modelo cinemático de la vista superior y con agarre suficiente. Con μ bajo, la restricción puede no tener solución, y eso hay que reportarlo como tal.
- **Riesgo:** medio. **Esfuerzo:** 1.5-2 días.

### P8. Reporte de seguridad automático (`reporte_seguridad.py` → `reportes/AAAA-MM-DD_nivelK.md` + CSV + JSON). **Prioridad 1 (junto con P1)**
- **Contenido:**
  1. **ODD declarado** (materiales, pendientes, curvaturas acotadas por `V_DISENO` como en `terreno.py:241-245`, sin tráfico, velocidades ≥ 30 km/h);
  2. tabla de requisitos R1-R8 con la ρ mínima, la mediana y el % de violación;
  3. métricas de P1 con IC;
  4. taxonomía de fallas por rasgo y material;
  5. curvas de fragilidad (P4) y resultados de falsificación (P6);
  6. ablaciones (P3) y efecto del escudo (P7);
  7. trazabilidad: hash de `config.py`, hash de los pesos, semillas, versión de numpy y fecha;
  8. *safety case* esquemático al estilo UL 4600 (afirmación → argumento → evidencia), con las **limitaciones explícitas** de D1 a D6.
- **Gráficas:** matplotlib, que ya es dependencia. **Riesgo:** bajo. **Esfuerzo:** 1 día.

### P9. Rigor estadístico del entrenamiento. **Prioridad 2**
Como mínimo 5 semillas de entrenamiento independientes (`--semilla`). Se reportan generaciones-hasta-nivel-k y la tasa de llegada limpia reservada con **IQM y bootstrap al 95 %** (Agarwal 2021). Las comparaciones entre variantes (P2c, P3 y P4 encendidos o apagados) se hacen con la misma suite de P1 y con pruebas pareadas (las mismas semillas de pista). **Esfuerzo:** script de 0.5 días; el cómputo lo corre el usuario.

### P10. Verificación del simulador (`pruebas/test_fisica.py`, pytest). **Prioridad 3**
- Convergencia en `DT` (SUBPASOS 6 → 12: las métricas no deben cambiar más de x %).
- Energía en caída libre y rebote.
- Distancia de frenado contra tablas (el README ya trae una, `README.md:304`; hay que convertirla en prueba automática).
- Moto en recta sin control → cae por debajo de `V_CRITICA`.
- Determinismo con semilla.
- Opcional (doctoral): comparar los modos *weave* y *capsize* del modelo lateral linealizado contra el benchmark de Meijaard (2007) y, si no coinciden, documentar el modelo como "reducido/fenomenológico".

**Esfuerzo:** 1 día. **Riesgo:** nulo.

---

## 4. Qué NO cambiar

1. **La arquitectura vectorizada por lote** (`Simulador` con N motos). Es lo que hace viables P1, P4 y P6 en una laptop. Hay que extenderla, no reescribirla.
2. **El GA sin gradientes y la red pequeña 35-20-3.** Un controlador chico es *más* auditable (abre la puerta a verificación formal o a análisis de sensibilidad por entrada). No hay que saltar a una red profunda.
3. **Los números aleatorios comunes en el entrenamiento** (mismo ruido y misma pista para toda la población). Son correctos para *ordenar*. Solo hay que separar la *evaluación*.
4. **El rebobinado como andamio de entrenamiento.** Se queda, pero **fuera de las métricas** (P2).
5. **El currículo de 8 niveles y la garantía de factibilidad** de las pistas (`terreno.py:241-245`). Eso ya es una definición implícita de ODD y solo hay que **escribirla**.
6. **ABS, TCS y CMG** tal como están: no son el cuello de botella de credibilidad.
7. **No perseguir más fidelidad física (Pacejka completo, multicuerpo 3D) antes de tener P1, P2 y P8.** Sin evaluación rigurosa, más fidelidad no compra credibilidad.
8. **El formato de `mejor_moto.json`** (P3 y P4 no cambian la dimensión de entrada) y el flujo del usuario de entrenar él mismo.
9. **No usar la ruta del usuario** ni rutas vistas en el entrenamiento como evidencia de desempeño.

---

## 5. Plan mínimo sugerido para la Ronda 2

| Orden | Entregable | Esfuerzo | Resultado presentable |
|---|---|---|---|
| 1 | P2 (llegada limpia + aptitud corregida) | 3 h | Elimina el *reward hacking* más obvio |
| 2 | P1 + P8 (suite reservada + reporte) | 2 días | Primera tabla con IC; afirmaciones con su n |
| 3 | P5 (STL) | 1 día | Requisitos auditables |
| 4 | P3 + P4 (sensores, latencia, randomización) | 2-2.5 días | Ablación y curvas de fragilidad: el núcleo "sim2real honesto" |
| 5 | P6 + P7 (falsificación + escudo) | 3.5-4 días | Nivel doctoral: escenarios críticos, P(falla) por IS, Simplex/CBF |
| 6 | P9 + P10 | 1.5 días + cómputo del usuario | Reproducibilidad multi-semilla y simulador verificado |

**Frase para la empresa:** *"No afirmamos transferencia al mundo real. Afirmamos, con intervalos de confianza y requisitos formales, cuán robusta es la política ante ruido, latencia, error de percepción y variación de parámetros dentro de un ODD declarado, y mostramos los escenarios exactos donde falla."* Esa afirmación sí la cree un equipo de validación.
