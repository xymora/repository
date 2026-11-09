<!-- Resumen ejecutivo para directivos. Las cifras marcadas {{RESULTADO:...}} se llenan
     SOLO desde resultados/ en la Fase B. Nunca escribir cifras a mano. -->

# MT-Bench: banco de pruebas virtual para controladores de motocicletas sin piloto

**Resumen ejecutivo (2 páginas)** · Versión {{RESULTADO:version_commit}} · {{RESULTADO:fecha_corridas}}
*Nombre del repositorio: MotoTerminator. Para presentaciones externas se usa el nombre técnico MT-Bench.*

---

## 1. El problema

- Una parte importante de los accidentes graves de motocicleta ocurre en curvas. Por eso la industria desarrolla asistencias como el ABS en curva y el control de estabilidad (Bosch MSC, en serie desde la KTM 1190 Adventure de 2014) y asistencias por radar (Bosch ARAS, Ducati Multistrada V4).
- Para desarrollarlas, los fabricantes usan **motos sin piloto como instrumento de investigación**. BMW presentó su R 1200 GS autónoma como "banco de pruebas de equipo de seguridad". Honda (Riding Assist) y Yamaha (MOTOROiD/AMCES) exploraron el auto-equilibrio a baja velocidad.
- Validar estos controladores en pista es caro y lento. Las herramientas comerciales de simulación (dSPACE ASM Bike, IPG MotorcycleMaker) son de alta fidelidad, cerradas y costosas, y no están pensadas para **entrenar y comparar estadísticamente** muchos controladores candidatos.

## 2. Qué es MT-Bench

Es un simulador abierto y ligero (Python + numpy, corre en una laptop) de una moto robot **sin piloto**. Tiene:

- estabilizador activo modelado: giroscopio de control y lastre móvil;
- ABS y control de tracción;
- camino de dos carriles;
- **8 niveles de terreno procedural** (asfalto, tierra, grava, arena, lodo, rocas, escalones, saltos, nieve, hielo);
- **geometría de calles reales de OpenStreetMap**, en cualquier ciudad y con rutas A→B que respetan los sentidos.

Un controlador neuronal pequeño (783 parámetros) **aprende por evolución** con un plan de estudios de dificultad creciente. El mismo banco permite comparar ese controlador contra otros, por ejemplo un controlador clásico PD o uno aleatorio, **en exactamente las mismas condiciones**.

## 3. Qué lo hace serio: el protocolo de evaluación

| Práctica | Por qué le importa a una empresa |
|---|---|
| Pistas de prueba **reservadas**, nunca vistas en el entrenamiento | Mide generalización, no memoria |
| **Sin "rebobinado"**: el primer error cuenta como falla | Las tasas de éxito no se inflan |
| Intervalos de confianza exactos (Clopper-Pearson) y bootstrap con {{RESULTADO:n_semillas}} semillas | Toda cifra trae su incertidumbre y su tamaño de muestra |
| Requisitos formales (STL): carril, margen al borde, velocidad segura, reserva del estabilizador | Especificación auditable; señala dónde y cuándo se viola cada requisito |
| Curvas de fragilidad (ruido de sensores, latencia, masa, fricción) | Robustez medida, no supuesta |
| Verificación contra el benchmark de bicicleta de Meijaard et al. (2007) | Referencia académica estándar |

## 4. Resultados (corridas cortas reales)

| Indicador | Valor |
|---|---|
| Tasa de llegada limpia en pistas reservadas, nivel 1 (controlador evolutivo) | {{RESULTADO:tasa_limpia_nivel1_ga}} (IC 95 % {{RESULTADO:ic95_nivel1_ga}}) |
| Igual, con el controlador clásico PD | {{RESULTADO:tasa_limpia_nivel1_pd}} (IC 95 % {{RESULTADO:ic95_nivel1_pd}}) |
| Diferencia entre llegadas "con rebobinado" y llegadas limpias | {{RESULTADO:brecha_reintentos_nivel1}} |
| Fallas por km, nivel 1 | {{RESULTADO:fallas_km_nivel1_ga}} |
| Modo de falla dominante | {{RESULTADO:modo_falla_dominante}} |
| Nivel máximo alcanzado (mediana de las semillas) | {{RESULTADO:nivel_max_mediana}} |
| Costo de cómputo | {{RESULTADO:tiempo_generacion_s}} s por generación en {{RESULTADO:hardware}} |

## 5. Casos de uso B2B

1. **Búsqueda automática de escenarios críticos** (prioridad 1). El algoritmo evolutivo se invierte: evoluciona *pistas* que hacen fallar a un controlador dado. Clientes posibles: equipos de validación de proveedores Tier-1 y de fabricantes.
2. **Comparación de controladores** (PID/LQR, aprendidos, asistencias) con métricas e intervalos estandarizados.
3. **Estudios de estabilización a baja velocidad**: compromiso entre giroscopio, lastre y dirección, al estilo Riding Assist o AMCES.
4. **Docencia** en control, dinámica vehicular y aprendizaje evolutivo.

## 6. Límites declarados (lo que **no** afirmamos)

- No es "física realista". Es un **modelo de orden reducido**: plano longitudinal multicuerpo, más guiñada cinemática, más un modelo fenomenológico de inclinación.
- **La red no gobierna el equilibrio lateral.** Lo hacen leyes fijas del giroscopio y del lastre; la red sólo influye a través de la velocidad. Tampoco hay contradirección.
- Una frenada total puede voltear la moto aun con ABS. Es una limitación conocida y documentada.
- No hay transferencia demostrada a una moto real ni cumplimiento de ISO 26262, ISO 21448 o UL 4600.
- El modo ciudad es un circuito con geometría real, **sin tráfico, semáforos ni peatones**.
- Los resultados provienen de corridas cortas (niveles 1–3).

## 7. Hoja de ruta (TRL 2-3 → 4-5)

| Etapa | Contenido | TRL |
|---|---|---|
| Hoy | Banco reproducible, protocolo con IC, baselines | 2 → 3 |
| +3 meses | Módulo lateral físico Whipple/Sharp con lazo LQR (emerge la contradirección), elipse de fricción, frenado tipo MSC | 3 |
| +6 meses | Falsificación de escenarios y exportación tipo OpenSCENARIO; aceleración con numba | 3 → 4 |
| +12 meses | Identificación de parámetros con una moto real o un prototipo a escala | 4 → 5 |

## 8. Qué pedimos a un socio industrial

1. Parámetros geométricos e inerciales de una moto de referencia, o datos de una prueba de frenada y de giro estacionario.
2. Un ingeniero de contacto para un piloto de 3 meses centrado en el caso de uso 1.
3. Retroalimentación sobre el formato de exportación de escenarios.
