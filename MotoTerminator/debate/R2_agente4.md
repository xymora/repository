# Ronda 2 · Agente 4 (seguridad, robustez, evaluación): réplica

## (a) Coincidencias del panel

Estos son los puntos en los que coincidimos varios agentes; tómenlos como consenso:

1. **El rebobinado no debe contar en las métricas.** Lo dicen el A2 (P5, "con/sin la regla de regreso solo en evaluación"), el A5 (P3 y el *overclaim* n.º 4) y yo (D2).
2. **Hace falta una suite reservada con semillas fijas y con IC**: A2 (D5, D10), A3 (Fase 5), A5 (P1) y yo (P1).
3. **La percepción es omnisciente y sin latencia**: A1 (D15), A5 (P7) y yo (D1).
4. **Los números aleatorios comunes (CRN) se quedan en el entrenamiento** (A1 D13, A2, A3 §4.3). Para *estimar* robustez se necesita ruido por moto, pero solo en evaluación.
5. **Pruebas antes de tocar nada**: A1 (P0) y A3 (Fase 0) con la regresión dorada, más mi P10.
6. **No exagerar lo que se afirma** (A5 §5). Lo suscribo completo.

## (b) Objeciones y defensa

**Frente al A2 (no tocar la aptitud del usuario).** Lo acepto: **la aptitud de entrenamiento queda intacta por defecto.** Mi objetivo nunca fue cambiar cómo aprende la moto, sino que **lo que se reporte no pueda inflarse**. Eso se logra sin tocarla:
- La evaluación usa `max_reintentos=0` como parámetro del `Simulador` y cuenta como éxito solo la *llegada limpia*.
- El `historial.csv` gana columnas nuevas sin quitar ninguna: `llegadas_limpias_%`, `reintentos_lider` y los componentes de la aptitud por separado (justo la P5 del A2). El lector actual ignora las columnas que no conoce.
- `APTITUD_ESTRICTA = False` queda en `config.py` como bandera opcional, para que el usuario decida y para la ablación.

Sí mantengo un matiz científico. El incentivo de "cambiar choques por rapidez" (un choque cuesta 20 puntos y la rapidez da hasta 150) sigue existiendo en el entrenamiento por defecto. Ya no lo trato como dogma sino como **hipótesis medible**: si la brecha entre "llegó" y "llegó limpio" crece con las generaciones, hay *reward hacking*; si no, el rebobinado es un andamio legítimo, como los *resets* en RL. En ambos casos se reporta. Sobre el criterio para subir de nivel (A2 P4, cota de Wilson): también cambia el currículo del usuario, así que lo dejaría detrás de una bandera y no por defecto.

**Frente al A1 (un frenazo voltea la moto con ABS, y el equilibrio no depende de la red).**
- El vuelco por frenazo (freno = 1 → 204°) es **exactamente un hallazgo SOTIF**: un escenario conocido-inseguro dentro del ODD. Propongo tres cosas:
  1. Fijarlo como **prueba de regresión** marcada como peligro conocido (`xfail` documentado).
  2. Agregar un requisito STL `G(|θ| < 0.5)` al monitor.
  3. Implementar la mitigación de levantamiento trasero (A1 P2) detrás de la bandera `MSC_ACTIVO`, **apagada por defecto**, porque altera la dinámica que aprendió la campeona actual.

  Al usuario le diría que un ABS moderno real sí incluye esta mitigación, de modo que encenderla por defecto sería coherente con su intención de "como moto real". Pero la decisión es suya.
- Que el equilibrio no dependa de la red **cambia lo que se puede afirmar, no necesariamente el código de hoy**. Arquitectónicamente, tenemos un estabilizador fijo de bajo nivel con un planificador aprendido de alto nivel. Esa jerarquía es estándar en la industria y, en términos Simplex, el lazo de equilibrio ya es el "controlador simple". Lo que no se puede decir es "la red aprendió a equilibrarse". El módulo Whipple/Sharp (A1 P4) es valioso, pero lleva días y obliga a reentrenar: no es para hoy. Si se hace, los monitores R6/R7 y la suite sirven sin cambios para comparar ambos modelos laterales.
- La no linealidad artificial (`AMPLIF_LENTA`) y el ruido sin escalar por √dt (A1 D14) los incorporo al reporte como **limitaciones declaradas**.

**Frente al A5 (renombrar y reposicionar).** Estoy de acuerdo con el reposicionamiento: *banco de escenarios adversos y comparación de controladores*. Mi falsificador (P6) es justo su producto U1, así que convergemos. Dos matices:
1. **No renombraría código ni archivos.** "MotoTerminator" se queda como nombre del proyecto y la GUI lleva un subtítulo técnico. Renombrar rompe el flujo del usuario y no aporta credibilidad.
2. **El vocabulario SOTIF/UL 4600 sí se usa, como metodología, no como cumplimiento.** El reporte dirá "estructura inspirada en UL 4600; sin afirmación de conformidad; TRL ≤ 3". Callarlo del todo le quita al proyecto su argumento más fuerte ante un equipo de validación.

**Frente al A3 (numba primero).** Discrepo en el orden *para hoy*. Numba son 3-4 días con riesgo de divergencia numérica, mientras que la evaluación rigurosa cabe en una sesión y no exige velocidad: 200 pistas × 5 réplicas por lote salen en minutos. Primero hay que medir bien y después medir rápido. Los nuevos parámetros del `Simulador` llevan valores por defecto idénticos a los actuales, así que la regresión dorada del A3 no cambia ni un bit.

## (c) TOP-8 para implementar HOY (una sesión, sin entrenamientos largos, defaults del usuario intactos)

| # | Qué | Archivo(s) | Est. |
|---|---|---|---|
| 1 | **Red de seguridad:** regresión dorada (4 pistas × 4 redes, exacta), determinismo, invariantes físicos y prueba del vuelco por frenazo (`xfail`, peligro conocido) | `tests/test_regresion.py`, `tests/test_fisica.py` | 1.5 h |
| 2 | **Parámetros del simulador sin cambiar el comportamiento:** `max_reintentos=None` (usa config), `ruido_por_moto=False`, `registrar=False` (trazas para STL) | `fisica.py` | 45 min |
| 3 | **Métricas limpias en el entrenamiento sin tocar la aptitud:** `llegadas_limpias_%`, `reintentos_lider` y componentes desagregados (columnas nuevas compatibles hacia atrás) | `evolucion.py`, `fisica.py:aptitud` (solo expone partes) | 1 h |
| 4 | **Suite reservada:** semillas ≥ 2³¹, M pistas × K ruidos, sin rebobinado; IC de Clopper-Pearson y Poisson (fallas/km), taxonomía por motivo/rasgo/material, TLC mínimo; `main.py --evaluar` (prueba rápida de humo 30×3; las corridas grandes las lanza el usuario) | `evaluacion.py`, `main.py` | 2.5 h |
| 5 | **Monitores STL R1-R9** (R9 = cabeceo) con robustez ρ y lugar y momento de cada violación | `stl.py` | 1.5 h |
| 6 | **Perturbaciones solo en evaluación:** ruido y sesgo de sensores, latencia de 0-3 pasos, μ percibido ≠ μ real, más un barrido de fragilidad con IC. La bandera `SENSORES="ideal"` queda por defecto en el entrenamiento | `sensores.py`, `evaluacion.py` | 2 h |
| 7 | **Reporte de seguridad automático:** ODD declarado, requisitos, métricas con IC, fragilidad, limitaciones (A1 D1-D15) y lista de "no afirmar" (A5), con hash de config y pesos | `reporte_seguridad.py` → `reportes/*.md` + PNG | 1.5 h |
| 8 | **Banderas opcionales apagadas:** `APTITUD_ESTRICTA` y `MSC_ACTIVO` (mitigación de levantamiento trasero, A1 P2), documentadas para que el usuario decida | `config.py`, `fisica.py:275-286` | 1 h |

**Total ≈ 11.75 h.** Si la sesión se acorta, el núcleo irrenunciable son los puntos 1 a 4 más el 7. La falsificación adversarial (P6), el escudo Simplex/CBF (P7), multiprocesamiento, numba y Whipple quedan para la siguiente sesión, ya montados sobre esta base de medición.
