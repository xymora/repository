# R1 — Agente 1: Dinámica de vehículos de dos ruedas y modelado físico

**Rol:** experto en dinámica de motocicletas y modelado multicuerpo.
**Alcance:** solo diagnóstico y propuesta. No modifiqué ningún archivo del proyecto.
**Fecha:** 2026-10-08.

---

## 0. Resumen ejecutivo

El plano longitudinal (vista lateral: chasís, dos ruedas, suspensión, contacto, motor, frenos) es un modelo de 2D razonable. Su calibración es creíble: la suspensión trasera da 1.8 Hz con amortiguamiento ζ≈0.45 y el salto de rueda unos 15 Hz. El **plano lateral (inclinación, dirección, trayectoria) no es dinámica de motocicleta**: lo forman dos osciladores de segundo orden desacoplados más un modelo cinemático de bicicleta. Por eso:

1. **La red no puede influir en el equilibrio.** `wobdd` (fisica.py:364-365) no depende de la dirección `dirc` ni de ninguna salida de la red. El equilibrio es un piloto automático y la red solo dirige.
2. **No hay contradirección (countersteering) ni fase no mínima.** El giro sale directo del manubrio, `giro = v·tanδ/L` (fisica.py:321), y la inclinación "sigue" a un objetivo con un filtro (fisica.py:370-374). Una política entrenada así no se transfiere a una moto real.
3. **La inestabilidad a baja velocidad no viene de la física.** Linealicé el modelo de `wob`: sus eigenvalores son estables a **todas** las velocidades (≈ −11.9 y −0.97 1/s a 5 km/h; −16.8 y −3.6 1/s desde 30 km/h). La caída lenta aparece solo por la saturación de los actuadores y la amplificación artificial del ruido (`AMPLIF_LENTA`). Arriba de 30 km/h la dinámica no depende de la velocidad: no hay weave, wobble ni capsize.
4. **Un frenazo total en asfalto plano voltea la moto aunque el ABS esté activo.** El cabeceo llega a más de 200°. Mi prueba de 6 s está en la sección 2. Al 70 % de freno la desaceleración es de solo ≈6.6 m/s², cuando una moto real con ABS logra ≈9–10 m/s².
5. **No hay elipse de fricción** entre la fuerza lateral y la longitudinal, y el agarre lateral usa `max(μ)` de ambas ruedas con `μ·g`, sin la carga de cada rueda (fisica.py:326-327).

Propongo una ruta en tres capas, de menor a mayor riesgo:
- **(A)** Validación y correcciones baratas: tests, elipse de fricción, protección contra levantamiento trasero, ruido bien escalado.
- **(B)** Un CMG físico (cardán + rotor) que mantiene la dependencia de la velocidad que el usuario ya eligió.
- **(C)** Un módulo lateral físico opcional: Whipple–Meijaard parametrizado, extensible a Sharp con neumáticos con deriva, camber y relajación. Incluye un lazo interno automático de equilibrio, para que el aprendizaje siga siendo viable.

Todo es Python/numpy. Ya verifiqué que puedo reproducir el benchmark de Meijaard a 10⁻⁶.

---

## 1. Estado del arte relevante (fuentes verificadas)

| Tema | Referencia | Qué aporta al proyecto |
|---|---|---|
| Modelo de referencia bicicleta | Meijaard, Papadopoulos, Ruina, Schwab (2007), *Proc. R. Soc. A* 463:1955-1982, [doi:10.1098/rspa.2007.1857](https://doi.org/10.1098/rspa.2007.1857) | Ecuaciones linealizadas de inclinación y dirección `M q̈ + v C1 q̇ + (g K0 + v² K2) q = f`, con valores de referencia de 14 dígitos. Es el estándar de validación. |
| Implementación abierta | BicycleParameters (Moore), [docs del benchmark](https://bicycleparameters.readthedocs.io/stable/gallery/examples/plot_benchmark.html) | Eigenvalores a v=2 m/s: 2.682±1.681j, −3.072, −8.674. Los reproduje. |
| Autoestabilidad | Kooijman et al. (2011), *Science* 332:339-342, [doi:10.1126/science.1201959](https://doi.org/10.1126/science.1201959) | La estabilidad propia no depende solo del giroscopio ni del trail: la distribución de masas importa. Argumento para no "inventar" la estabilidad con una curva f(v). |
| Moto con neumáticos | Sharp (1971), *J. Mech. Eng. Sci.* 13(5):316-329, [doi:10.1243/JMES_JOUR_1971_013_051_02](https://doi.org/10.1243/JMES_JOUR_1971_013_051_02) | Primer modelo de moto con neumáticos con deriva: modos **wobble** (oscilación de la dirección, 6-10 Hz) y **weave** (inclinación, guiñada y dirección, 2-4 Hz). |
| Modelo avanzado | Sharp, Evangelou, Limebeer (2004), *Multibody Syst. Dyn.* 12:251-283, [doi:10.1023/B:MUBO.0000049195.60868.A2](https://doi.org/10.1023/B:MUBO.0000049195.60868.A2) | Geometría de contacto del neumático, Magic Formula con carga, deriva y camber, relajación. Encuentra que los pilotos ligeros sufren más oscilaciones (relevante: esta moto no tiene piloto). |
| Revisión de control | Limebeer & Sharp (2006), *IEEE Control Systems Mag.* 26(5):34-61, [doi:10.1109/MCS.2006.1700044](https://doi.org/10.1109/MCS.2006.1700044) | Revisión de modelado y control de vehículos de una sola huella. |
| Control de bicicletas | Åström, Klein, Lennartsson (2005), *IEEE CSM* 25(4):26-47, [doi:10.1109/MCS.2005.1499389](https://doi.org/10.1109/MCS.2005.1499389) | Jerarquía de modelos de simple a multicuerpo. Fase no mínima de la contradirección. |
| Neumáticos de moto | Cossalter, Doria, Lot (2003), "Dynamic Properties of Motorcycle and Scooter Tires" ([registro](https://core.ac.uk/works/29482016)); Cossalter, *Motorcycle Dynamics* (2ª ed., 2006, ISBN 9781430308614) | En moto el **empuje por camber** suele superar a la fuerza por deriva. Rigideces de camber y de deriva medidas. |
| Modelo de neumático | Lot (2004), "A motorcycle tire model for dynamic simulations" ([U. Padova](https://research.unipd.it/handle/11577/143336)); Pacejka, *Tyre and Vehicle Dynamics* (libro) | Magic Formula aplicada en el punto de contacto real del perfil toroidal. |
| CMG en bicicletas | Thanh & Parnichkun (2008), *IJARS* 5(4), [doi:10.5772/6235](https://doi.org/10.5772/6235); Yetkin et al., ACC 2014 ([PDF](https://web.stanford.edu/~kalouche/docs/ACC_2014.pdf)); CMG en par de tijera ("scissored pair") para bicicleta no tripulada, *IJCAS* 2020 ([registro](https://pure.seoultech.ac.kr/en/publications/active-balancing-control-for-unmanned-bicycle-using-scissored-pai/)) | Modelo CMG: par = h·α̇·cos α. El par en tijera cancela el par parásito y duplica el de recuperación. |
| Lit Motors C-1 | ASME, ["Finding the Balance"](https://www.asme.org/topics-resources/content/finding-the-balance) | Dos CMG de cardán de un eje, con redundancia. Balancea detenido y se inclina sola en curva. |
| Honda Riding Assist (CES 2017) | [Mobility Engineering/SAE](https://www.mobilityengineeringtech.com/component/content/article/43213-sae-ma-02501), [Ultimate Motorcycling](https://ultimatemotorcycling.com/2017/01/06/honda-riding-assist-debuts-at-ces-self-balancing-motorcycle) | Balancea **sin giroscopio**: cambia el lanzamiento (rake) y el trail, y corrige con la dirección a paso de peatón. Honda descartó los giroscopios por peso y por alterar la dinámica natural. |
| Yamaha MOTOBOT | [IEEE Spectrum](https://spectrum.ieee.org/cars-that-think/transportation/self-driving/watch-yamahas-humanoid-robot-ride-a-motorcycle-around-a-racetrack) | Robot humanoide sobre una YZF-R1M; estable desde ≈15 km/h. Usa los actuadores originales de la moto. |
| BMW ConnectedRide | [webbikeworld](https://webbikeworld.com/bmw-connectedride-motorcycle/) | R 1200 GS autónoma que acciona acelerador, freno, embrague y dirección; banco de pruebas de seguridad (mantener el carril, evadir obstáculos). |
| Bosch MSC | [eeNews Europe](https://www.eenewseurope.com/en/stability-control-reaches-motorbikes/), [Mobility Eng.](https://www.mobilityengineeringtech.com/component/content/article/45008-sae-ma-01353) | ABS sensible al ángulo de inclinación, **mitigación del levantamiento trasero** (limita el freno delantero según la tasa de cabeceo y la aceleración longitudinal), control antiwheelie, eCBS. Primera aplicación en serie: KTM 1190 Adventure 2014. |
| Estimación de inclinación | Boniolo, Savaresi, Tanelli (2012) ([registro](https://re.public.polimi.it/handle/11311/657466)); Maceira et al. (2021), *Sensors* 21:6626, [doi:10.3390/s21196626](https://doi.org/10.3390/s21196626) | Estimar la inclinación con IMU de dos acelerómetros y un giróscopo, con filtro de Kalman. |

---

## 2. Diagnóstico concreto (con evidencia)

### 2.1 Plano lateral: lo que falta (prioridad crítica)

- **D1. El equilibrio no depende de la red** (fisica.py:345-367). `wobdd = caida·sin(wob) − estabiliza·wob + sacudida + lastre + cmg − amortigua·wobd`. Ningún término contiene `dirc`, `ctrl` ni `giro`. El lastre (línea 352) y el CMG (línea 360) son leyes PD fijas sobre `wob`. La observación `phi` (fisica.py:154) sirve para el castigo por balanceo, pero la red no tiene ninguna acción que mueva `wob`.
- **D2. La inclinación por curva es cinemática** (fisica.py:370-375). `incl` sigue `arctan(v·giro/g)` con un filtro de 2º orden (INCL_W=8, INCL_Z=0.9) y la gravedad no actúa sobre `incl`. En una moto real la inclinación es un péndulo invertido que se controla **a través de la dirección**. Para girar a la derecha primero se gira el manubrio a la izquierda (fase no mínima; Åström 2005, sección "counter-steering").
- **D3. La guiñada sale del modelo de bicicleta cinemático** (fisica.py:321). Usa `DISTANCIA_EJES` y δ sin lanzamiento (rake), sin trail y sin deriva de neumáticos. config.py no define lanzamiento ni trail. Así no se pueden discutir con Honda o BMW la geometría de dirección ni el trail variable (el principio de Riding Assist).
- **D4. La estabilidad está impuesta, no emerge** (fisica.py:48-51 y 346). `estabilidad(v)` es una rampa de 10 a 30 km/h con exponente 1.9. Mi linealización (tabla abajo) muestra que el sistema lineal es **estable a toda velocidad**. Solo cae por la saturación (`LASTRE_MAX`, `CMG_MAX·h`) y por la sacudida amplificada (×8 a baja velocidad, `AMPLIF_LENTA`). Arriba de 30 km/h la dinámica no cambia con v, cuando en la realidad la frecuencia y el amortiguamiento del weave dependen fuertemente de v (Sharp 1971).

| km/h | f(v) | eigenvalores del lazo lineal de `wob` (1/s) | par CMG máximo (rad/s²) |
|---|---|---|---|
| 5 | 0.00 | −11.87, −0.97 | 0.22 |
| 15 | 0.07 | −11.54, −1.30 | 2.00 |
| 20 | 0.27 | −12.23, −2.02 | 3.56 |
| 30+ | 1.00 | −16.79, −3.61 | 8.00 |

- **D5. El CMG es fenomenológico** (fisica.py:359-363). El par sale en rad/s² y no en N·m. La saturación `cmg_sat` es un integrador artificial con un factor `(1 − sat²)`. Un CMG real satura porque el **ángulo de cardán** α se acerca a ±90° (singularidad: τ = h·α̇·cos α → 0). Se desatura regresando el cardán a cero, lo que obliga a la moto a apoyarse en la gravedad o en la dirección. Además produce un par de reacción en guiñada, h·α̇·sin α, que en el C-1 se cancela con dos rotores.
- **D6. Unidades mezcladas.** El lastre, el CMG y la sacudida están en rad/s², sin inercia de alabeo. Convertidos con I_x ≈ m·h² ≈ 290·0.75² ≈ 163 kg·m²: `LASTRE_MAX=1.5` equivale a ≈245 N·m, o sea un desplazamiento lateral de ≈0.42 m de los 60 kg (plausible). `CMG_MAX=8` equivale a ≈1300 N·m. Hay que documentarlo en N·m para que un ingeniero de Bosch o BMW lo pueda revisar.

### 2.2 Acoplamiento longitudinal–lateral

- **D7. Sin elipse de fricción.** El agarre lateral (fisica.py:326-331) es `μ_max·g·(1 − 0.7·pérdida)`, independiente de cuánta fuerza longitudinal `ft` ya se está usando. Frenar fuerte en curva no reduce la capacidad lateral salvo que el deslizamiento pase de 0.2. Justo este problema es el que resuelven el ABS en curva y el MSC de Bosch.
- **D8. `p.mu[i].max(0)` es optimista** (línea 327): toma el mejor material de las dos ruedas. Además usa `μ·g` en vez de `Σ μ_i·Fn_i/m`, así que ignora la transferencia de carga: en un stoppie la trasera no aporta nada lateral y en un wheelie la delantera tampoco.
- **D9. La inclinación no carga la suspensión.** En una curva estacionaria la carga normal efectiva es m·g/cos φ (a 40° son +30 %), y el radio de rodadura y el punto de contacto se desplazan lateralmente por el perfil toroidal (Cossalter; Lot 2004). El plano vertical no recibe nada de `phi`.

### 2.3 Plano longitudinal

Hice una prueba de 6 s en plano, con asfalto, desde 20 m/s y forzando `ctrl` en `_fisica`. Mi script está en el scratchpad y no toca el proyecto.

| freno | SUBPASOS | desaceleración media | cabeceo máximo | resultado |
|---|---|---|---|---|
| 0.3 | 6 / 24 | 3.90 / 3.93 m/s² | 2.3° | ok |
| 0.7 | 6 / 24 | 6.48 / 6.70 m/s² | 4.1° | ok, pero lejos de ≈9.5 m/s² |
| 1.0 | 6 / 24 | — | **204° / 225°** | **se voltea (stoppie)** con ABS activo |

- **D10. Falta mitigación del levantamiento trasero.** El ABS (fisica.py:282-286) solo mira el deslizamiento. Con 1600 N·m por rueda (config.py:45) el par total pide ≈13 m/s², más que la desaceleración de vuelco g·b/h ≈ 9.7 m/s². Bosch MSC limita el freno delantero según la tasa de cabeceo y la aceleración longitudinal. Hoy la red tiene que aprender a no frenar a fondo. Es una limitación realista de una moto **sin** MSC, pero inconsistente con "ABS/TCS como moto real".
- **D11. La curva de agarre mezcla magnitudes** (fisica.py:263-268): `tanh(|slip|/V_DESLIZ)` usa la velocidad de deslizamiento en m/s y `caida` usa la relación de deslizamiento. El pico efectivo cambia con la velocidad: con V_DESLIZ=0.8 m/s, a 5 m/s el 76 % se alcanza con 16 % de deslizamiento y a 30 m/s con 2.7 %. Una Magic Formula en relación de deslizamiento κ es la práctica estándar.
- **D12. Convergencia temporal.** Al acelerar, SUBPASOS 6 y 24 coinciden a 0.1 %. Al frenar fuerte difieren entre 2 y 6 % en la distancia, porque el contacto rígido (SUELO_K=150 kN/m, ω·dt≈0.7) domina. SUBPASOS=6 es aceptable, pero está al borde en transitorios de contacto.

### 2.4 Ruido y perturbaciones

- **D13.** Las perturbaciones `empujon` y `deriva` (fisica.py:192-193) son **un solo escalar compartido por toda la población** en cada paso de control (números aleatorios comunes). Es útil para comparar individuos de forma justa en el GA, pero debe documentarse como decisión explícita.
- **D14.** El ruido es blanco por paso de control y no está escalado por √dt: cambiar `DT_CONTROL` cambia la dificultad. Además usa `self.vx` (eje x del mundo) en vez de la rapidez `v`.
- **D15.** La red observa el estado **verdadero** sin ruido ni latencia (`phi`, `incld`, `mu` adelante, `kappa` exacta; fisica.py:149-181). Ninguna moto real tiene eso. Sin estimación de estado, la historia sim-to-real ante Bosch no se sostiene.

---

## 3. Propuestas priorizadas

Leyenda de riesgo: el riesgo es para **el aprendizaje ya logrado** (pesos en `mejor_moto.json` y `poblacion.npz`).

### P0 — Suite de validación física (`pruebas/test_fisica.py` + `validacion.py`)
- **Qué:** tests automáticos con pytest (o con `assert` sin pytest) y una figura de validación.
- **Por qué:** frente a una compañía, lo primero que se pregunta es "¿cómo saben que la física es correcta?".
- **Cómo:**
  1. Benchmark de Meijaard: con las matrices M, C1, K0, K2 de la Tabla 2 del paper, los eigenvalores a v=2 m/s deben coincidir a 10⁻⁶. La velocidad de weave es 4.2923825 m/s y la de capsize 6.0242620 m/s. **Ya lo reproduje** con numpy y `scipy.optimize.brentq`: 4.29238254 y 6.02426202.
  2. Frenada y vuelco: la desaceleración máxima sin volcar ≈ g·b/h, y la distancia ≈ v²/(2·μ_ef·g).
  3. Umbral de wheelie: par en la rueda ≈ m·g·a·r/h.
  4. Frecuencias de suspensión: 1.5–2.5 Hz para la masa suspendida y 10–18 Hz para la no suspendida.
  5. Convergencia: el error entre SUBPASOS 6, 12 y 24 debe quedar por debajo de un umbral.
  6. Energía: sin fricción, amortiguamiento ni motor, la energía mecánica oscila acotada (Euler semiimplícito) y no deriva.
  7. Curva estacionaria: φ ≈ atan(v²κ/g).
  8. Simetría izquierda/derecha.
- **Archivo:** nuevos `pruebas/`; no toca la simulación.
- **Riesgo:** nulo. **Esfuerzo:** 1–2 días.

### P1 — Elipse de fricción y carga por rueda (D7, D8)
- **Qué:** capacidad lateral por rueda `Fy_max,i = sqrt((μ_i·Fn_i)² − ft_i²)`, y luego `a_lat,max = Σ Fy_max,i / m_total`.
- **Por qué:** es la física central de frenar en curva, la que vende el MSC de Bosch.
- **Cómo:** reemplazar fisica.py:326-327 usando el `fn` y el `ft` que ya existen en cada subpaso. Mantener `PERDIDA_LATERAL` solo como término de bloqueo.
- **Riesgo:** medio-bajo. Endurece curvas con freno o gas; el currículo puede absorberlo. Conviene un flag `FRICCION_COMBINADA`. **Esfuerzo:** 0.5 día.

### P2 — MSC "a la Bosch": ABS en curva, mitigación del levantamiento trasero y antiwheelie (D10)
- **Qué:**
  - Mitigación del levantamiento trasero: recortar el freno delantero si `Fn_trasera < 0.1·m·g` o si la tasa de cabeceo `om < −umbral`.
  - Antiwheelie: el TCS recorta el par si `th > umbral` o si `om > umbral`.
  - ABS en curva: `ABS_OBJ` y el reparto de frenado dependen de |φ|.
- **Por qué:** hoy un frenazo total en plano voltea la moto aunque el ABS esté activo. Estas funciones son las de una moto de serie actual (KTM 2014 en adelante).
- **Archivo:** fisica.py:275-286 y config.py.
- **Riesgo:** bajo; hace la tarea más fácil, nunca más difícil. **Esfuerzo:** 0.5 día.

### P3 — CMG físico con cardán (D5, D6)
- **Qué:** estado α (ángulo de cardán) con su tasa α̇ comandada por un servo con límite de tasa (|α̇| ≤ 2–4 rad/s) y de ángulo (|α| ≤ 75°).
  - Par de alabeo: τ_φ = h·α̇·cos α.
  - Par en guiñada: h·α̇·sin α. Es cero con el par en tijera, que conviene mantener como opción.
  - **Se respeta la decisión del usuario** de que el CMG dependa de la velocidad: h = I_r·Ω_r con Ω_r = n·ω_rueda (rotor movido por la transmisión), saturado en Ω_max. Así `CMG_EXP` se vuelve física y no un ajuste a mano.
  - La saturación sale sola cuando |α| se acerca al límite. La observación `cmg_sat` se sustituye por `α/α_max`, que tiene el mismo rango [−1, 1] y la misma semántica: así se conserva la entrada 7 de la red.
- **Por qué:** es auditable en N·m y N·m·s, coincide con la literatura (Thanh 2008, Yetkin 2014, IJCAS 2020) y con el Lit C-1.
- **Archivo:** fisica.py:354-363 y config.py:87-95.
- **Riesgo:** medio. Se recalibra I_r para que V_CRITICA siga en ≈18–20 km/h, comparando contra la tabla actual. **Esfuerzo:** 1–2 días.

### P4 — Módulo lateral físico opcional: Whipple–Meijaard → Sharp (D1–D4). Es el núcleo del "nivel doctorado"
- **Qué:** nuevo `dinamica_lateral.py` con un flag `MODELO_LATERAL = "simple" | "whipple" | "sharp"`.
  1. **Whipple linealizado:** las fórmulas del Apéndice A de Meijaard (2007) calculan M, C1, K0 y K2 a partir de 4 cuerpos rígidos (cuadro trasero con el lastre, horquilla, dos ruedas), la geometría (distancia entre ejes w, trail c, lanzamiento λ) y las inercias. Hay que añadir a config.py el lanzamiento (≈24–27°) y el trail (≈0.09–0.11 m) típicos de una moto.
     - Estado: (φ, δ, φ̇, δ̇).
     - Entradas: par de alabeo (CMG + lastre) y par de dirección.
     - La guiñada y la posición lateral salen de la cinemática del benchmark: ψ̇ = (v·δ + c·δ̇)·cos λ / w.
     - Integración: Euler semiimplícito o RK2, vectorizado (matrices 2×2 por velocidad; se pueden tabular en v).
  2. **Sharp con neumáticos:** se agregan fuerzas laterales por neumático, `Fy = Cα·α + Cγ·φ` (camber; Cossalter–Doria–Lot), con relajación `(σ/v)·Ḟy + Fy = Fy_ss`, saturadas por la elipse de P1. Aquí emergen el **wobble** y el **weave**, y el amortiguador de dirección (`AMORT_DIRECCION`) se vuelve un c_δ físico en N·m·s/rad. Así se puede mostrar el compromiso clásico: el amortiguador estabiliza el wobble pero puede desestabilizar el weave a alta velocidad (Sharp et al. 2004; Limebeer & Sharp 2006).
  3. **Lazo interno automático** (no aprendido, coherente con la decisión del usuario de que balancear solo con el manubrio es inaprendible): un LQR con ganancias programadas por velocidad (`scipy.linalg.solve_continuous_are` fuera de línea, tabla de 1 a 40 m/s) que use CMG + lastre + par de dirección para seguir una **inclinación o guiñada objetivo**.
     - La red conserva sus 3 salidas, pero la tercera pasa a significar "curvatura o inclinación pedida" en lugar de ángulo de manubrio.
     - La contradirección la ejecuta el lazo interno, como en una moto autónoma real (BMW acciona la dirección con un servo).
     - La dependencia de la velocidad (mínimo 30 km/h) **emerge**: el giroscopio de las ruedas escala con v, el trail y el camber con v², y h_CMG(v) viene de P3. Se calibra para conservar V_CRITICA ≈ 18–20 km/h.
- **Entregables para presentar:**
  - Lugar de raíces de los eigenvalores contra v (weave, wobble, capsize) para la moto del proyecto.
  - Comparación con el benchmark.
  - Estudio paramétrico del trail variable, al estilo Honda Riding Assist: cómo se mueven las velocidades críticas al cambiar el trail.
- **Riesgo:** **alto** para los pesos actuales; requiere reentrenar con `--nuevo` o con *fine-tuning* desde terrenos. Mitigación: flag con "simple" por defecto hasta validar, y conservar los rangos de las observaciones. **Esfuerzo:** 4–6 días (Whipple 2, Sharp 2, LQR y calibración 1–2).

### P5 — Neumático Magic Formula longitudinal por material (D11)
- **Qué:** `Fx = D·sin(C·atan(B·κ − E·(B·κ − atan(B·κ))))` con D = μ·Fn y κ = relación de deslizamiento (se mantiene el denominador regularizado `max(|vt|, 1)` para baja velocidad).
  - Tabla B, C, E por material: el asfalto tiene un pico marcado (C≈1.6–1.9); en grava y arena la curva es monótona y sin pico; en hielo la rigidez es baja.
- **Archivo:** fisica.py:262-268 y terreno.py (columnas en `MATERIALES`).
- **Riesgo:** medio-bajo si se calibra para que el pico quede en κ≈0.12–0.15, como `DESLIZ_PICO`. **Esfuerzo:** 1 día.

### P6 — Acoplar la inclinación al plano vertical (D9)
- **Qué:** carga efectiva `m·g/cos φ` en la suspensión y el contacto (una fuerza vertical extra sobre el chasís en el marco de la pista), y contacto desplazado según el radio de corona del neumático.
- **Riesgo:** bajo. **Esfuerzo:** 0.5 día.

### P7 — Sensores realistas y estimación de estado (D15)
- **Qué:**
  - Capa `sensores.py`: IMU (giróscopo con sesgo y paseo aleatorio, acelerómetros), encoders de rueda, latencia de 1 paso de control y ruido en lidar y μ.
  - Un estimador de inclinación (filtro complementario o Kalman de 2 estados como en Maceira 2021) alimenta a la red en lugar de `phi` verdadero.
  - Randomización de dominio: masa, altura del CG y μ ±10–15 % por pista.
- **Por qué:** es el puente sim-to-real que cualquier fabricante va a exigir.
- **Riesgo:** medio (aprender cuesta más). Introducirlo como nivel 9 del currículo o con un flag. **Esfuerzo:** 1–2 días.

### P8 — Ruido bien escalado y explícito (D13, D14)
- **Qué:** sacudida ∝ σ·√(DT_REF/DT_CONTROL), con DT_REF=1/30 para no cambiar la dificultad actual. Usar `v` en vez de `vx`. Flag `RUIDO_COMUN=True` documentado (números aleatorios comunes).
- **Riesgo:** bajo; con los valores actuales es idéntico. **Esfuerzo:** 1 hora.

### P9 — Rendimiento para poder subir SUBPASOS (D12)
- **Qué:** compilar el núcleo `_fisica` con `numba.njit` (ya está instalado), en un bucle sobre las motos o con `parallel=True` en 8 núcleos.
- **Por qué:** permite SUBPASOS=12 al mismo costo y deja holgura para P4. El resultado debe coincidir bit a bit (o a 1e-12) con la versión numpy, y eso se verifica con P0.
- **Riesgo:** nulo para el aprendizaje si P0 pasa. **Esfuerzo:** 1–2 días. Es tema compartido con el experto en cómputo.

**Orden sugerido:** P0 → P8 → P2 → P1 → P3 → P5 → P6 → P9 → P4 → P7. P4 es el que más valor académico tiene; conviene hacerlo en una rama o con un flag, y con P0 listo antes.

---

## 4. Cómo validar la física (plan concreto)

1. **Validación cruzada con el benchmark:** `dinamica_lateral.whipple_matrices(params_benchmark)` debe dar las matrices de la Tabla 2 de Meijaard (2007) a 10⁻¹⁰. Los eigenvalores contra v en [0, 10] m/s deben reproducir la Fig. 3 del paper (weave 4.292 m/s, capsize 6.024 m/s). Así se separa "la implementación es correcta" de "los parámetros de la moto son razonables".
2. **Simulación no lineal contra lineal:** con perturbaciones pequeñas (φ₀ = 0.5°), la integración temporal debe coincidir con la respuesta modal (la frecuencia del weave, con error de 1 %).
3. **Plausibilidad de motocicleta:** la frecuencia del weave debe salir en 2–4 Hz y la del wobble en 6–10 Hz a velocidades de autopista (rangos de Sharp 1971 y Cossalter 2006). Si no, revisar inercias y rigideces.
4. **Pruebas de maniobra estándar:** frenada en recta con ABS (distancia y desaceleración), *steady-state circular test* (φ contra a_lat), cambio de carril tipo ISO 3888 adaptado a moto, y *step steer* para medir el retardo por contradirección.
5. **Invariantes:** simetría izquierda/derecha (espejo de κ y lat), conservación de la energía sin disipación, ninguna fuerza normal negativa, y |ft| ≤ μ·Fn siempre (elipse).
6. **Regresión del aprendizaje:** antes y después de cada cambio, evaluar `mejor_moto.json` en 20 pistas fijas por nivel y reportar la tasa de meta y el tiempo medio. Así se mide cuánto "rompe" cada mejora.

---

## 5. Lo que **no** debería cambiarse (riesgos)

1. **No quitar el CMG ni volver al equilibrio solo con el manubrio.** El usuario ya comprobó que es inaprendible para un GA con MLP 35-20-3. Toda la física nueva de P4 debe ir con un **lazo interno automático**.
2. **No eliminar la dependencia de la velocidad (mínimo 30 km/h).** Si P3 y P4 la hacen emerger físicamente, hay que **calibrar para conservar V_CRITICA ≈ 18–20 km/h** y que las pistas (diseñadas para `V_DISENO = 9.5 m/s`, terreno.py:241-245) sigan siendo factibles.
3. **No bajar SUBPASOS de 6.** El contacto rígido (ω·dt≈0.7–0.9 con tope) está cerca del límite de estabilidad del Euler semiimplícito. Si se endurece algo (SUELO_K, TOPE_K), hay que subir SUBPASOS o usar numba.
4. **No cambiar el orden ni el rango de las 35 observaciones** sin migrar los pesos. Si una entrada cambia de significado, mantener el rango [−1, 1] o [−2, 2] (por ejemplo `cmg_sat` → `α/α_max`).
5. **No cambiar el integrador por RK4 o uno implícito "por elegancia"** sin necesidad: el Euler semiimplícito es simpléctico, barato y estable aquí. RK4 cuesta 4 veces más y no mejora el contacto con no suavidades.
6. **No reemplazar la vista lateral 2D por un multicuerpo 3D completo** (tipo MBDyn o Chrono). Sería inviable para 80 motos × 3 pistas por generación en numpy. La arquitectura correcta es **2D longitudinal + modelo lateral linealizado de 4 a 6 estados acoplado por carga y fricción**, que es exactamente lo que hacen Sharp y Limebeer para estudiar la estabilidad.
7. **No activar a la vez P1, P4, P5 y P7.** Hay que introducirlos uno por uno, con flag y regresión (sección 4.6), para atribuir cualquier caída del aprendizaje.
8. **Mantener las ayudas (ABS, TCS, amortiguador) como automáticas**, igual que en una moto de serie. Hacer la mitigación del levantamiento trasero (P2) parte del ABS, no una tarea que aprenda la red.

---

## 6. Referencias

1. Meijaard J.P., Papadopoulos J.M., Ruina A., Schwab A.L. (2007). Linearized dynamics equations for the balance and steer of a bicycle: a benchmark and review. *Proc. R. Soc. A* 463:1955–1982. https://doi.org/10.1098/rspa.2007.1857
2. Moore J.K. et al. BicycleParameters — Benchmark Carvallo-Whipple Model. https://bicycleparameters.readthedocs.io/stable/gallery/examples/plot_benchmark.html
3. Kooijman J.D.G., Meijaard J.P., Papadopoulos J.M., Ruina A., Schwab A.L. (2011). A bicycle can be self-stable without gyroscopic or caster effects. *Science* 332:339–342. https://doi.org/10.1126/science.1201959
4. Sharp R.S. (1971). The stability and control of motorcycles. *J. Mech. Eng. Sci.* 13(5):316–329. https://doi.org/10.1243/JMES_JOUR_1971_013_051_02
5. Sharp R.S., Evangelou S., Limebeer D.J.N. (2004). Advances in the modelling of motorcycle dynamics. *Multibody Syst. Dyn.* 12:251–283. https://doi.org/10.1023/B:MUBO.0000049195.60868.A2
6. Limebeer D.J.N., Sharp R.S. (2006). Bicycles, motorcycles, and models. *IEEE Control Systems Magazine* 26(5):34–61. https://doi.org/10.1109/MCS.2006.1700044
7. Åström K.J., Klein R.E., Lennartsson A. (2005). Bicycle dynamics and control. *IEEE Control Systems Magazine* 25(4):26–47. https://doi.org/10.1109/MCS.2005.1499389
8. Cossalter V. (2006). *Motorcycle Dynamics*, 2ª ed. Lulu. ISBN 9781430308614.
9. Cossalter V., Doria A., Lot R. (2003). Dynamic properties of motorcycle and scooter tires: measurement and comparison. https://core.ac.uk/works/29482016
10. Lot R. (2004). A motorcycle tire model for dynamic simulations: theoretical and experimental aspects. https://research.unipd.it/handle/11577/143336
11. Pacejka H.B. *Tyre and Vehicle Dynamics*. Butterworth-Heinemann (Magic Formula).
12. Thanh B.T., Parnichkun M. (2008). Balancing control of Bicyrobo by PSO-based structure-specified mixed H2/H∞ control. *IJARS* 5(4):395–402. https://doi.org/10.5772/6235
13. Yetkin H. et al. (2014). Gyroscopic stabilization of an unmanned bicycle. ACC 2014. https://web.stanford.edu/~kalouche/docs/ACC_2014.pdf
14. Active balancing control for unmanned bicycle using scissored-pair CMG (2020). *Int. J. Control Autom. Syst.* https://pure.seoultech.ac.kr/en/publications/active-balancing-control-for-unmanned-bicycle-using-scissored-pai/
15. ASME. Finding the Balance (Lit Motors C-1). https://www.asme.org/topics-resources/content/finding-the-balance
16. Honda Riding Assist — SAE Mobility Engineering. https://www.mobilityengineeringtech.com/component/content/article/43213-sae-ma-02501
17. Yamaha MOTOBOT — IEEE Spectrum. https://spectrum.ieee.org/cars-that-think/transportation/self-driving/watch-yamahas-humanoid-robot-ride-a-motorcycle-around-a-racetrack
18. BMW Motorrad ConnectedRide autonomous R 1200 GS. https://webbikeworld.com/bmw-connectedride-motorcycle/
19. Bosch Motorcycle Stability Control. https://www.eenewseurope.com/en/stability-control-reaches-motorbikes/ ; https://www.mobilityengineeringtech.com/component/content/article/45008-sae-ma-01353
20. Boniolo I., Savaresi S.M., Tanelli M. (2012). Lean angle estimation in two-wheeled vehicles with a reduced sensor configuration. https://re.public.polimi.it/handle/11311/657466
21. Maceira D. et al. (2021). Roll angle estimation of a motorcycle through inertial measurements. *Sensors* 21:6626. https://doi.org/10.3390/s21196626

*Nota de verificación:* las matrices del benchmark (M, C1, K0, K2) y las velocidades críticas se verificaron numéricamente en esta ronda: weave 4.2923825 m/s y capsize 6.0242620 m/s, iguales al paper. Las pruebas de frenada y de linealización usaron scripts temporales fuera del proyecto, con simulaciones de 4 a 8 s de una sola moto.
