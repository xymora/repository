<!-- Guion del deck ejecutivo (12 diapositivas, ~15 min). El .pptx se genera en la Fase B
     (python-pptx 1.0.2 ya instalado). Cifras SOLO desde resultados/ ({{RESULTADO:...}}).
     Figuras: docs/figuras/*.png generadas por reporte.py. -->

# Deck MT-Bench: guion y notas del orador

**Formato:** 16:9 · fondo neutro claro (tema de "ingeniería", no post-apocalíptico) · una idea por diapositiva · máximo 3 viñetas · fuente de datos al pie de cada cifra.

---

## 1. Portada
- **Título:** MT-Bench: banco de pruebas virtual para controladores de motocicletas sin piloto
- **Subtítulo:** *Curriculum Neuroevolution for Riderless Two-Wheeler Control on Procedural and OpenStreetMap Roads*
- Autor · afiliación · {{RESULTADO:fecha_corridas}}
- **Visual:** captura de la vista lateral con el tema neutro (se toma en la Fase B).

**Notas del orador:** "Les voy a mostrar un banco de pruebas, no una moto autónoma. Su valor está en cómo mide, no en lo que promete."

---

## 2. El problema
- Una parte importante de las víctimas de moto se concentra en curvas (Bosch; citar la fuente exacta al pie).
- Las asistencias en curva y a baja velocidad necesitan validarse en miles de escenarios.
- La pista es cara y la simulación comercial es cerrada y costosa.

**Notas:** No usar cifras de mercado como un dato único: las consultoras discrepan unas 10 veces (USD 0.3–3 B en 2025). Si preguntan, dar el rango y la fuente.

---

## 3. Qué hace la industria

| Actor | Enfoque |
|---|---|
| BMW R 1200 GS autónoma | "Banco de pruebas de equipo de seguridad" |
| Honda Riding Assist | Equilibrio sin giroscopio a < 3 mph |
| Yamaha MOTOROiD / AMCES | Control del centro de masa |
| Bosch MSC / ARAS | ABS en curva / radar en serie |
| Lit Motors C-1 | Dos CMG |

**Notas:** "Los fabricantes usan la autonomía como instrumento para desarrollar asistencias. Ése es nuestro posicionamiento." Fuentes en `docs/related_work.md`.

---

## 4. La brecha
- **Alta fidelidad** (dSPACE ASM Bike, IPG MotorcycleMaker): MIL/SIL/HIL, cerrado.
- **Académico** (Meijaard 2007, Tianjic 2019): modelos y demostraciones aisladas.
- **Falta** un banco abierto y ligero que **entrene y compare controladores con estadística rigurosa**.

**Notas:** Somos complementarios a dSPACE e IPG, no competidores en fidelidad.

---

## 5. MT-Bench en una imagen
- **Diagrama:** Terreno procedural / OSM → Simulador vectorizado (N motos) → Controlador (red GA | PD | externo) → Métricas + STL → Reporte.
- Corre en una laptop; numpy es la única dependencia obligatoria.

**Notas:** Mencionar el gancho `controlador=`: cualquier controlador del cliente puede conectarse.

---

## 6. Demo (video de 60 s)
- Entrenamiento en terreno, luego graduación a calles reales.
- Ruta A→B en una ciudad con satélite. La imagen satelital es sólo visualización y no se redistribuye.

**Notas:** Decir en voz alta: "En la ciudad no hay tráfico ni semáforos: es un circuito con geometría real."

---

## 7. Cómo medimos (el diferenciador)
- Pistas reservadas, nunca vistas · sin rebobinado: el primer error es falla
- IC exactos y bootstrap con {{RESULTADO:n_semillas}} semillas
- Requisitos STL (carril, velocidad segura, reserva del estabilizador) y curvas de fragilidad

**Notas:** "Con 0 fallas en n episodios, la cota superior al 95 % es 1 − 0.05^(1/n). Para prometer menos de 1 % de fallas hacen falta 299 episodios limpios. El reporte imprime qué afirmación permite cada n."

---

## 8. Resultados
- **Figura:** `docs/figuras/tasa_limpia.png` (barras con IC por nivel y controlador)
- Nivel 1: evolutivo {{RESULTADO:tasa_limpia_nivel1_ga}} ({{RESULTADO:ic95_nivel1_ga}}) contra PD {{RESULTADO:tasa_limpia_nivel1_pd}} ({{RESULTADO:ic95_nivel1_pd}})
- Brecha entre llegadas con rebobinado y limpias: {{RESULTADO:brecha_reintentos_nivel1}}

**Notas:** Si el PD gana en algún nivel, decirlo. La credibilidad vale más que el resultado. Insistir en que son corridas cortas (niveles 1–3).

---

## 9. Dónde falla y por qué
- **Figuras:** `histograma_fallas.png` y `fragilidad.png`
- Modo de falla dominante: {{RESULTADO:modo_falla_dominante}}
- Umbral de fragilidad: {{RESULTADO:fragilidad_umbral_50}}

**Notas:** Aquí se enlaza con el caso de uso 1: "Si podemos encontrar estas fallas automáticamente para *su* controlador, eso es lo que ofrecemos."

---

## 10. Límites declarados
- Modelo de orden reducido: **la red no gobierna el equilibrio**, sin contradirección
- Una frenada total puede voltear la moto, aun con ABS
- Sin transferencia demostrada a una moto real ni cumplimiento de ISO 26262 o SOTIF

**Notas:** Mostrar esta diapositiva **antes** de que lo pregunten. Un ingeniero de dinámica lo detectará en 2 minutos.

---

## 11. Hoja de ruta TRL y colaboración
- TRL 2-3 (hoy) → 3: módulo lateral Whipple/Sharp + LQR → 3-4: falsificación de escenarios y exportación tipo OpenSCENARIO → 4-5: identificación con una moto real o a escala
- **Piloto de 3 meses:** búsqueda de escenarios críticos para un controlador del socio

**Notas:** Modelos posibles: piloto financiado, co-desarrollo o licencia. La propiedad intelectual defendible es el método de generación de escenarios, no el CMG ni el lastre (hay arte previo de Lit Motors y Yamaha).

---

## 12. La petición
1. Parámetros de una moto de referencia o datos de frenada y giro
2. Un ingeniero de contacto
3. Retroalimentación sobre el formato de escenarios

**Notas:** Cerrar con: "Todo número de esta presentación sale de un archivo reproducible con un comando." Nota legal: "Terminator" es marca de terceros; el nombre comercial se definirá antes de cualquier uso fuera del ámbito académico.
