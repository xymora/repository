# R1 — Agente 5: Director de I+D industrial / transferencia tecnológica (dos ruedas)

**Fecha:** 2026-10-08 · **Ronda:** 1 (investigación y propuesta) · **Proyecto:** MotoTerminator (numpy + tkinter, GA 35-20-3)

---

## 0. Tesis en una línea

MotoTerminator **no** se vende como "moto autónoma": se vende como **un banco de pruebas virtual, ligero y reproducible, para generar escenarios adversos y comparar controladores de estabilidad/asistencia en dos ruedas**, con un currículo evolutivo como generador de casos difíciles. Eso es lo que la industria ya paga (dSPACE ASM Bike, IPG MotorcycleMaker) y es donde un proyecto de doctorado puede aportar algo defendible.

---

## 1. Panorama industrial y académico (con fuentes)

### 1.1 Lo que han hecho los fabricantes

| Actor | Qué hizo | Lección para nosotros | Fuente |
|---|---|---|---|
| **Honda Riding Assist** (CES 2017) | Equilibrio a < ~3 mph **sin giroscopio**: cambia el ángulo de horquilla (desacopla manubrio) y hace micro-correcciones de dirección; tecnología heredada de UNI-CUB/ASIMO. Seguía al dueño a paso de peatón. Concepto, no producción. | Honda descartó explícitamente el giroscopio por **peso y por cambiar la sensación de manejo**. Nuestro CMG es una elección que hay que justificar, no un dato. | [global.honda 2017](https://global.honda/en/newsroom/news/2017/c170109eng.html), [Honda CES](https://global.honda/innovation/CES/2017/002.html), [PCWorld](https://www.pcworld.com/article/411611/hondas-amazing-riding-assist-motorcycle-wont-fall-over.html) |
| **Yamaha MOTOBOT** (con SRI International) | Robot humanoide pilotando una R1M sin modificar. Superó 200 km/h (sept. 2017). Vuelta en Thunderhill West: 117.504 s vs 85.74 s de Rossi. | El valor fue **el aprendizaje de dinámica**, no el robot. Cifra honesta: ~37 % más lento que un humano élite, y Yamaha lo publicó así. | [Yamaha MOTOBOT ep3](https://global.yamaha-motor.com/design_technology/technology/motobot/ep3/), [The Drive](https://www.thedrive.com/watch-this/15582/watch-a-robots-attempt-to-beat-valentino-rossis-lap-time) |
| **Yamaha MOTOROiD / MOTOROiD2** (2017, 2023) | **AMCES** (Active Mass Center Control System): equilibrio moviendo masas (batería, basculante) alrededor de un eje; MOTOROiD2 con dirección electrónica se levanta del caballete. | **Validación directa de nuestro "lastre activo"**: un OEM grande apuesta por control de centro de masa. Es nuestro mejor ancla narrativa. | [Yamaha MOTOROiD](https://global.yamaha-motor.com/design_technology/design/concept/motoroid/), [New Atlas](https://newatlas.com/motorcycles/yamaha-motoroid-2) |
| **BMW Motorrad R 1200 GS ConnectedRide** (2018/CES 2019) | GS autónoma (acelera, curva, frena, se detiene) **sin giroscopio**, con computadoras en maletas. BMW la definió como **"testbed for advanced motorcycle safety equipment"**: evasión de obstáculos, mantenimiento de carril. | **Exactamente nuestro posicionamiento**: la autonomía como instrumento para desarrollar ayudas al piloto, no como producto. | [WebBikeWorld](https://www.webbikeworld.com/bmw-built-self-driving-motorcycle/), [Evo India](https://evoindia.com/news/ces-2019-bmw-motorrad-showcases-autonomous-r-1200-gs) |
| **Bosch MSC** (2013/2014) | ABS + IMU de inclinación; frenado al límite hasta 45° de inclinación (ABS convencional ~20°). Primera serie: KTM 1190 Adventure 2014. Bosch afirma: ABS evita ~35 % de accidentes con víctimas, MSC ~6 pp adicionales (cifra del propio Bosch). | KPI clave de la industria: **frenado/aceleración en curva sin pérdida de estabilidad**. Nuestro ABS/TCS debe medirse contra eso. | [Ultimate Motorcycling](https://ultimatemotorcycling.com/2014/10/23/bosch-motorcycle-stability-control-system-explained/), [Mobility Eng. Tech](https://www.mobilityengineeringtech.com/component/content/article/45008-sae-ma-01353) |
| **Bosch ARAS** (radar, 2020→) | ACC (30–160 km/h), Blind Spot, Forward Collision Warning; debut Ducati Multistrada V4 (MY2021), luego KTM 1290 SAS, Yamaha Tracer 9 GT+, BMW R 18 Transcontinental. Ducati **limitó la autoridad** de aceleración/frenado del ACC. | La industria **limita autoridad** del sistema en motos porque el piloto no está atado: el mercado real es *asistencia*, no autonomía. | [Cycle Gear ARAS](https://www.cyclegear.com/common-tread/bosch-advanced-rider-assistance-system-aras-first-ride-review), [Ducati Multistrada V4 electronics](https://ducati.com/ww/en/bikes/multistrada/multistrada-v4/electronics) |
| **Lit Motors C-1** | Vehículo cerrado de dos ruedas con **dos CMG de gimbal simple** (redundancia) + caballete automático. Patente US11648994B2 (control integrado CMG + steer-by-wire). Litigio 2020 sobre patentes; **no encontré evidencia de producción**. | Es el **antecedente directo de nuestro CMG**: hay arte previo patentado → riesgo de PI si reclamamos "CMG para motos". | [Wikipedia Lit Motors](https://en.wikipedia.org/wiki/Lit_Motors), [ASME](https://www.asme.org/topics-resources/content/finding-the-balance), [US11648994B2](https://patents.google.com/patent/US11648994B2) |
| **Damon HyperSport CoPilot** (CES 2020) | Radar + cámaras + red neuronal, hasta 64 objetos, alertas hápticas; datos etiquetados a la nube para mejorar algoritmos. Socio de software: BlackBerry QNX. Reportes de **retrasos de producción y problemas financieros**. | Advertencia: prometer IA en motos sin vehículo en producción daña credibilidad. | [BusinessWire 2020](https://www.businesswire.com/news/home/20201118005299/en/), [Cycle Gear](https://www.cyclegear.com/common-tread/damon-hypersport-unveiled-at-ces) |
| **Harley/LiveWire, Gogoro, robots de entrega en dos ruedas, Ducati–Lamborghini ADAS** | **No investigado a fondo / no encontré fuentes específicas en esta ronda.** No citar cifras sobre ellos hasta verificarlas. | — | — |

### 1.2 Academia (lo que los revisores van a preguntar)

- **Modelo de referencia Whipple / benchmark** — Meijaard, Papadopoulos, Ruina, Schwab, *Proc. R. Soc. A* 463 (2007) 1955–1982 ([PDF](https://eklausmeier.lima-city.de/pdf/meijaard2007.pdf)). Cualquier revisor de dinámica de dos ruedas pedirá comparar contra este modelo linealizado (modos *weave*, *capsize*, velocidad de autoestabilidad).
- **TU Delft Bicycle Dynamics Lab** — Kooijman et al., "A Bicycle Can Be Self-Stable Without Gyroscopic or Caster Effects", *Science* 332 (2011) 339–342 ([ScienceDaily](https://www.sciencedaily.com/releases/2011/04/110414141356.htm)). Implicación: el efecto giroscópico **no es la explicación de la estabilidad**; nuestro modelo simplificado no debe afirmar lo contrario. Parámetros medibles: [BicycleParameters (TU Delft/UC Davis)](https://bicycleparameters.readthedocs.io/en/latest/description.html).
- **Tsinghua — bicicleta autónoma con chip Tianjic** — Pei et al., *Nature* 572 (2019) 106–111 ([Tsinghua CBICR](https://www.cbicr.tsinghua.edu.cn/en/?p=104), [TechXplore](https://techxplore.com/news/2019-08-hybrid-chip-autonomous-bicycle.amp)): equilibrio con red *spiking*, detección con CNN, seguimiento y evasión. Presentada como **prueba de concepto**, no como producto; es el precedente más citado de "red neuronal que equilibra un vehículo de dos ruedas".
- **Neuroevolución** (contexto del método; referencias canónicas a verificar en la bibliografía final): NEAT (Stanley & Miikkulainen, *Evolutionary Computation* 2002); Evolution Strategies como alternativa a RL (Salimans et al., arXiv:1703.03864, 2017); Deep GA (Such et al., arXiv:1712.06567, 2017).
- **Herramientas comerciales competidoras** (= quién ya cobra por esto): [dSPACE ASM Bike](https://www.dspace.com/ja/jpn/home/learning-center/recordings/handson/video_ho_asm-bike.cfm) (MIL/SIL/HIL para asistencias al piloto), IPG MotorcycleMaker; en pista física, [ABD LaunchPad 80](https://www.abdynamics.com/track-testing/adas-platforms/launchpad-80/) (blanco móvil de moto para protocolos Euro NCAP AEB/LSS 2023).
- Univ. Padova (grupo de dinámica de motos), MIT: **no localicé en esta ronda** referencias concretas verificadas; queda como pendiente para el agente de estado del arte.

### 1.3 Mercado y regulación

- **Tamaño de mercado ADAS para motos: las cifras discrepan ~10×.** Fortune Business Insights: USD 311 M (2025) → 1,447 M (2034), CAGR 18.1 %, Europa 39 % ([FBI](https://www.fortunebusinessinsights.com/motorcycle-adas-market-119056)); Allied Market Research: USD 1.86 B (2025) → 3.34 B (2035) ([Allied](https://alliedmarketresearch.com/motorcycle-adas-advanced-driver-assistance-system-market)); Market Research Future: USD 3.01 B (2025) ([MRFR](https://www.marketresearchfuture.com/es/reports/motorcycle-adas-market-33289)). **Recomendación:** citar un rango y la fuente, nunca una sola cifra como hecho.
- **Regulación:** UNECE incluyó motos/scooters (> 25 km/h) en **R155 (ciberseguridad)** en enero 2024 ([IEU Monitoring](https://ieu-monitoring.com/editorial/autonomous-vehicles-unece-extends-cybersecurity-regulation-to-motorcycles-and-scooters/427024/)). En la UE las motos están bajo el Reglamento 168/2013 (categoría L) y la GSR2 (2019/2144) está pensada para autos ([Comisión Europea](https://single-market-economy.ec.europa.eu/sectors/automotive-industry/legislation/two-and-three-wheel-vehicles-and-quadricycles_en)). Euro NCAP Vision 2030 contempla evaluar motos y ya usa blancos de moto en AEB ([MCN](https://motorcyclenews.com/news/2023/january/euro-ncap-motorcycle-safety-changes)). **India:** borrador MoRTH (junio 2025) para exigir ABS en todas las L2 fabricadas desde 1-ene-2026 ([Autocar India](https://www.autocarindia.com/bike-news/two-wheelers-401597)); **no confirmé** la notificación final. ISO 34502:2022 (evaluación por escenarios) se dirige a ADS en autopistas y **no confirmé que cubra motos** ([ISO](https://www.iso.org/standard/78951.html)).
- **No encontré** una regulación UNECE específica que exija ADAS (AEB, LKA) en motos a 2026. Esto significa que el motor de compra hoy es **diferenciación de producto y preparación para Euro NCAP**, no cumplimiento obligatorio — salvo ABS en mercados como India.

---

## 2. Propuesta de valor y casos de uso B2B

**Propuesta de valor:** *"Generador de escenarios adversos y banco comparativo de controladores de estabilidad para dos ruedas, de bajo costo, reproducible por semilla y con mapas reales (OSM)."*

Lo que **sí** tenemos de diferencial frente a dSPACE/IPG: (a) currículo evolutivo que **descubre automáticamente** combinaciones terreno-velocidad-curva donde los controladores fallan; (b) geometría de calles reales de cualquier ciudad (OSM) en minutos; (c) costo cero de licencia y ejecución en una laptop. Lo que **no** tenemos: modelo multicuerpo validado, modelo de neumático Pacejka/MF-Tyre, HIL, tiempo real certificado.

| # | Caso de uso | Cliente típico | Qué entregamos | KPI que mira el cliente |
|---|---|---|---|---|
| U1 | **Fuzzing de escenarios para ADAS** (falsificación): el GA evoluciona *escenarios* (no motos) que maximizan la falla de un controlador dado | Bosch Two-Wheeler, proveedores Tier-1, equipos de validación OEM | Librería de escenarios críticos exportados (JSON → idealmente ASAM OpenSCENARIO) | Nº de escenarios críticos únicos/hora de cómputo; cobertura del espacio de parámetros; tasa de falsos positivos al re-simular en su herramienta |
| U2 | **Benchmark comparativo de controladores** (PID/LQR vs MPC vs red evolucionada vs RL) | Departamentos de I+D, universidades | Modo "comparar controladores" con métricas estandarizadas e IC | Tasa de caída por km, desviación lateral RMS, pico de inclinación, distancia de frenado en curva, esfuerzo de actuador, *jerk* |
| U3 | **Estabilización a baja velocidad** (estilo Riding Assist / AMCES) | Honda, Yamaha, scooters urbanos (Piaggio, Gogoro), *follow-me* | Estudio de compromiso masa-del-actuador vs velocidad mínima estable (CMG vs lastre vs dirección) | Velocidad mínima estable, energía del actuador (W), masa añadida (kg), tiempo de recuperación ante empujón |
| U4 | **Logística / reubicación autónoma** (moto o scooter que se reubica sola a baja velocidad en calle real) | Flotas de *sharing*, delivery de última milla | Planificador A→B con sentido de calles + controlador; métricas de éxito por ruta | Tasa de misión completada, tiempo/km, intervenciones por 100 km |
| U5 | **Educación/formación** de ingenieros en control y neuroevolución | Universidades, centros de capacitación OEM | Paquete docente | Adopción, nº de cursos |

**Prioridad comercial:** U1 > U2 > U3. U1 es la que encaja con la tendencia real (validación virtual por escenarios, ver [SAE 2026-26-0048](https://saemobilus-test.cld.sae.org/papers/experimental-correlation-virtual-physical-testing-regulatory-adas-features-a-roadmap-towards-fully-virtual-adas-validation-2026-26-0048)) y requiere pocos cambios: el GA ya existe, sólo hay que **invertir el genoma** (evolucionar terreno en vez de pesos).

---

## 3. Entregables "nivel doctorado presentable"

### 3.1 Artículo técnico (formato IEEE, 8–10 págs., objetivo: IEEE T-ITS, IEEE IV, IROS o *Vehicle System Dynamics*)

1. **Título** sugerido: *"Curriculum-Driven Neuroevolution for Riderless Two-Wheeler Stabilization on Procedural and OpenStreetMap-Derived Roads: A Reproducible Benchmark"*.
2. **Abstract** (≤ 200 palabras): problema, método, 3 números con IC, limitación principal.
3. **I. Introducción**: motivación de seguridad (curvas, baja velocidad), brecha (no hay benchmark abierto y ligero para controladores de dos ruedas), 3–4 contribuciones numeradas y **acotadas**.
4. **II. Trabajo relacionado**: (a) dinámica de bicicleta/moto (Whipple, Kooijman 2011); (b) estabilización activa (Honda RA, AMCES, Lit C-1 CMG); (c) control aprendido (Tianjic 2019, RL, neuroevolución); (d) validación por escenarios (ISO 34502, ASAM OpenSCENARIO, ASM Bike).
5. **III. Modelo del sistema**: ecuaciones explícitas de lo que el simulador hace **realmente** — plano de cabeceo multicuerpo (chasís + 2 ruedas + suspensión), guiñada cinemática tipo bicicleta, inclinación como sistema de 2º orden que sigue `atan(v·ω/g)`, CMG y lastre como pares acotados, curva de agarre con pico al 15 % de deslizamiento, ABS/TCS. Tabla de parámetros (de `config.py`). **Declarar que no es el modelo de Whipple** y cuantificar la diferencia (sec. VI).
6. **IV. Método**: codificación (783 pesos, 35-20-3), aptitud (ecuación completa con todos los términos), GA (élite 4, torneo 3, σ adaptativa, 4 % inmigrantes), currículo de 8 niveles, transferencia terreno→calles.
7. **V. Experimentos**: protocolo con **semillas fijas (≥ 10 corridas independientes)**, conjunto de pistas de prueba **nunca vistas** (*held-out*) por nivel, y *baselines*: (i) PID/LQR de inclinación + control longitudinal por perfil de velocidad, (ii) aleatorio, (iii) CMA-ES o PPO con el mismo presupuesto de evaluaciones.
8. **VI. Resultados**: curvas de aprendizaje media ± IC 95 % (bootstrap), tasa de éxito por nivel, tabla de KPIs (sec. 2), **ablaciones** (sin CMG, sin lastre, sin ABS/TCS, sin currículo, sin lidar), sensibilidad a parámetros físicos (±20 % masa, μ, altura CG), y análisis de **escenarios de falla**.
9. **VII. Limitaciones** (sección obligatoria y honesta — ver sec. 5).
10. **VIII. Trabajo futuro**: modelo multicuerpo 3D validado, neumático Pacejka, exportación OpenSCENARIO, SIL con controlador real, prototipo a escala.
11. **Disponibilidad de código y datos** + referencias.

### 3.2 Deck ejecutivo (12 diapositivas, 15 min)

1. Problema (cifra de accidentes en curva **citada**) · 2. Qué hace la industria (tabla 1.1 condensada) · 3. Brecha: validación virtual cara y cerrada · 4. Nuestra solución (1 diagrama) · 5. Demo en video 60 s · 6. Resultados clave con IC · 7. Caso de uso U1 (fuzzing) con ejemplo concreto · 8. Comparación honesta vs dSPACE/IPG (qué sí/qué no) · 9. Roadmap TRL · 10. Modelo de colaboración (piloto de 3 meses, licencia, co-desarrollo) · 11. Equipo y PI · 12. Petición concreta (datos de parámetros de una moto real + 1 ingeniero de contacto).

### 3.3 Demo reproducible

- `requirements.txt` con versiones fijadas; `python -m mototerminator.bench --semilla 0..9 --nivel 1..8 --salida resultados/`.
- Modelo pre-entrenado versionado + *hash*; script que regenera **cada figura del paper** (`make figuras`).
- Modo *headless* determinista (ya existe `--sin-gui`); prueba de CI que verifique determinismo por semilla.
- Contenedor Docker opcional (respetar las reglas del usuario: `npm` no aplica, pero sí orden de capas y usuario no root).

### 3.4 Ficha técnica (1 página)

Alcance del modelo · grados de libertad simulados · paso de integración (DT = 1/180 s; control a 30 Hz) · sensores/actuadores modelados · rendimiento (generaciones/minuto en hardware X) · formatos de entrada/salida · limitaciones · licencia · contacto.

### 3.5 Licencia y PI

- **Código**: dual — AGPL-3.0 o Apache-2.0 para la versión académica + licencia comercial para U1/U2 (si se busca ingreso). Si el objetivo es solo reputación/doctorado: Apache-2.0 (las empresas la aceptan; AGPL suele ser bloqueada por sus legales).
- **Datos**: OpenStreetMap es **ODbL** (atribución + *share-alike* en bases derivadas); la imagen satelital de Esri tiene **términos de uso propios** que normalmente **no permiten uso comercial libre** — verificar antes de cualquier demo pagada o redistribución de los `.jpg` en `datos/`.
- **Patentabilidad**: el CMG en dos ruedas tiene arte previo (Lit Motors US11648994B2); el control de centro de masa tiene arte previo de Yamaha (AMCES). Lo potencialmente novedoso y defendible es el **método de generación de escenarios críticos por currículo evolutivo** — candidato a *invention disclosure* antes de publicar (en México, IMPI; periodo de gracia de 12 meses tras divulgación propia, verificar vigencia).
- Nombre: "Terminator" es marca registrada de terceros → **cambiar el nombre comercial** antes de presentarlo a empresas (p.ej. "TwinTrack Bench").

### 3.6 Roadmap TRL (escala NASA/EU H2020)

| TRL | Estado | Criterio de salida | Plazo orientativo |
|---|---|---|---|
| 2 → 3 (hoy) | Concepto formulado + prueba analítica/simulada simplificada | Paper con baselines, IC y ablaciones | 2–3 meses |
| 3 → 4 | Validación de componentes en laboratorio (simulación de alta fidelidad) | Controlador evolucionado transferido a modelo multicuerpo 3D (p.ej. MuJoCo/Chrono) con parámetros de una moto real medida; brecha sim-a-sim reportada | 4–6 meses |
| 4 → 5 | Validación en entorno relevante | Prototipo a escala (RC 1:5 con IMU + CMG/volante de inercia) o SIL con ECU real; ensayo de empujón y slalom a baja velocidad | 6–12 meses |

---

## 4. Mejoras de producto/UI priorizadas

| P | Mejora | Por qué (valor industrial) | Esfuerzo |
|---|---|---|---|
| P1 | **Modo benchmark headless con semillas y exportación CSV/JSON de KPIs** por episodio (caídas, desviación lateral RMS, pico de inclinación, saturación CMG, energía, tiempo) | Sin esto no hay IC ni paper; es lo primero que pide cualquier ingeniero de validación | Bajo (1–2 días) |
| P2 | **Interfaz `Controlador` enchufable** (red GA, PID/LQR, externo vía función Python) + **modo "comparar controladores"** en la misma pista | Habilita U2 y los *baselines* del paper; demuestra que es banco, no juguete | Medio (3–5 días) |
| P3 | **Desactivar el "rebobinado"** (SEG_RETROCESO / MAX_REINTENTOS) y el arranque asistido en modo evaluación | Hoy un error no termina el episodio: inflaría cualquier tasa de éxito ante un auditor | Bajo (½ día) |
| P4 | **Generador de escenarios adversos** (GA sobre parámetros de pista contra un controlador fijo) + exportación | Es el producto U1 | Medio-alto (1–2 semanas) |
| P5 | **Dashboard de métricas** (pestaña o HTML exportado): curvas con IC, histograma de modos de falla, mapa de calor de fallas sobre la pista/OSM | Lo que se enseña en una reunión de 15 min | Medio (3–4 días) |
| P6 | **Reporte automático PDF/HTML por corrida** (config, *hash* del modelo, semillas, KPIs, figuras) | Trazabilidad tipo ISO 26262/SOTIF; profesionalismo | Medio (2–3 días) |
| P7 | **Ruido de sensores, latencia de actuador y fallas inyectadas** (IMU con sesgo, lidar con dropout, CMG saturado) | Robustez es el KPI #1 de seguridad funcional | Medio (3–5 días) |
| P8 | **Perfiles de vehículo** (scooter 110 kg, naked 190 kg, touring 300 kg) en archivo YAML | Cada OEM querrá "su" moto | Bajo-medio |
| P9 | Modo "piloto humano" (teclado/joystick) para comparar contra humano | Demo vistosa; dato comparativo tipo MOTOBOT | Medio |
| P10 | Estética post-apocalíptica → **tema "ingeniería"** conmutable (fondo neutro, rejilla métrica) | Las empresas desconfían de lo que parece videojuego | Bajo |

---

## 5. Afirmaciones que NO se deben hacer (overclaiming)

1. **"Moto autónoma"** o "conduce sola en calles reales". Lo correcto: *"controlador simulado sobre geometría de calles de OSM, asumiendo asfalto plano, sin tráfico, peatones ni semáforos"*.
2. **"Física realista"**. El modelo es plano en cabeceo + guiñada cinemática + inclinación como sistema de 2º orden que sigue un objetivo; **no** es Whipple ni multicuerpo 3D, y no tiene modelo de neumático validado. Decir *"modelo de orden reducido"*.
3. **"El giroscopio la mantiene estable"** como explicación física general — contradice Kooijman et al. 2011 y la elección de Honda/BMW de no usar giroscopio.
4. **Tasas de éxito con rebobinado y arranque asistido a 32 km/h** presentadas como éxito real. Reportar siempre con esas ayudas desactivadas o declararlas.
5. **"Aprende en 10 minutos / nivel 8 en 30 generaciones"** sin IC ni número de semillas. Una corrida no es un resultado.
6. **"Transferible a moto real"** o cualquier mención a seguridad funcional/ISO 26262 — no hay validación con datos físicos (TRL ≤ 3).
7. **"Mejor que Bosch/dSPACE"**. Somos complementarios y de menor fidelidad; la comparación correcta es costo/velocidad de exploración.
8. **Cifras de mercado como hecho único** (discrepan ~10× entre consultoras).
9. **"Lidar"** sin matizar: son muestras de altura del terreno a distancias fijas, no un modelo de sensor lidar.
10. **Uso comercial de imágenes Esri** o del nombre "Terminator" sin revisar licencias/marca.
11. **Novedad** del CMG o del lastre activo: hay arte previo (Lit Motors, Yamaha AMCES).

---

## 6. Propuesta concreta para el panel (para debatir en R2)

1. Reposicionar: de "Moto-Terminator" a **banco de escenarios y comparación de controladores**.
2. Primer sprint (≈ 2 semanas): P3 → P1 → P2 → baseline PID/LQR → 10 semillas → primeras figuras con IC.
3. Segundo sprint: P4 (escenarios adversos) + borrador del paper secciones III–VI.
4. Tercer sprint: deck, ficha técnica, licencia, verificación de términos Esri/OSM, *invention disclosure*.
5. Contactos realistas para un piloto: grupos universitarios de dinámica de dos ruedas (TU Delft, UC Davis) para validación del modelo **antes** de un OEM; después, programas de innovación abierta de Tier-1.

**Riesgo principal que veo:** que el panel invierta en más gráficos/terrenos antes de tener métricas reproducibles. Para una empresa, **una tabla con IC vale más que diez terrenos nuevos**.
