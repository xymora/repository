<!--
  MT-Bench paper draft — Phase A (text only).
  RULE: every number marked {{RESULTADO:...}} must be filled ONLY from files in resultados/
  produced by experimentos.py / evaluacion.py / validacion_fisica.py / bench.py (Phase B).
  Never type a number by hand. Numbers that appear without a marker are configuration
  constants copied from config.py (design parameters, not results).
-->

# Curriculum Neuroevolution for Riderless Two-Wheeler Control on Procedural and OpenStreetMap Roads: A Reproducible Reduced-Order Testbed

**Authors:** {{AUTOR:nombres_y_afiliacion}}
**Testbed:** MT-Bench (repository name: MotoTerminator) · **Version:** {{RESULTADO:version_commit}} · **Date:** {{RESULTADO:fecha_corridas}}

---

## Abstract

{{RESULTADO:abstract_final}} — *to be written in Phase B, ≤ 200 words, using this template:*

> Riderless two-wheelers are used as test platforms for motorcycle rider-assistance systems, but open, lightweight and statistically rigorous testbeds for comparing their controllers are scarce. We present MT-Bench, a vectorized reduced-order simulator of a riderless motorcycle with an active roll stabilizer (a saturating control-moment-gyroscope model plus an active ballast mass), ABS and traction control. It runs on procedurally generated off-road tracks (8 curriculum levels, 9 surface materials) and on road geometry extracted from OpenStreetMap. A 35-20-3 neural policy is trained by a genetic algorithm with a curriculum. We define an evaluation protocol that separates training from testing: held-out track seeds, no rewind after failures, Clopper–Pearson intervals for clean-arrival rates, and bootstrap confidence intervals over {{RESULTADO:n_semillas}} independent training seeds. In short runs ({{RESULTADO:n_generaciones}} generations), the evolved policy reaches a held-out clean-arrival rate of {{RESULTADO:tasa_limpia_nivel1_ga}} (95% CI {{RESULTADO:ic95_nivel1_ga}}) on level 1, compared with {{RESULTADO:tasa_limpia_nivel1_pd}} for a hand-tuned PD baseline. We report the model's verified limitations: roll balance is not governed by the policy, there is no countersteering, and full braking can cause a pitch-over. We release the code to support reproducible comparison of two-wheeler controllers.

**Index Terms** — motorcycle dynamics, riderless vehicles, neuroevolution, curriculum learning, scenario-based testing, reproducibility.

---

## I. Introduction

Motorcycle manufacturers and suppliers increasingly use self-riding or self-balancing two-wheelers as **research instruments**, not products. BMW Motorrad presented its autonomous R 1200 GS as a testbed for rider-safety systems [12]. Honda's Riding Assist [9] and Yamaha's MOTOROiD/AMCES [11] explored low-speed self-balancing, and Yamaha's MOTOBOT [10] studied high-speed robotic riding. In parallel, rider-assistance functions such as cornering ABS and stability control [13] and radar-based assistance [14] have reached series production. Scenario-based virtual testing is becoming the main way to validate such functions [31], [34].

Commercial motorcycle simulators (e.g., dSPACE ASM Bike [41], IPG MotorcycleMaker [42]) target high-fidelity MIL/SIL/HIL workflows. They are closed and costly, and they are not designed to train and statistically compare many candidate controllers. Learning-based balance control of two-wheelers has been demonstrated, notably the Tianjic neuromorphic bicycle [16]. However, such work rarely reports held-out evaluation with confidence intervals, which recent reinforcement-learning methodology deems necessary [28], [29].

This paper makes four **bounded** contributions:

1. **MT-Bench**, an open, vectorized reduced-order simulator of a riderless motorcycle with an active roll stabilizer, ABS/TCS and a two-lane road. It runs on procedural multi-surface tracks and on OpenStreetMap road geometry (Sec. III).
2. A **curriculum neuroevolution baseline**: a 783-parameter policy trained by a genetic algorithm across 8 terrain levels, with automatic transfer to real street geometry (Sec. IV).
3. An **evaluation protocol** that separates training from testing. It uses held-out seeds, no rewind, clean-arrival rates with exact intervals, failures per km, signal-temporal-logic (STL) requirement robustness and fragility curves (Sec. V).
4. An **honest characterization of the model's limits**, including physics checks against the Whipple–Meijaard benchmark [1] and documented failure modes (Sec. VII).

We do **not** claim realistic full-vehicle dynamics, transfer to a physical motorcycle, or compliance with any functional-safety standard.

---

## II. Related Work

### A. Two-wheeler dynamics

The linearized Carvallo–Whipple bicycle model, with its benchmark parameters and eigenvalues, is the standard reference for lateral dynamics [1]. Kooijman et al. showed that self-stability requires neither gyroscopic nor caster effects; the mass distribution matters [2]. Motorcycle models add tire side-slip and camber forces. These models produce the *weave* (≈2–4 Hz) and *wobble* (≈6–10 Hz) modes [3], [4], [7]. Reviews of modelling and control are given in [5], [6], and tire modelling follows the Magic Formula [8]. Our simulator does **not** implement these lateral models. It uses a reduced-order phenomenological roll model (Sec. III-C) and treats the benchmark only as a verification target and a roadmap item.

### B. Active stabilization of two-wheelers

Honda Riding Assist balances at walking speed **without** a gyroscope by changing fork geometry and applying small steering inputs [9]. Yamaha's AMCES balances by moving the vehicle's mass center [11]. Lit Motors' C-1 uses two single-gimbal control-moment gyroscopes (CMGs) for redundancy [15]. CMG balancing of unmanned bicycles has been studied in [17], [18]. BMW's autonomous GS relies on steering actuation without a gyroscope [12]. MT-Bench models two of these concepts, a CMG and an active ballast mass, as **saturating torque sources** rather than as physical mechanisms.

### C. Learned control and neuroevolution

The Tianjic chip balanced a riderless bicycle with a spiking network while running perception networks [16]. Neuroevolution ranges from topology-evolving methods [19] to evolution strategies [20], deep genetic algorithms [21], CMA-ES [22] and random search [45]. Curriculum learning [23], prioritized level replay [24] and open-ended environment generation [25] address learning with increasing difficulty. Procedural benchmarks require separate train and test levels to measure generalization [26]. Domain randomization helps sim-to-real transfer [27].

### D. Safety validation and evaluation methodology

ISO 21448 (SOTIF) addresses hazards that arise without any system fault [33]. ISO 34502 frames scenario-based evaluation [34], and ASAM OpenSCENARIO standardizes scenario description [35]. Accumulating test distance alone cannot demonstrate reliability [31]. ML-based systems make validation harder because the training objective becomes an implicit specification [32], and objective misspecification enables reward hacking [30]. STL with quantitative robustness [36], [37] and black-box falsification [38] support requirement-based testing. Runtime assurance architectures such as Simplex [44] are future work here. For statistical reporting we follow [28], [29] and use exact binomial [39], Poisson [46] and bootstrap [40] intervals.

---

## III. System Model

All quantities are SI units. Parameters are listed in Table A1 (generated from `config.py`). The simulator integrates **N vehicles in parallel** as numpy arrays and uses a **semi-implicit Euler** scheme. Control runs at 30 Hz with 6 physics sub-steps, so Δt = 1/180 s.

### A. Longitudinal–vertical plane (multibody, planar)

- **Chassis:** a rigid body with 3 DOF (x, y, pitch θ). Its mass is 290 kg: a 230 kg robot plus a 60 kg active ballast. Pitch inertia is 55 + 60·0.45² kg·m².
- **Wheels:** two wheels (18 kg, r = 0.38 m), each with 2 translational DOF plus spin.
- **Suspension:** each wheel is connected to the chassis by a spring–damper expressed in the chassis frame (k = 22 kN/m, c = 1.5 kN·s/m, stiff longitudinal link). Bump stops act at 0.20 m compression and 0.06 m extension.
- **Tire–ground contact:** penalty-based (k = 150 kN/m, c = 2 kN·s/m). The terrain profile is sampled at 9 points under each wheel, and the deepest penetration defines the normal direction.
- **Longitudinal friction:** μ(material) · F_n · g(s) · tanh(|v_slip| / 0.8). The factor g(s) drops by up to 30% beyond a peak slip ratio of 0.15 (wheel lock or spin). The force is also capped by a numerical stability limit.
- **Other forces:** rolling resistance per material and aerodynamic drag ½ρC_dA = 0.33.
- **Powertrain and brakes:**
  - Rear-wheel torque is limited to 520 N·m and to 45 kW.
  - Brake torque is 1600 N·m per wheel, split 40/60 rear/front.
  - **TCS** and **ABS** scale motor and brake torque proportionally when the slip ratio exceeds 0.15 or 0.18.
- **Pitch actuator:** an internal pitch-torque actuator (±700 N·m) is commanded by the policy.

### B. Yaw and lateral position (kinematic)

- **Steering:** the policy's steering command passes through a first-order filter (τ = 0.15 s) and a rate limit (3 rad/s).
- **Steering angle limit:** δ_max(v) = min(0.35, atan(8·L / v²)), which caps the requested lateral acceleration at about 0.8 g.
- **Yaw rate:** follows the kinematic bicycle relation ω = v·tan δ / L, measured relative to the road curvature κ: ψ̇ = ω − vκ + d_slow.
- **Lateral grip:** the lateral acceleration is capped at μ_max·g·(1 − 0.7·ℓ), where ℓ grows with longitudinal slip. Any excess builds a scalar "skid" state, and the vehicle falls when that state exceeds 2.
- **Low-speed drift:** below 30 km/h, a random heading drift d_slow is injected.

### C. Roll (reduced-order, phenomenological)

Roll is φ = φ_c + φ_w. The two parts are:

- **Quasi-static cornering lean φ_c:** a critically damped second-order filter (ω_n = 8 rad/s, ζ = 0.9) tracks atan(v·ω/g).
- **Perturbation roll φ_w:** obeys an inverted-pendulum-like equation:

  φ̈_w = (g/h) sin φ_w − (ω_g² + g/h)·f(v)·φ_w + w(t)·(1 + 7(1 − f(v))) + u_ballast + u_CMG − c(v)·φ̇_w,

  where h = 0.75 m and f(v) ∈ [0, 1] is a stabilizer-effectiveness curve. f(v) is 0 below 10 km/h and 1 above 30 km/h (exponent 1.9).
- **Ballast and CMG:** u_ballast and u_CMG are **saturating PD laws** on (φ_w, φ̇_w). The CMG authority scales with (v / 8.33 m/s)², and an internal saturation state models finite gimbal capacity (recentering rate 0.35 s⁻¹).
- **Disturbance:** w(t) grows with terrain roughness and speed. It is drawn from a per-track random stream (common random numbers).

This roll model is a **design choice for learnability**, not a derived multibody model (see Sec. VII).

### D. Sensing, actions and termination

- **Observation (35 dimensions):** speed and body rates, pitch, roll and roll rate, CMG saturation, skid, steering angle, lateral position and heading error, predicted lateral offset at 0.8 s, wheel contact, slip and suspension compression, friction coefficient under and 5 m ahead of the vehicle, curvature at three speed-dependent look-ahead distances, the margin to a curve-safe speed, the margin to 30 km/h, and six terrain-height samples at 1–12 m ahead (called "lidar" in the code). These are **privileged, noise-free state variables** unless a sensor filter is enabled (Sec. V-D).
- **Actions (3, in [−1, 1]):** throttle/brake, pitch torque and steering.
- **Termination events:**
  - pitch > 1.5 rad (flip-over);
  - |roll| > 0.8 rad or skid > 2 (fall);
  - |lateral position| > 2 m (off-road);
  - chassis–ground contact (crash);
  - no progress for 4 s (stuck);
  - time-out;
  - finish.
- **Training scaffolding:**
  - After a failure, the vehicle is **rewound** 2 s and continues, up to 3 times.
  - Episodes start at 9 m/s (assisted launch).

### E. Tracks

- **Procedural tracks:** height profiles on a 0.1 m grid with 9 materials (μ from 0.12 for ice to 1.0 for asphalt) and a road-curvature profile.
- **Curriculum levels** add features in this order: hills and bumps; rocks, logs, sand and mud; steps and ditches; ramps, steep grades and snow; ice. Each level also increases amplitude, curvature (up to 0.065 m⁻¹) and length (160–320 m). The generator guarantees that every curve can be taken at 9.5 m/s.
- **OpenStreetMap mode:**
  - Routes follow the shortest path between random intersections and respect one-way streets.
  - Corners are rounded to a radius of about 6–8 m.
  - The surface is assumed flat asphalt (μ = 1) with **no traffic, signals or pedestrians**.
  - Route lengths grow from ≈250 m (level 1) to ≈950 m (level 8).

---

## IV. Learning Method

### A. Policy

The policy is a fully connected network 35-20-3 with tanh activations, 783 parameters in total. It is evaluated in batch for the whole population. Initial weights follow 𝒩(0, 1/fan_in), with a +0.6 bias on the throttle output.

### B. Fitness (training objective, unchanged from the original design)

For a track of length L, fitness is computed as follows.

```
F = 100·progress/L − 1·lean_unnec[deg] − 8·lane_dev[m] − 30·invasion_frac
    + 1[finish]·(50 + 100·min(t_ref / t_finish, 1.5)),    t_ref = L / 15 m/s
    − 20·1[ended by failure] − 20·n_rewinds
```

The terms are:

- **lean_unnec:** the time-averaged deviation between roll and the roll required by the road curvature.
- **lane_dev:** the curvature-weighted mean distance from the lane center (weight up to 4× in curves).
- **invasion_frac:** the fraction of time spent in the opposite lane.

Each generation, fitness is averaged over 3 freshly generated tracks. All individuals share the same tracks and disturbance stream (common random numbers). An optional strict variant (`APTITUD_ESTRICTA`, off by default) is reserved for ablation (Sec. VII-B).

### C. Genetic algorithm

| Setting | Value |
|---|---|
| Population | N = 80 |
| Elitism | 4 |
| Selection | tournament of size 3 |
| Crossover | uniform, p = 0.7 |
| Mutation | per-gene Gaussian, p = 0.1, σ = 0.2 |
| Immigrants | 4% random individuals per generation |

σ is adaptive: it is multiplied by 1.1 (cap 0.4) when the mean best fitness of the last 10 generations does not exceed that of the previous 10, and by 0.97 (floor 0.2) otherwise. Because the champion is re-evaluated on the same tracks, the best fitness of a generation is never below the previous champion's score on those tracks.

### D. Curriculum and transfer

- **Level-up rule:** the level increases when the leader finishes all tracks in 2 consecutive generations.
- **Graduation:** after mastering level 8, the population graduates to OpenStreetMap routes, starting at city level 1 with the terrain-trained weights.
- **Note:** the level-up rule counts arrivals **with** rewinds. The evaluation protocol (Sec. V) does not.

---

## V. Evaluation Protocol

The protocol is implemented in `evaluacion.py` and `experimentos.py`. Its guiding principle is that **no reported number uses training tracks, rewinds or a single seed.**

### A. Seed partition

| Use | Seed range |
|---|---|
| Training tracks | < 2³⁰ |
| Champion validation | 2³⁰ + 1000·level + j |
| Held-out test tracks | 2³¹ + 1000·level + j |
| Test noise streams | 2³¹ + 7919·k |

The ranges are disjoint by construction.

### B. Test conditions

- `max_reintentos = 0`: the first failure ends the episode.
- Each evaluated replica receives its own disturbance stream (`ruido_por_moto = True`).
- Per level and controller: M = {{RESULTADO:n_pistas_eval}} tracks × K = {{RESULTADO:n_ruidos_eval}} noise realizations.

### C. Metrics

1. **Clean-arrival rate:** finish with zero rewinds. Reported with a Clopper–Pearson 95% CI [39].
2. **Arrival rate with rewinds:** reported separately, for comparison with training logs only.
3. **Failures per km:** with a Garwood exact Poisson CI [46].
4. **Failure-mode histogram:** flip, fall, off-road, crash, stuck, time-out.
5. **Mean speed of clean arrivals, minimum lateral margin, and maximum CMG saturation.**
6. **STL requirement robustness ρ** [36], [37], where ρ > 0 means satisfied:
   - R1 lane-keeping: G(|lat − lat_lane| < 1.0)
   - R2 road-edge margin: G(|lat| < 1.7)
   - R3 minimum speed: G(v ≥ 8.33)
   - R4 curve-safe speed: G(v ≤ v_safe + 1)
   - R5 bounded invasion: G(lat > 0 → F[0,2] lat < 0)
   - R6 roll limit: G(|φ| < 0.6)
   - R7 stabilizer reserve: G(|cmg_sat| < 0.9)
   - R8 task completion: F[0,T] x ≥ goal
7. **Sample-size statement:** with zero failures in n episodes, the one-sided 95% upper bound on the failure probability is 1 − 0.05^(1/n). For example, a bound below 1% requires n ≥ 299. The report prints which claim the achieved n supports.

### D. Robustness (fragility curves)

Clean-arrival rate is measured as a function of perturbation magnitude, using `sensores.py` and physics scale factors:

- observation noise and bias;
- actuation latency;
- mass and friction scaling.

### E. Learning curves

- {{RESULTADO:n_semillas}} independent GA runs × {{RESULTADO:n_generaciones}} generations, levels 1–3, each in an isolated data directory.
- Curves show the mean and a 95% bootstrap CI over seeds (10 000 resamples) [40].
- Champions are compared on the held-out set, not on training fitness.

### F. Baselines

- **Random:** a random 35-20-3 network with the same initialization.
- **PD:** a hand-tuned controller (`controladores.py`) that combines lane and heading feedback with a target speed derived from curvature and friction.

All controllers use the same simulator interface (`controlador=`).

### G. Physics verification

- **Whipple–Meijaard benchmark** [1], implemented stand-alone in `validacion_fisica.py`: reproduction of the benchmark eigenvalues and of the weave and capsize speeds (Table A2).
- **Straight-line full-braking test:** peak pitch and mean deceleration.
- **Determinism and batch-invariance tests:** the same seed gives identical fitness, and a vehicle evaluated alone gives the same result as in a batch.
- **Golden regression** against the archived v9 implementation.

---

## VI. Results

*All entries are filled in Phase B from `resultados/`. Figures are generated by `reporte.py` into `docs/figuras/`.*

### A. Simulator verification

**Table A2. Whipple–Meijaard benchmark reproduction.**

| Quantity | Reference [1] | MT-Bench verification script | Abs. error |
|---|---|---|---|
| Weave speed (m/s) | 4.292 382 5 | {{RESULTADO:meijaard_weave}} | {{RESULTADO:meijaard_err_weave}} |
| Capsize speed (m/s) | 6.024 262 0 | {{RESULTADO:meijaard_capsize}} | {{RESULTADO:meijaard_err_capsize}} |

Full braking on flat asphalt with ABS active: peak pitch {{RESULTADO:frenada_cabeceo_max_deg}}°, mean deceleration {{RESULTADO:frenada_desacel_ms2}} m/s², outcome {{RESULTADO:frenada_resultado}}. This is a documented limitation (Sec. VII-A).

Throughput: {{RESULTADO:bench_ms_por_paso_80}} ms per control step for N = 80 and {{RESULTADO:bench_us_por_moto_320}} µs per vehicle per sub-step for N = 320, on {{RESULTADO:hardware}}.

### B. Learning curves

**Fig. 1** (`docs/figuras/curvas_aprendizaje.png`): best and mean training fitness versus generation, mean ± 95% bootstrap CI over {{RESULTADO:n_semillas}} seeds. Highest level reached: median {{RESULTADO:nivel_max_mediana}}, range {{RESULTADO:nivel_max_rango}}. Wall-clock time per generation: {{RESULTADO:tiempo_generacion_s}} s.

### C. Held-out clean-arrival rates

**Table II. Held-out evaluation (no rewind).** Each cell shows the rate (95% CI).

| Level | GA policy (clean) | GA policy (with rewinds) | PD baseline (clean) | Random (clean) |
|---|---|---|---|---|
| 1 | {{RESULTADO:tasa_limpia_nivel1_ga}} ({{RESULTADO:ic95_nivel1_ga}}) | {{RESULTADO:tasa_reintentos_nivel1_ga}} | {{RESULTADO:tasa_limpia_nivel1_pd}} ({{RESULTADO:ic95_nivel1_pd}}) | {{RESULTADO:tasa_limpia_nivel1_aleatorio}} |
| 2 | {{RESULTADO:tasa_limpia_nivel2_ga}} ({{RESULTADO:ic95_nivel2_ga}}) | {{RESULTADO:tasa_reintentos_nivel2_ga}} | {{RESULTADO:tasa_limpia_nivel2_pd}} ({{RESULTADO:ic95_nivel2_pd}}) | {{RESULTADO:tasa_limpia_nivel2_aleatorio}} |
| 3 | {{RESULTADO:tasa_limpia_nivel3_ga}} ({{RESULTADO:ic95_nivel3_ga}}) | {{RESULTADO:tasa_reintentos_nivel3_ga}} | {{RESULTADO:tasa_limpia_nivel3_pd}} ({{RESULTADO:ic95_nivel3_pd}}) | {{RESULTADO:tasa_limpia_nivel3_aleatorio}} |

Failures per km (GA policy, level 1): {{RESULTADO:fallas_km_nivel1_ga}} (95% CI {{RESULTADO:ic95_fallas_km_nivel1_ga}}). **Fig. 2** (`tasa_limpia.png`) shows the rates with error bars.

### D. Failure modes and requirements

**Fig. 3** (`histograma_fallas.png`). Dominant failure mode: {{RESULTADO:modo_falla_dominante}}. The STL requirement with the lowest median robustness was {{RESULTADO:stl_req_peor}} (ρ = {{RESULTADO:stl_rho_peor}}).

### E. Robustness

**Fig. 4** (`fragilidad.png`). The clean-arrival rate drops to 50% at {{RESULTADO:fragilidad_umbral_50}} under {{RESULTADO:fragilidad_perturbacion}}.

### F. Discussion

{{RESULTADO:discusion}} — *To be written once the numbers exist. Interpret the gap between the rate with rewinds and the clean rate, the GA-vs-PD comparison, and any level at which the GA does not beat the PD baseline. That case must be reported, not hidden.*

---

## VII. Limitations

### A. Physics fidelity (verified findings)

1. **The policy does not govern roll balance.** The perturbation-roll dynamics (Sec. III-C) do not depend on the steering command or on any other network output. The ballast and CMG laws are fixed, hand-designed controllers. The policy affects stability only indirectly, through forward speed. Results must therefore **not** be described as "the network balances the motorcycle".
2. **No countersteering or non-minimum-phase behavior.** Yaw follows steering kinematically, and cornering lean tracks its quasi-static target through a filter. A real single-track vehicle must first steer opposite to the intended turn to initiate lean [5], [6]. Policies trained here are not expected to transfer.
3. **The low-speed instability is imposed, not emergent.** Linearizing the φ_w equation gives stable eigenvalues at all speeds. Low-speed falls arise from actuator saturation and the explicit speed-dependent amplification of disturbances. There is no weave, wobble or capsize mode.
4. **Full braking can pitch the vehicle over even with ABS** (Sec. VI-A), and achievable deceleration is below typical values for ABS-equipped motorcycles. A Bosch-MSC-like rear-lift mitigation exists as an optional, off-by-default flag (`MSC_ACTIVO`) and is not used for the reported results unless stated.
5. **No combined-slip friction ellipse by default.** Lateral grip uses the larger μ of the two wheels without per-wheel load (`FRICCION_COMBINADA` is off by default).
6. **The CMG and ballast are torque abstractions,** with no gimbal kinematics, no parasitic torques and no energy accounting.

### B. Learning and evaluation

1. **Exploitable training objective.** With rewinds, a failure costs 20 points, while finishing 50% faster than the reference speed earns up to +50. The objective can therefore reward trading crashes for speed (reward hacking [30]). Our evaluation neutralizes this by measuring clean arrivals only. The training objective was deliberately left unchanged, and the strict variant is future work.
2. **Privileged, noise-free observations** (exact curvature ahead, friction ahead, terrain heights) unless sensor filters are enabled.
3. **Short runs only:** {{RESULTADO:n_generaciones}} generations, levels 1–3. Claims about levels 4–8 and city driving in earlier project notes are **not** supported by archived artifacts and are not made here.
4. **City mode is a geometric circuit,** not an urban scenario: there is no traffic, intersection logic, signals, pedestrians or speed limits.
5. **Single robot configuration;** no parameter identification against a real vehicle.

### C. Claims we explicitly do not make

Realistic physics. Balance by the gyroscope or by the network. Transfer to a physical motorcycle. Compliance with ISO 26262, ISO 21448 or UL 4600. Any success rate that counts rewinds. Any result based on a single seed.

---

## VIII. Future Work and Technology-Readiness Roadmap

| Step | Content | Exit criterion | TRL |
|---|---|---|---|
| 1 | Current work: reduced-order testbed, held-out protocol, baselines | Reproducible tables with CIs | 2 → 3 |
| 2 | Optional Whipple–Meijaard lateral module, then a Sharp model with tire relaxation and camber [1], [3], [4], with a speed-scheduled LQR inner loop. The policy commands lean or curvature, and countersteering emerges | Benchmark eigenvalues reproduced inside the simulator; weave and wobble frequencies in the plausible range [4], [7] | 3 |
| 3 | Combined-slip friction, MSC-like braking, Magic Formula longitudinal tire [8]; sensor models and state estimation | Braking and steady-turning maneuver tests pass | 3 |
| 4 | Scenario falsification (search over track parameters that minimize STL robustness) [38], rare-event estimation, and export to an OpenSCENARIO-like format [35] | Library of critical scenarios that are reproducible in a third-party tool | 3 → 4 |
| 5 | Runtime assurance (Simplex/CBF) [44]; optimizer comparison (CMA-ES [22], ES [20], PPO); quality-diversity [47]; numba acceleration | Statistically powered comparison | 4 |
| 6 | Parameter identification from a real or scaled vehicle; scaled prototype (IMU + reaction wheel or CMG) | Sim-to-real gap reported | 4 → 5 |

---

## Code and Data Availability

Code: {{RESULTADO:url_repositorio}}. Every figure and table is regenerated by `python experimentos.py ...`, `python evaluacion.py ...` and `python reporte.py`. Road geometry © OpenStreetMap contributors (ODbL) [43]. Satellite imagery is used for visualization only and is not redistributed (see `docs/licencia_y_datos.md`).

---

## References

[1] J. P. Meijaard, J. M. Papadopoulos, A. Ruina, and A. L. Schwab, "Linearized dynamics equations for the balance and steer of a bicycle: A benchmark and review," *Proc. R. Soc. A*, vol. 463, no. 2084, pp. 1955–1982, 2007, doi: 10.1098/rspa.2007.1857.

[2] J. D. G. Kooijman, J. P. Meijaard, J. M. Papadopoulos, A. Ruina, and A. L. Schwab, "A bicycle can be self-stable without gyroscopic or caster effects," *Science*, vol. 332, no. 6027, pp. 339–342, 2011, doi: 10.1126/science.1201959.

[3] R. S. Sharp, "The stability and control of motorcycles," *J. Mech. Eng. Sci.*, vol. 13, no. 5, pp. 316–329, 1971, doi: 10.1243/JMES_JOUR_1971_013_051_02.

[4] R. S. Sharp, S. Evangelou, and D. J. N. Limebeer, "Advances in the modelling of motorcycle dynamics," *Multibody Syst. Dyn.*, vol. 12, pp. 251–283, 2004, doi: 10.1023/B:MUBO.0000049195.60868.A2.

[5] D. J. N. Limebeer and R. S. Sharp, "Bicycles, motorcycles, and models," *IEEE Control Syst. Mag.*, vol. 26, no. 5, pp. 34–61, 2006, doi: 10.1109/MCS.2006.1700044.

[6] K. J. Åström, R. E. Klein, and A. Lennartsson, "Bicycle dynamics and control," *IEEE Control Syst. Mag.*, vol. 25, no. 4, pp. 26–47, 2005, doi: 10.1109/MCS.2005.1499389.

[7] V. Cossalter, *Motorcycle Dynamics*, 2nd ed. Lulu, 2006, ISBN 9781430308614.

[8] H. B. Pacejka, *Tyre and Vehicle Dynamics*. Oxford, U.K.: Butterworth-Heinemann.

[9] Honda Motor Co., "Honda Riding Assist," CES 2017. [Online]. Available: https://global.honda/en/newsroom/news/2017/c170109eng.html

[10] Yamaha Motor Co., "MOTOBOT." [Online]. Available: https://global.yamaha-motor.com/design_technology/technology/motobot/ep3/

[11] Yamaha Motor Co., "MOTOROiD." [Online]. Available: https://global.yamaha-motor.com/design_technology/design/concept/motoroid/

[12] WebBikeWorld, "BMW built a self-driving motorcycle" (ConnectedRide R 1200 GS). [Online]. Available: https://www.webbikeworld.com/bmw-built-self-driving-motorcycle/

[13] SAE Mobility Engineering, "Stability control boosts motorcycle safety" (Bosch MSC). [Online]. Available: https://www.mobilityengineeringtech.com/component/content/article/45008-sae-ma-01353

[14] Ducati, "Multistrada V4 — Electronics" (radar-based ACC/BSD, Bosch). [Online]. Available: https://ducati.com/ww/en/bikes/multistrada/multistrada-v4/electronics

[15] ASME, "Finding the balance" (Lit Motors C-1). [Online]. Available: https://www.asme.org/topics-resources/content/finding-the-balance ; see also U.S. Patent 11 648 994 B2.

[16] J. Pei *et al.*, "Towards artificial general intelligence with hybrid Tianjic chip architecture," *Nature*, vol. 572, pp. 106–111, 2019, doi: 10.1038/s41586-019-1424-8.

[17] B. T. Thanh and M. Parnichkun, "Balancing control of Bicyrobo by particle swarm optimization-based structure-specified mixed H2/H∞ control," *Int. J. Adv. Robot. Syst.*, vol. 5, no. 4, pp. 395–402, 2008, doi: 10.5772/6235.

[18] H. Yetkin *et al.*, "Gyroscopic stabilization of an unmanned bicycle," in *Proc. American Control Conf.*, 2014. [Online]. Available: https://web.stanford.edu/~kalouche/docs/ACC_2014.pdf

[19] K. O. Stanley and R. Miikkulainen, "Evolving neural networks through augmenting topologies," *Evol. Comput.*, vol. 10, no. 2, pp. 99–127, 2002, doi: 10.1162/106365602320169811.

[20] T. Salimans, J. Ho, X. Chen, S. Sidor, and I. Sutskever, "Evolution strategies as a scalable alternative to reinforcement learning," arXiv:1703.03864, 2017.

[21] F. P. Such *et al.*, "Deep neuroevolution: Genetic algorithms are a competitive alternative for training deep neural networks for reinforcement learning," arXiv:1712.06567, 2017.

[22] N. Hansen, "The CMA evolution strategy: A tutorial," arXiv:1604.00772, 2016.

[23] S. Narvekar *et al.*, "Curriculum learning for reinforcement learning domains: A framework and survey," *J. Mach. Learn. Res.*, 2020, arXiv:2003.04960.

[24] M. Jiang, E. Grefenstette, and T. Rocktäschel, "Prioritized level replay," arXiv:2010.03934, 2020.

[25] R. Wang, J. Lehman, J. Clune, and K. O. Stanley, "Paired open-ended trailblazer (POET)," arXiv:1901.01753, 2019.

[26] K. Cobbe, C. Hesse, J. Hilton, and J. Schulman, "Leveraging procedural generation to benchmark reinforcement learning," in *Proc. ICML*, 2020, arXiv:1912.01588.

[27] J. Tobin *et al.*, "Domain randomization for transferring deep neural networks from simulation to the real world," in *Proc. IROS*, 2017, arXiv:1703.06907.

[28] R. Agarwal *et al.*, "Deep reinforcement learning at the edge of the statistical precipice," in *Proc. NeurIPS*, 2021, arXiv:2108.13264.

[29] P. Henderson *et al.*, "Deep reinforcement learning that matters," in *Proc. AAAI*, 2018, arXiv:1709.06560.

[30] D. Amodei *et al.*, "Concrete problems in AI safety," arXiv:1606.06565, 2016.

[31] N. Kalra and S. M. Paddock, "Driving to safety: How many miles of driving would it take to demonstrate autonomous vehicle reliability?" *Transp. Res. A*, vol. 94, pp. 182–193, 2016, doi: 10.1016/j.tra.2016.09.010.

[32] P. Koopman and M. Wagner, "Challenges in autonomous vehicle testing and validation," *SAE Int. J. Transp. Safety*, vol. 4, no. 1, 2016, doi: 10.4271/2016-01-0128.

[33] *Road vehicles — Safety of the intended functionality*, ISO 21448:2022.

[34] *Road vehicles — Test scenarios for automated driving systems — Scenario based safety evaluation framework*, ISO 34502:2022. [Online]. Available: https://www.iso.org/standard/78951.html

[35] ASAM e.V., "ASAM OpenSCENARIO." [Online]. Available: https://www.asam.net/standards/detail/openscenario/

[36] O. Maler and D. Nickovic, "Monitoring temporal properties of continuous signals," in *Proc. FORMATS/FTRTFT*, LNCS 3253, 2004, doi: 10.1007/978-3-540-30206-3_12.

[37] A. Donzé and O. Maler, "Robust satisfaction of temporal logic over real-valued signals," in *Proc. FORMATS*, LNCS 6246, pp. 92–106, 2010, doi: 10.1007/978-3-642-15297-9_9.

[38] A. Corso, R. Moss, M. Koren, R. Lee, and M. Kochenderfer, "A survey of algorithms for black-box safety validation of cyber-physical systems," *J. Artif. Intell. Res.*, vol. 72, pp. 377–428, 2021, doi: 10.1613/jair.1.12716.

[39] C. J. Clopper and E. S. Pearson, "The use of confidence or fiducial limits illustrated in the case of the binomial," *Biometrika*, vol. 26, no. 4, pp. 404–413, 1934, doi: 10.1093/biomet/26.4.404.

[40] B. Efron, "Bootstrap methods: Another look at the jackknife," *Ann. Statist.*, vol. 7, no. 1, pp. 1–26, 1979, doi: 10.1214/aos/1176344552.

[41] dSPACE GmbH, "ASM Bike: Real-time simulation for next-generation motorcycle development." [Online]. Available: https://www.dspace.com/ja/jpn/home/learning-center/recordings/handson/video_ho_asm-bike.cfm

[42] IPG Automotive, "MotorcycleMaker" (CarMaker product family). {{VERIFICAR:url_oficial_ipg_motorcyclemaker}}

[43] OpenStreetMap Foundation, "Copyright and License (ODbL 1.0)." [Online]. Available: https://www.openstreetmap.org/copyright

[44] L. Sha, "Using simplicity to control complexity," *IEEE Softw.*, vol. 18, no. 4, pp. 20–28, 2001, doi: 10.1109/MS.2001.936213.

[45] H. Mania, A. Guy, and B. Recht, "Simple random search provides a competitive approach to reinforcement learning," arXiv:1803.07055, 2018.

[46] F. Garwood, "Fiducial limits for the Poisson distribution," *Biometrika*, vol. 28, no. 3/4, pp. 437–442, 1936, doi: 10.1093/biomet/28.3-4.437.

[47] J.-B. Mouret and J. Clune, "Illuminating search spaces by mapping elites," arXiv:1504.04909, 2015.

---

## Appendix A — Table A1 (parameters)

{{RESULTADO:tabla_parametros_config}} — *generated automatically from `config.py` plus `config_hash` (do not type by hand).*
