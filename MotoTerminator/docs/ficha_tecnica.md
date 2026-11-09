<!-- Ficha técnica de 1 página. Las cifras medidas van con {{RESULTADO:...}} (Fase B).
     Las cifras sin marcador son parámetros de diseño copiados de config.py. -->

# MT-Bench · Ficha técnica

**Banco de pruebas virtual de controladores para motocicleta sin piloto** · Repositorio: MotoTerminator · Versión {{RESULTADO:version_commit}} · `config_hash` {{RESULTADO:config_hash}}

| Rubro | Especificación |
|---|---|
| **Lenguaje y dependencias** | Python ≥ 3.8 y numpy (obligatorias). Pillow para mapas, matplotlib y scipy para reportes; tkinter para la GUI. |
| **Tipo de modelo** | Orden reducido, vectorizado (N motos en paralelo). Integración Euler semi-implícita. |
| **Plano longitudinal-vertical** | Chasís rígido de 3 GDL (x, y, cabeceo), 290 kg incluido el lastre de 60 kg. Dos ruedas de 18 kg (r = 0.38 m) con 2 GDL de traslación más giro. Suspensión resorte-amortiguador con topes. Contacto con penalización, 9 puntos por rueda. |
| **Guiñada y posición lateral** | Cinemática de bicicleta ω = v·tanδ/L. Límite de agarre lateral μ·g. Estado de derrape. |
| **Inclinación** | Fenomenológica: inclinación cuasi-estática filtrada más péndulo invertido con estabilizador f(v). **No es Whipple/Sharp.** |
| **Neumático** | μ por material, pico de agarre con 15 % de deslizamiento y pérdida del 30 % al bloquear o patinar. Sin elipse de fricción por defecto. |
| **Actuadores** | Motor de 520 N·m / 45 kW. Frenos de 1600 N·m por rueda (40/60). Par de cabeceo ±700 N·m. Dirección con filtro de 0.15 s y 3 rad/s. CMG y lastre como pares PD saturados (automáticos). |
| **Ayudas** | ABS y TCS por deslizamiento, amortiguador de dirección. MSC y fricción combinada como banderas opcionales, apagadas por defecto. |
| **Pasos de tiempo** | Control a 30 Hz, física a 180 Hz (6 subpasos). |
| **Sensores (observación)** | 35 entradas: estado del vehículo, posición en el carril, curvatura adelante (3 distancias), μ adelante y 6 muestras de altura del terreno (1–12 m). Perfectos por defecto; ruido, sesgo y latencia opcionales (`sensores.py`). |
| **Controladores incluidos** | Red 35-20-3 tanh (783 parámetros) entrenada por algoritmo genético. Baselines PD y aleatorio. Interfaz `controlador(obs, sim) → (n, 3)` para controladores externos. |
| **Escenarios** | 8 niveles procedurales con 9 materiales (μ de 0.12 a 1.0), curvatura de hasta 0.065 m⁻¹ y 160–320 m de largo. Calles de OpenStreetMap con rutas de ≈250–950 m, sentidos respetados, asfalto plano, sin tráfico. |
| **Protocolo de evaluación** | Semillas reservadas (2³¹ + 1000·nivel + j), sin rebobinado, IC Clopper-Pearson, fallas/km con IC de Poisson, robustez STL (8 requisitos) y curvas de fragilidad. |
| **Verificación** | Benchmark de Meijaard 2007: weave {{RESULTADO:meijaard_weave}} m/s, capsize {{RESULTADO:meijaard_capsize}} m/s. Pruebas de determinismo y regresión dorada contra v9. |
| **Rendimiento medido** | {{RESULTADO:bench_ms_por_paso_80}} ms por paso de control con N = 80; {{RESULTADO:tiempo_generacion_s}} s por generación ({{RESULTADO:hardware}}). |
| **Resultado de referencia** | Llegada limpia, nivel 1, pistas reservadas: {{RESULTADO:tasa_limpia_nivel1_ga}} (IC 95 % {{RESULTADO:ic95_nivel1_ga}}), con n = {{RESULTADO:n_episodios_nivel1}}. |
| **Salidas** | CSV y JSON por episodio y por generación, figuras PNG (`reporte.py`), reporte de seguridad en Markdown. |
| **Licencia** | Pendiente de decisión del autor (ver `docs/licencia_y_datos.md`). Datos OSM bajo ODbL; imagen satelital sólo para visualización. |
| **TRL** | 2–3 (simulación de orden reducido, sin validación física). |
| **Limitaciones clave** | La red no gobierna el equilibrio. Sin contradirección. Vuelco en frenada total. Observaciones privilegiadas. Corridas cortas (niveles 1–3). |
