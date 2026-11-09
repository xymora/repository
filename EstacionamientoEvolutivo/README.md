# Estacionamiento evolutivo

Simulador hecho **sólo con Python** (biblioteca estándar, sin instalar nada) en el
que un auto aprende solo a estacionarse **perfectamente** en un cajón: centrado,
recto, sin pisar las líneas y totalmente detenido. Su "inteligencia" evoluciona
con un **algoritmo genético**: cada vez que los autos de una generación fallan
(chocan, se quedan sin tiempo o terminan mal estacionados) se crea una nueva
generación a partir de los mejores, hasta que lo logran y, después, lo hacen con
**menos movimientos, en menos tiempo y con más precisión**.

## Ejecutar

Doble clic en **`Iniciar_Simulador.bat`**, o desde una terminal:

```bash
python main.py                  # entrenar viendo la animación
python main.py --modo reversa   # aprender a estacionarse en reversa (por defecto: frente)
python main.py --lugar asignado # el lugar se asigna (por defecto: lo busca con la cámara)
python main.py --cajon 3        # asignar el cajón 3 como lugar libre
python main.py --demo           # ver al mejor plan guardado estacionarse
python main.py --continuar      # seguir evolucionando desde el mejor guardado
python main.py --sin-gui 60     # entrenar 60 generaciones en consola (rápido)
python main.py --semilla 4      # resultados reproducibles
python main.py --poblacion 200  # cambiar el tamaño de la población
```

Requiere Python 3.8+ (tkinter viene incluido en el instalador de Windows).

**De frente o en reversa:** se elige con los botones **De frente / En
reversa** del panel derecho (o con `--modo`). Al cambiar, la evolución empieza
en la generación 1 para aprender la nueva forma. Cada modo guarda su propio
mejor plan, así que no se pierde lo aprendido en el otro. En el cajón, una
flecha indica hacia dónde debe quedar el **frente** del auto: hacia el fondo
(de frente) o hacia el pasillo (en reversa).

**Botones:** `Pausa`/`Continuar` · `Turbo`/`Animar` · `⟲ Reiniciar desde cero`
(pide confirmación, borra el plan guardado del modo actual y el historial, y
vuelve a la generación 1 con autos al azar).

**Teclas:** `Espacio` pausa · `+`/`-` velocidad · `T` turbo · `N` reiniciar ·
`Esc` salir.

En la ventana, el auto **amarillo** es el líder (el mejor de la generación
anterior): llantas delanteras que giran con el volante, calaveras que se
encienden al frenar y luces blancas en reversa. Los demás autos se ven como
siluetas con el parabrisas marcado, de color según su estado. Debajo del
estacionamiento están su **tablero** (velocímetro, volante, pedales y marcha),
la **cámara lateral** y su **plan de maniobras**, con la maniobra en curso
resaltada y su avance.

## El lugar libre: asignado o buscado con la cámara

En el panel, **Lugar** tiene dos opciones:

- **Buscar con cámara** (por defecto): en cada generación queda libre un cajón
  al azar. El auto entra al pasillo sin saber cuál es y lo busca con una cámara
  en el espejo izquierdo: un abanico de rayos que mide distancias. Un cajón se
  da por libre cuando varios rayos llegan hasta su fondo por la franja central,
  donde estaría un auto. Los rayos se ven en el lote y en la tarjeta *Cámara
  lateral*.
- **Asignado**: haz **clic en cualquier cajón** del lote (o en *Al azar*) para
  elegir el lugar. El auto ya sabe dónde está y va directo.

En los dos casos, el auto se detiene en el pasillo en una **pose de referencia**
respecto al cajón libre y desde ahí ejecuta su plan. Por eso el mismo plan sirve
para cualquier cajón. Cambiar el lugar no borra lo aprendido: sólo repite la
generación en el nuevo cajón.

## El auto se maneja como uno real

- **Acelerador y freno** por separado. El freno reduce la velocidad hasta
  detener el auto; nunca lo hace ir en reversa.
- **Volante gradual**: las llantas giran a velocidad limitada (60°/s), hasta 34°.
- **Palanca D/R**: sólo se puede cambiar de marcha con el auto detenido.
- **Gira como un coche**: modelo de bicicleta en el que el auto rota alrededor
  de su eje trasero (radio de giro mínimo: 3.85 m).

## Qué significa "estacionado perfecto"

| Criterio | Tolerancia |
|---|---|
| Dentro del cajón, sin pisar la pintura de las líneas | ≥ 8 cm libres |
| Centrado (de lado a lado) | ± 10 cm |
| Recto respecto al cajón | ± 2° |
| Orientación | La que se eligió: frente hacia el fondo (de frente) o hacia el pasillo (en reversa) |
| Detenido | < 0.02 m/s |

Las líneas se dibujan con su ancho real (12 cm), y el eje central del cajón
aparece punteado como referencia.

## Cómo aprende

**El genoma es un plan de maniobras.** Cada maniobra es un movimiento continuo:
marcha (D o R), distancia, velocidad de crucero y posición del volante al
inicio, a la mitad y al final del tramo. El genoma tiene espacio para 6
maniobras y la evolución decide cuántas usar (menos = mejor). Un **conductor**
ejecuta el plan con los pedales: acelera, frena de forma progresiva para
detenerse justo al final de cada maniobra y cambia de marcha estando detenido.

**La calificación (aptitud):**

- **Si se estaciona perfecto:** `3000 + 1000·(rapidez) + 300·(maniobras que le
  sobran de las 6 posibles) + 400·(precisión)`. Un fallo nunca llega a 3000, así
  que estacionarse siempre gana; entre los que lo logran, gana el que usa menos
  maniobras, tarda menos y queda más centrado.
- **Si falla:** se usa un **mapa de costo** que indica cuántos metros de manejo
  le faltan, desde cualquier posición *y orientación*, para llegar al cajón con
  las maniobras que un auto real puede hacer. Se calcula una sola vez con el
  algoritmo de Dijkstra (al estilo de Hybrid A*) y se guarda en
  `mapa_costo_frente.pkl` / `mapa_costo_reversa.pkl` (uno por modo, porque la
  orientación final es distinta). Así, llegar chueco a la boca del cajón califica mal aunque
  esté "cerca", porque desde ahí falta mucho para corregir. El auto **no**
  recibe este mapa: sólo sirve para calificarlo. Ya dentro del cajón, cada
  criterio de precisión que cumple suma puntos. Chocar resta 150 puntos más 60
  por cada m/s del impacto: un castigo moderado a propósito, porque si chocar
  costara demasiado la evolución nunca se animaría a probar maniobras nuevas
  (como meter reversa), que al principio casi siempre terminan en choque.

**El algoritmo genético:**

- **Elitismo:** los 3 mejores pasan intactos a la siguiente generación.
- **Ajuste fino (búsqueda local):** el 30% de cada generación son copias de los
  mejores con cambios diminutos en todos sus genes, para pasar de "casi" a
  "perfecto".
- **Selección por torneo y cruce por maniobras:** el hijo toma maniobras
  completas de cada padre.
- **Mutación adaptativa:** se reduce cuando hay mejoras y aumenta si la
  evolución se estanca.
- **Extinción:** si la población queda atrapada 10 generaciones en una mala
  estrategia sin lograr estacionarse, se renueva por completo. La gráfica lo
  marca con una línea naranja.

## Resultados medidos

Medido con la versión anterior, de cajón fijo: 12 corridas por modo con
semillas distintas (250 autos por generación), contando la generación del primer
estacionamiento perfecto:

| Modo | Lo lograron antes de la gen. 50 | Mediana |
|---|---|---|
| De frente | 11 de 12 | generación 13 |
| En reversa | 10 de 12 | generación 20 |

En reversa cuesta más porque el auto tiene que pasarse del cajón, detenerse,
meter R y entrar de espaldas. Al seguir evolucionando, el mejor auto suele
quedar a 1–2 cm del centro y a menos de 1° de inclinación.

## Archivos

| Archivo | Contenido |
|---|---|
| `main.py` | Punto de entrada y opciones de línea de comandos |
| `config.py` | Todos los parámetros (física, tolerancias, algoritmo genético) |
| `fisica.py` | Escenario, colisiones y física del auto |
| `plan.py` | El genoma: plan de maniobras |
| `simulacion.py` | Conductor, agente y cálculo de aptitud |
| `navegacion.py` | Mapa de costo (guía para calificar) |
| `evolucion.py` | Algoritmo genético, récords e historial |
| `camara.py` | Cámara lateral: rayos y reconocimiento del cajón libre |
| `interfaz.py` | Ventana, paneles y lógica de la interfaz (tkinter) |
| `escena.py` | Dibujo del lote, de los autos estacionados y de los autos en movimiento |
| `estilo.py` | Tema visual, pintor de imágenes con antialias, gráfica e indicadores |
| `plan_frente.json`, `plan_reversa.json` | El mejor plan de cada modo; lo usa `--demo` y sólo se reemplaza por uno mejor |
| `historial.csv` | Estadísticas de cada generación |
| `mapa_costo_frente.pkl`, `mapa_costo_reversa.pkl` | Mapas de costo precalculados (se regeneran solos si cambia el escenario) |
