# Contrato: circuito A→B→A y superficie irregular (2026-10-09)

Reglas para TODOS: no tocar mejor_moto*.json, poblacion*.npz, historial*.csv, sesion.json del
usuario (usar copias / dir_datos en el scratchpad). Con los defaults (pavimento, sin circuito)
todo debe ser BIT A BIT igual que ahora (respaldo en ..\MotoTerminator_respaldo_v11_2026-10-09).
Sin entrenamientos largos, sin capturas de pantalla, sin documentos: solo código + tests.

## config.py (lo agrega el agente GUI/integración)
CALLES_CIRCUITO = "no"        # "no" (sólo ida, como siempre) | "misma" | "otra"
CALLES_SUPERFICIE = "pavimento" | "irregular" | "variado"

## calles.py (dueño: agente RUTAS)
RedVial.ruta_circuito(a_xy, b_xy, vuelta="otra") -> (pts, nombres, extra)
    A→B y luego B→A. "misma": regresa por las mismas calles en sentido contrario (si alguna es
    de sentido único, usa la alternativa más parecida y lo dice en extra). "otra": regreso que
    evita en lo posible las calles de la ida. SIN vueltas en U de 180° (ni en B ni en ningún
    nodo): en B debe rodear una manzana. extra = {"x_b": metros hasta B, "vuelta": texto real,
    "largo_ida": m, "largo_vuelta": m}. Lanza RuntimeError con mensaje claro si no se puede.
RedVial.circuito(rng, largo_min, largo_max, vuelta) -> (pts, nombres, extra)   circuito al azar
    (largo TOTAL entre largo_min y largo_max) para entrenar.
PistaCalle(red, nivel, semilla, ruta=None, superficie=None, circuito=None)
    ruta puede ser (pts, nombres) o (pts, nombres, extra). circuito None -> C.CALLES_CIRCUITO.
    Si ruta es None y circuito != "no" -> circuito al azar de largo largo_ruta(nivel).
    Atributos nuevos: .circuito ("no"/"misma"/"otra"), .x_b (float o None), .extra (dict o None).
    La meta queda de vuelta en A. Curvatura en todo el recorrido <= agarre del asfalto a V_DISENO.

## superficies.py (dueño: agente SUPERFICIE)
SUPERFICIES = {"pavimento": ..., "irregular": ..., "variado": ...} (en ese orden)
generar(pista, rng, nivel, nombres, idx, tipo) para "irregular" y "variado".
"irregular" = relieve como en terrenos (colinas, colinas suaves, baches, pendientes,
ondulaciones) según el nivel, SIN obstáculos sueltos (rocas, troncos, escalones, zanjas,
rampas) y con materiales de calle (asfalto; tierra/grava en niveles altos si hay agarre).
"variado" no cambia (bit a bit).

## planificador.py, interfaz.py, main.py, evolucion.py, config.py (dueño: agente GUI/INTEGRACIÓN)
- Planificador A→B: opción "Circuito: regresar a A" con "por la misma ruta / por otra ruta".
- Ventana ⌖ Zona: 3 superficies y "Rutas de entrenamiento: sólo ida / circuito misma / circuito otra".
- Sesión (calles.guardar_sesion/cargar_sesion) guarda también circuito; el agente GUI puede
  editar SÓLO esas dos funciones de calles.py (coordinar: el agente RUTAS no las toca).
- main.py: --circuito {no,misma,otra}, --superficie {pavimento,irregular,variado}.
- evolucion.py: checkpoint por superficie (…_ciudad, …_ciudad_irregular, …_ciudad_variado);
  el circuito NO separa checkpoint. Pasa circuito/superficie a PistaCalle.
- Mapa: marcar A y B y que se distinga ida y vuelta.

## tests/ (dueño: agente QA)
tests/test_circuito.py, tests/test_superficies.py: contrato, defaults bit a bit, sin vueltas en U
(|kappa| <= límite en todo el circuito), x_b correcto, factibilidad (la campeona de terrenos
recorre irregular y variado; la de calles recorre circuitos pavimentados), GUI headless.
