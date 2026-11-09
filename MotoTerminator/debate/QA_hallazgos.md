# Hallazgos QA (circuito A→B→A / superficie irregular) — 2026-10-09

## H1 (para agente RUTAS) — giros agudos y vueltas en U YA existen en rutas de sólo ida
No es del circuito: el Dijkstra actual (ruta_entre / ruta) ya produce giros de 150°–180° en
<20 m (retornos de avenidas dobles: Av. Bernardo Reyes, Av. Félix Uresti Gómez en Monterrey;
bifurcaciones en "Y" agudas: Gómez Farías→Arizpe, Viaducto Nuevo Hidalgo en la zona 20.1217).
Con el suavizado actual (k=22 → ventana 22.5 m) eso da |kappa| ≈ 0.12–0.14 1/m, por encima del
límite del asfalto min(A_LAT_MAX, 0.85·μ·g)/V_DISENO² = 0.0886 1/m.
Medido: PistaCalle sólo ida al azar con |kappa| > límite: Monterrey 3/60, zona 20.1217 19/60.
Reproducción:
    import calles, numpy as np
    red = calles.RedVial(calles.Zona('Zona 20.1217, -98.7358', (20.121666666666666, -98.73583333333333)))
    n = sum(np.abs(calles.PistaCalle(red, s % 8 + 1, s).kappa).max() > 0.08864 for s in range(60))  # 19
Implicación: el contrato pide "curvatura en TODO el recorrido <= agarre del asfalto" para el
circuito; para cumplirlo ruta_circuito/circuito deben penalizar o prohibir giros > ~120–150°
en cualquier nodo (no sólo en B), p. ej. Dijkstra sobre aristas (estado = arista entrante)
con costo por ángulo de giro. Los defaults (sin circuito) deben quedar bit a bit, así que esto
sólo puede cambiar en el camino del circuito. tests/test_circuito.py lo verifica (sin U en
20 m sobre la polilínea y |kappa| <= límite en la PistaCalle).

## H2 (agente RUTAS) — "misma" a veces NO regresa por la misma ruta aunque la ida es de doble sentido
tests/test_circuito.py::test_misma_en_calles_de_doble_sentido. Zona 20.1217, A=(834.258, 181.208)
(20.129022, -98.737419), B=(721.789, 369.004) (20.127335, -98.738495); la ida (Calle 21 de Marzo,
8 de Mayo, Pedro María Anaya, 320 m) es toda de doble sentido. ruta_circuito(A, B, "misma") da un
regreso de 337 m del que 317 m son "rodea la manzana" y sólo repite el 6 % de la ida, pero
extra["vuelta"] dice "por la misma ruta en sentido contrario (6% del regreso)". El "rodeo" se
convierte en todo el regreso (es en la práctica "otra"). En Monterrey (#5, #10) cubre 92–100 %.
Reproducción:
    red = calles.RedVial(calles.Zona('Zona 20.1217, -98.7358', (20.121666666666666, -98.73583333333333)))
    pts, nom, ex = red.ruta_circuito((834.2581602976012, 181.2080387187101),
                                     (721.7892390121018, 369.0040196870114), "misma")
Sugerencia: el rodeo en B debe volver a B (o a la ida) y de ahí seguir la ida al revés; si eso
no es posible decirlo en extra["vuelta"] en vez de "por la misma ruta".

## H3 (agente SUPERFICIE) — "irregular" pasa de 5 cm entre muestras (0.1 m) en niveles 5–8
tests/test_superficies.py::test_irregular_continua_sin_obstaculos_y_con_agarre: saltos de
5.1–5.5 cm entre muestras consecutivas (pendiente local 51–55 %) en colinas+ondas, p. ej.
PistaCalle(red_mty, 5, 5, superficie="irregular") en x=46.1 m (sección 'colinas'/asfalto);
también en circuito (nivel 6). La pendiente media de 3 m sí respeta μ/2, pero la local no.
Arreglo sugerido: limitar también |diff(hs)| <= 0.045 (p. ej. reescalar `off` por la pendiente
máxima de muestra a muestra, además de la de 3 m), o bajar la amplitud de _ondas sobre colinas.
