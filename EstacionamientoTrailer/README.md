# Estacionamiento evolutivo de tractocamión

Simulador hecho **sólo con Python** (biblioteca estándar, sin instalar nada) en el
que un **tractocamión** aprende solo a estacionarse en un cajón de un patio de
maniobras, con **1 remolque** (caja de 13.6 m) o **2 remolques** (doble remolque
de 8.5 m). Su "inteligencia" evoluciona con un **algoritmo genético**: cada vez
que los camiones de una generación fallan (chocan, hacen tijera, se quedan sin
tiempo o terminan mal estacionados) se crea una nueva generación a partir de los
mejores, hasta que lo logran y, después, lo hacen con **menos movimientos, en
menos tiempo y con más precisión**.

## Ejecutar

Doble clic en **`Iniciar_Simulador.bat`**, o desde una terminal:

```bash
python main.py                    # entrenar viendo la animación
python main.py --remolques 2      # con doble remolque (por defecto: 1)
python main.py --modo frente      # estacionarse de frente (por defecto: reversa)
python main.py --tamano chico     # cajón chico, normal, grande o azar
python main.py --lugar asignado   # el lugar se asigna (por defecto: lo busca con la cámara)
python main.py --cajon 5          # asignar el cajón 5 como lugar libre
python main.py --demo             # ver al mejor plan guardado estacionarse
python main.py --continuar        # seguir evolucionando desde el mejor guardado
python main.py --sin-gui 100      # entrenar 100 generaciones en consola (rápido)
python main.py --semilla 4        # resultados reproducibles
```

Requiere Python 3.8+ (tkinter viene incluido en el instalador de Windows).

**Opciones en la ventana:**

- **Estacionarse: De frente / En reversa.** En reversa entran primero los
  remolques, como en un andén de carga; de frente entra primero el tractor.
- **Remolques: 1 rem. / 2 rem.**
- **Cajón: Chico (3.8 m) / Normal (4.4 m) / Grande (5.2 m) / Al azar.** La fila
  se llena con los cajones que quepan (20, 17 o 15). Con *Al azar* el tamaño
  cambia en cada generación.
- **Lugar: Asignado / Buscar con cámara.** Con cámara, en cada generación queda
  libre un cajón al azar. El camión recorre el pasillo y lo busca con una cámara
  en la cabina: un abanico de rayos que da el cajón por libre cuando varios
  llegan hasta su fondo por la franja central. Asignado: haz **clic en un
  cajón** del patio (o en *Al azar*) y el chofer va directo.

En todos los casos el camión se detiene recto en el pasillo, en una **pose de
referencia** respecto al cajón libre, y desde ahí ejecuta su plan. Así el mismo
plan sirve para cualquier cajón y tamaño. Cambiar el lugar o el tamaño no borra
lo aprendido. Los cajones de las orillas que no dejan espacio para esa pose
nunca quedan libres.

Al cambiar el modo o los remolques, la evolución empieza en la generación 1
para aprender esa combinación. Cada combinación guarda su propio mejor plan, así que no se pierde
lo aprendido en las demás. En el cajón, una flecha indica hacia dónde debe
quedar el **frente** (la cabina) del tractor.

**Botones:** `Pausa`/`Continuar` · `Turbo`/`Animar` · `⟲ Reiniciar desde cero`
(pide confirmación, borra el plan guardado de la combinación actual y el
historial, y vuelve a la generación 1).

**Teclas:** `Espacio` pausa · `+`/`-` velocidad · `T` turbo · `N` reiniciar ·
`Esc` salir.

En la ventana, el camión de **cabina amarilla** es el líder (el mejor de la
generación anterior). Su tractor tiene llantas delanteras que giran con el
volante y quinta rueda; sus remolques, techo acanalado y calaveras que se
encienden al frenar. Los demás se ven como contornos, de color según su estado.
Debajo del patio están su **tablero**, la **cámara de la cabina** y su **plan
de maniobras**. El tablero tiene velocímetro, volante, pedales, marcha y un
indicador del **ángulo de cada articulación**, que se pone rojo cerca de la
tijera.

## El camión se maneja como uno real

- **Acelerador y freno** por separado; el freno detiene sin mandar en reversa.
- **Volante gradual** (30°/s, hasta 40°) y **palanca D/R** que sólo cambia con
  el camión detenido.
- **Articulación real:** el tractor gira alrededor de su eje trasero y jala al
  remolque desde la quinta rueda; el segundo remolque va enganchado con lanza
  al primero. El eje de cada remolque sólo puede moverse hacia donde apunta, así
  que al avanzar en curva los remolques se cierran hacia adentro y **en reversa
  son inestables**: si no se corrige el volante, el ángulo crece solo.
- **Efecto tijera:** si el ángulo entre dos unidades pasa de 75°, el intento
  falla.
- **Asistente de reversa** (como el *trailer backup assist* de camiones y pickups
  modernos): como en reversa los remolques son inestables, en las maniobras en R
  el plan no indica la posición del volante sino **el ángulo que debe tener el
  remolque**, y el conductor corrige el volante continuamente para mantenerlo,
  igual que un chofer experimentado. Con 2 remolques el control es en cascada
  (para lograr el ángulo del segundo remolque busca un ángulo en el primero). En
  el tablero se ve qué ángulo está manteniendo. Se puede desactivar en
  `config.py` (`ASISTENTE_REVERSA = False`).

## Qué significa "estacionado perfecto"

Se exige a **todas** las unidades (tractor y cada remolque):

| Criterio | Tolerancia |
|---|---|
| Dentro del cajón, sin pisar la pintura de las líneas | ≥ 10 cm libres |
| Centrada (de lado a lado) | ± TOL_CENTRO (ver `config.py`) |
| Recta respecto al cajón y con la orientación elegida | ± TOL_ANGULO (ver `config.py`) |
| Camión detenido | < 0.02 m/s |

## Cómo aprende

**El genoma es un plan de maniobras.** Cada maniobra es un movimiento continuo:
marcha (D o R), distancia, velocidad de crucero y posición del volante al
inicio, a la mitad y al final del tramo. Hay espacio para 6 maniobras y la
evolución decide cuántas usar (menos = mejor). Un **conductor** ejecuta el plan
con los pedales: acelera, frena de forma progresiva para detenerse justo al
final de cada maniobra y cambia de marcha estando detenido.

**La calificación (aptitud):**

- **Si se estaciona perfecto:** `3000 + 1000·(rapidez) + 300·(maniobras que le
  sobran de las 6 posibles) + 400·(precisión)`. Un fallo nunca llega a 3000, así
  que estacionarse siempre gana.
- **Si falla:** un **mapa de costo** indica cuántos metros de manejo le faltan a
  la unidad que entra primero al cajón (el tractor de frente, el último remolque
  en reversa) desde cualquier posición *y orientación*. Se calcula una sola vez
  con el algoritmo de Dijkstra (al estilo de Hybrid A*) y se guarda en
  `mapa_costo_<modo>_<remolques>r.pkl`. El camión **no** recibe este mapa: sólo
  sirve para calificarlo. Además suma puntos la parte del camión que ya está
  dentro del cajón y, con todo dentro, cada criterio de precisión cumplido.
  Chocar o hacer tijera resta 150 puntos más 60 por cada m/s.

**El algoritmo genético:** elitismo (los 3 mejores pasan intactos), ajuste fino
(30% de cada generación son copias de los mejores con cambios diminutos),
selección por torneo, cruce por maniobras completas, mutación adaptativa y
**extinción** (si la población se atasca sin lograr estacionarse, se renueva).

## Archivos

| Archivo | Contenido |
|---|---|
| `main.py` | Punto de entrada y opciones de línea de comandos |
| `config.py` | Todos los parámetros (patio, camión, tolerancias, algoritmo genético) |
| `fisica.py` | Patio, colisiones y física del tractocamión articulado |
| `plan.py` | El genoma: plan de maniobras |
| `simulacion.py` | Conductor, agente y cálculo de aptitud |
| `navegacion.py` | Mapa de costo (guía para calificar) |
| `evolucion.py` | Algoritmo genético, récords e historial |
| `camara.py` | Cámara de la cabina: rayos y reconocimiento del cajón libre |
| `interfaz.py` | Ventana, paneles y lógica de la interfaz (tkinter) |
| `escena.py` | Dibujo del patio, de los remolques estacionados y de los camiones en movimiento |
| `estilo.py` | Tema visual, pintor de imágenes con antialias, gráfica e indicadores |
| `plan_<modo>_<remolques>r.json` | El mejor plan de cada combinación; se guarda solo al mejorar y lo usa `--demo` |
| `historial.csv` | Estadísticas de cada generación (se reinicia en cada entrenamiento) |
| `mapa_costo_<modo>_<remolques>r_<tamaño>.pkl` | Mapas de costo precalculados para el cajón de referencia de cada tamaño (se regeneran solos si cambia el patio) |
