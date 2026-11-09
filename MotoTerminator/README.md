# Moto autónoma evolutiva (estilo Moto-Terminator)

Simulador en Python donde una moto robot **sin piloto** aprende sola a andar por
cualquier tipo de camino: asfalto, tierra, pasto, grava, arena, lodo, rocas,
troncos, escalones, zanjas, rampas con salto, pendientes fuertes, nieve y hielo.
No dispara nada: su único objetivo es **llegar a la meta sin voltearse, sin caerse
y sin salirse del camino**.

Su "cerebro" es una **red neuronal** y aprende por **generaciones** con un
**algoritmo genético** (neuroevolución): en cada generación compiten 80 motos y
las mejores se cruzan y mutan para crear la siguiente.

## Ejecutar

Doble clic en **`Iniciar_Simulador.bat`**, o desde una terminal:

```bash
python main.py                  # entrenar viendo la animación (continúa lo guardado)
python main.py --nuevo          # empezar la evolución desde cero
python main.py --demo           # ver a la mejor moto en pistas nuevas
python main.py --demo --nivel 6 # ...en pistas de un nivel en particular
python main.py --sin-gui 150    # entrenar 150 generaciones en consola (más rápido)
python main.py --poblacion 120  # cambiar el tamaño de la población
python main.py --semilla 4      # resultados reproducibles
python main.py --ciudad "Monterrey · Centro"                            # calles reales
python main.py --desde "25.676, -100.315" --hasta "25.670, -100.300"     # ruta A → B
```

Requiere Python 3.8+ y **numpy**; para la imagen satelital de las calles reales,
**Pillow** (el `.bat` instala ambos si faltan). La ventana usa
tkinter, que ya viene con Python en Windows.

**Barra superior:** selector de modo `▲ Terrenos | ◈ Calles reales` ·
`⚑ Ruta A → B` (planificador) y `✕` (quitar la ruta) · `⌖ Zona` (otra ciudad) ·
`▶ Ver demo` / `◆ Entrenar` · `⚡ Turbo` · `❚❚ Pausa` · `− x1 +` (velocidad de la
animación) · `⟲ Desde cero` (pide confirmación y borra lo aprendido del modo actual).
**Barra de estado** (abajo): los avisos con su hora, cuadros por segundo y la atribución
de los mapas.

**El entrenamiento se ve completo:** se animan **todas** las pistas de cada generación
(la ventana avisa «Generación 12: pista 2 de 3» y, al terminar, el resumen de la
generación). Sólo se entrena sin animación si se pulsa **⚡ Turbo** (y se vuelve a la
animación pulsándolo otra vez).

**Distribución:** la vista lateral es baja (se ve el camino por delante y poco piso) y
el mapa y las vistas desde atrás / desde arriba tienen más espacio.

**Ventana maximizable:** usa el botón de maximizar de Windows (o `F11` para pantalla
completa; `Esc` la quita): la vista lateral, el mapa, la vista de equilibrio y la gráfica
crecen con la ventana. Sobre el mapa, la **rueda del mouse** acerca o aleja.

**Teclas:** `Espacio` pausa · `+`/`-` velocidad · `T` turbo · `D` demo · `C` calles reales ·
`←`/`→` nivel de la pista en la demo · `N` reiniciar · `Esc` salir.

## Plan de estudios: primero terrenos, luego calles

Al entrenar desde cero, la moto **empieza en los terrenos** y sube por sus 8 niveles.
Cuando **domina el nivel 8** (la líder termina todas las pistas 2 generaciones seguidas)
se **gradúa** y **pasa sola a calles reales** (Monterrey por defecto; funciona sin
internet), empezando en el nivel 1 de ciudad **con lo aprendido en terrenos**. Esto
funciona igual con la ventana y en consola (`--sin-gui`). Si ya hay un entrenamiento
de calles guardado no lo pisa: sólo avisa de la graduación. Se configura en `config.py`
(`PASAR_A_CALLES`, `ZONA_CALLES`) y siempre se puede cambiar de modo a mano.

## Calles reales (botón ◈ Calles reales)

Además de los terrenos inventados, la moto puede aprender a **recorrer calles
reales de una ciudad**, igual que el proyecto del dron: Monterrey, CDMX (Roma–Condesa
y Polanco), Guadalajara, Puebla, Querétaro, Mérida, Madrid… o **cualquier lugar**
escribiendo `lat, lon` o pegando un enlace de Google Maps.

- En cada prueba se elige una **ruta al azar entre dos esquinas** y se recorre por
  el camino más corto **respetando el sentido de las calles** (las de un solo
  sentido sólo se recorren a favor). Las esquinas se redondean con un radio de giro
  realista de ~6-8 m.
- Se supone que **todo el camino es asfalto liso y plano** (sin baches ni piedras):
  el reto es frenar antes de cada esquina para no derrapar ni salirse del carril, y
  no ir tan lento que se caiga.
- El mapa de abajo muestra la **imagen satelital real** (norte arriba) con la ruta
  (dorado lo que falta, verde lo recorrido) y todas las motos; *Abrir en Google
  Maps ↗* abre en el navegador la ubicación de la moto líder. En la vista lateral
  los carteles muestran el nombre de cada calle.
- **Niveles:** las rutas crecen de ~250 m (nivel 1) a ~950 m (nivel 8).
- El entrenamiento en calles se guarda **aparte** (`mejor_moto_ciudad.json`,
  `poblacion_ciudad.npz`, `historial_ciudad.csv`) y la primera vez **parte de lo
  aprendido en los terrenos**. En pruebas, así subió del nivel 1 al 8 en ~30
  generaciones. *⌖ Cambiar zona* lleva la misma moto a otra ciudad.
- **Datos:** calles de OpenStreetMap e imagen satelital de Esri (gratuitas, con
  atribución en el mapa). Se descargan una sola vez a `datos/`; si el proyecto del
  dron ya descargó esa ciudad, se reutilizan sus archivos sin descargar nada. Si los
  servidores de OpenStreetMap están saturados, la ventana avisa y se puede intentar
  más tarde (las ciudades que ya tiene el dron funcionan sin internet).

### Ruta A → B (botón ⚑ Ruta A → B)

Para que la moto siga **la ruta que tú le digas**:

1. Elige la ciudad de la lista y pulsa *Cargar mapa*, o escribe las coordenadas del
   centro de **cualquier ciudad** (o pega un enlace de Google Maps).
2. Marca la **salida (A)** y la **llegada (B)** haciendo clic en el mapa satelital
   (rueda del mouse: zoom · arrastrar: mover · clic derecho: borrar), o escríbelas
   como `lat, lon` / pega enlaces de Google Maps y pulsa *Trazar con estas
   coordenadas*. Si A y B quedan fuera de las ciudades descargadas, se arma y
   descarga una zona a la medida alrededor de ellos (de 2 a 8 km por lado).
3. Se calcula al instante el camino más corto **respetando los sentidos** de las
   calles: distancia, número de calles, por dónde sale y por dónde llega.
   *Comparar en Google Maps ↗* abre la misma ruta en Google Maps.
4. *✔ Usar esta ruta*: desde ese momento la **pista 1 de cada generación es tu ruta**
   (las otras dos siguen siendo al azar en la misma ciudad, para que la moto no sólo
   la memorice) y la **demo** recorre tu ruta una y otra vez. En el mapa aparecen los
   alfileres A y B y el panel muestra «TU RUTA A → B». `✕` vuelve a rutas al azar.

El planificador abre **maximizado** para ver el mapa lo más grande posible.

**Formatos de coordenadas aceptados** (en el planificador, en «Cambiar zona» y en
`--desde/--hasta`):

| Ejemplo | Formato |
|---|---|
| `Latitud: 20° 07′ 18″ N, 98° 44′ 09″ O` | grados, minutos y segundos con N/S/E/O/W |
| `N 20° 07′ 18″, O 98° 44′ 09″` | hemisferio antes del número |
| `20°07'18"N 98°44'09"W` | con apóstrofes y comillas normales |
| `20 07 18 N 98 44 09 O` · `20 07 18 norte 98 44 09 oeste` | sólo espacios / palabras |
| `20° 7.3′ N, 98° 44.15′ O` | grados y minutos decimales |
| `98° 44′ 09″ O, 20° 07′ 18″ N` | longitud primero (se acomoda sola) |
| `20.121667, -98.735833` · `Lat 20.1217 Lon -98.7358` | decimales |
| `https://www.google.com/maps/@20.1216,-98.7358,17z` | enlace de Google Maps |

Si las coordenadas caen en una zona que el proyecto del dron ya descargó (por ejemplo
Pachuca), se reutiliza sin internet.

Si un punto queda a más de 120 m de una calle (dentro de un parque, por ejemplo) o no
hay forma de llegar respetando los sentidos, el planificador lo avisa.

Desde la terminal: `python main.py --ciudad "Monterrey · Centro"` (o
`--ciudad "19.4326, -99.1332"`), también con `--demo` o `--sin-gui 50`.

## Qué se ve en la ventana

- **Vista lateral:** escenario post-apocalíptico (atardecer polvoso y ciudad en
  ruinas con parallax) y el terreno con texturas según el material: pasto, piedras,
  charcos de lodo, nieve, brillo del hielo, etc. La moto **líder** se dibuja
  completa (llantas de tacos que giran, horquilla, amortiguador, escape con
  flama al acelerar, luz de freno y el "ojo" rojo), con sus **rayos lidar**
  midiendo el terreno por delante y polvo que levanta la llanta trasera. El resto
  de la población se ve como siluetas tenues.
- **Indicadores sobre la vista:** generación y nivel, **velocímetro**, carteles con
  el tipo de tramo y una **barra de progreso** de la pista con los colores de cada
  material, la posición de la líder (▼) y la del resto de las motos.
- **Mapa desde arriba:** el camino real con sus curvas; cada punto es una moto y
  el triángulo amarillo es la líder.
- **Equilibrio de la líder:**
  - *Desde atrás:* la moto inclinándose a los lados, con el ángulo de inclinación
    en grados (verde → amarillo → rojo conforme se acerca a 46°, donde se cae), el
    bamboleo que le provoca el terreno y un aviso cuando va en el aire.
  - *Desde arriba, de cerca:* su posición dentro del carril de 4 m, hacia dónde
    apunta respecto al camino y el ángulo del manubrio (la llanta delantera gira).
- **Panel derecho:** resumen (generación, nivel, motos en carrera, llegadas),
  materiales y terrenos del nivel, **telemetría** (acelerador, freno, cabeceo,
  dirección y derrape que decide la red en ese instante) y la **gráfica** de
  aptitud (tendencia del mejor y promedio; las líneas punteadas marcan cada
  subida de nivel). En la demo, la lista de los últimos intentos.

La ventana se ajusta sola si la pantalla es chica.

## Cómo aprende

1. **Población:** 80 motos, cada una con una red neuronal distinta (35 entradas →
   20 neuronas ocultas → 3 salidas, 783 pesos que son su "ADN").
2. **Prueba:** cada generación recorre **3 caminos nuevos generados al azar**, para
   que aprenda a manejar en general y no memorice un camino.
3. **Aptitud:** porcentaje del camino recorrido + **premio por llegar (50) + premio por
   rapidez** proporcional a la velocidad media (100 puntos a 54 km/h, hasta 150): ir al
   doble de rápido vale el doble, así que la evolución busca **el menor tiempo**. Se
   restan **20 puntos** por cada error (volcarse, caerse de lado, chocar el chasís,
   salirse del camino), 8 puntos por cada metro promedio lejos del **centro de su
   carril** (en las curvas cuenta hasta 4 veces más), hasta 30 puntos por **invadir el
   otro carril** (según el tiempo que pase ahí) y 1 punto por cada grado promedio de
   **inclinación innecesaria**. Así gana la moto rápida, segura y en su carril.
4. **Selección y reproducción:** las 4 mejores pasan intactas (élite). La campeona
   de cada generación corre las **mismas pistas** que las nuevas, así que la mejor
   de una generación **nunca es peor** que la anterior en esas pistas (la consola y
   la ventana muestran «+X sobre la campeona anterior» y la velocidad media de la
   líder); el resto
   nace de cruzar padres elegidos por torneo, con mutaciones gaussianas en sus
   pesos. Un 4 % son motos nuevas al azar para no perder diversidad. Si la
   evolución se estanca, la mutación crece sola.
5. **Currículo por niveles:** cuando la líder termina todos los caminos 2
   generaciones seguidas, se sube de nivel y aparecen terrenos nuevos:

| Nivel | Se agrega |
|---|---|
| 1 | plano y colinas suaves sobre asfalto, tierra y pasto (camino recto) |
| 2 | baches, colinas grandes, grava; empiezan las curvas |
| 3 | rocas, troncos, arena, lodo |
| 4 | escalones y zanjas |
| 5 | rampas con salto, pendientes fuertes, nieve |
| 6 | hielo |
| 7–8 | todo más alto, más empinado y con curvas más cerradas |

En pruebas, la población pasó del nivel 1 al 6 en unas 70 generaciones
(unos 10 minutos en modo `--sin-gui`).

## Lo que "siente" y controla la moto

**Sensores (entradas de la red):** velocidad, cabeceo y su velocidad de giro,
inclinación lateral, derrape, ángulo del manubrio, posición y orientación dentro
del camino, contacto de cada rueda con el suelo, patinaje de cada rueda,
compresión de cada suspensión, **lidar** (altura del terreno a 1, 2, 3.5, 5.5, 8 y
12 m por delante), **cámara de terreno** (agarre del suelo bajo la moto y 5 m
adelante, si es blando como arena o lodo), y además:

- **Curvas que vienen a distancias que crecen con la velocidad** (lo que recorrerá en
  ~0.6 s, 1.5 s y 3 s), para frenar a tiempo antes de una esquina.
- **Margen contra la velocidad segura** de la curva más cerrada de los próximos 25 m,
  calculada con el agarre más bajo de ese tramo (en hielo o lodo es mucho menor).
- **Margen sobre los 30 km/h** (más lento la moto se vuelve inestable).
- **Capacidad gastada del giroscopio** (si se agota, ya no la puede sostener).
- **Velocidad lateral** hacia la orilla del carril y **qué tan rápido se está ladeando**.
- **Desvío respecto al centro de su carril**, **dónde estará en 0.8 s** si sigue igual y
  **cuánto manubrio pide la curva que viene** a su velocidad (la referencia para girar
  sin abrirse ni cortar la curva).

**Salidas:** acelerador/freno, cabeceo (un giroscopio interno inclina la moto
adelante o atrás, por ejemplo para no voltearse en una subida o para aterrizar un
salto) y dirección.

## La física

- **Vista lateral (2D):** chasís rígido de 230 kg + dos ruedas de 0.38 m unidas por
  suspensiones de resorte y amortiguador con tope. Contacto rueda-suelo con fuerza
  normal, fricción según el material (asfalto μ=1.0 … hielo μ=0.12), patinaje y
  resistencia a rodar (la arena y el lodo frenan mucho). Motor de 45 kW en la rueda
  trasera y frenos en ambas; sus reacciones levantan o hunden la nariz (caballitos
  reales). Arrastre del aire.
- **Vista superior:** el camino tiene curvas y 4 m de ancho. Al girar, la
  aceleración lateral no puede superar el agarre del suelo: en lodo, nieve o hielo
  la moto derrapa y, si insiste, se cae.
- **Equilibrio (inclinarse sólo cuando hace falta):**
  - En una curva la moto **debe** inclinarse: la inclinación necesaria es
    atan(v²·curvatura / g). Pero no es instantánea: la moto se ladea hacia ella con
    **inercia** (dinámica amortiguada), como una moto real, en lugar de saltar de lado a
    lado cada vez que la red mueve el manubrio.
  - El manubrio filtra los cambios bruscos de la red (0.15 s) y **a más velocidad gira
    menos**: nunca pide más de ~0.7 g de giro (≈35° de inclinación). En esquinas cerradas
    la moto tiene que frenar antes.
  - **Tiene que ir a 30 km/h o más.** La gravedad siempre tiende a tirarla (péndulo
    invertido); el estabilizador (efecto giroscópico de las ruedas + giroscopio interno,
    como en la película) sólo trabaja al 100 % **desde 30 km/h**. Más lento se debilita:
    cada golpe del terreno la sacude más y la dirección "serpentea", así que **entre más
    lenta, más fácil se cae o se sale del carril**; por debajo de **~20 km/h** se cae sí o
    sí. Con un piloto automático simple a velocidad fija: a 15 km/h se cae siempre, a
    20 km/h casi siempre, a 25 km/h con frecuencia en terreno rugoso, y desde 30 km/h se
    mantiene. La moto arranca lanzada a ~32 km/h.
  - **Todas las pistas se pueden recorrer arriba de 30 km/h:** ninguna curva es más
    cerrada de lo que el suelo permite a ~34 km/h (en hielo o lodo las curvas son más
    abiertas) y las esquinas de calle tienen ~14 m de radio (sólo algunas vueltas casi
    en U bajan a ~28 km/h).
  - El terreno rugoso (rocas, grava) la sacude más cuanto más rápido va.
  - **Premio a manejar suave:** la aptitud resta 1 punto por cada grado promedio de
    inclinación **innecesaria** (la que se aparta de la que pide la curva). Inclinarse
    en las curvas no se castiga; bambolearse en las rectas, sí.
- **Dos carriles:** el camino tiene una línea central; la moto circula por **su carril,
  el derecho**, y al girar debe hacerlo **sin cambiar de carril** (ni abrirse en la
  curva ni cortarla). La vista «desde arriba» marca su carril en verde y avisa
  «INVADE EL OTRO CARRIL».
- **Lastre activo (un "piloto" que es parte del sistema):** 60 kg montados donde iría
  el piloto. El sistema de la moto los desplaza automáticamente de lado a lado, como un
  piloto carga su peso, para contrarrestar el bamboleo y los golpes del terreno. Tiene
  un límite de fuerza: ayuda, pero lenta la moto sigue siendo inestable (se cae sí o
  sí bajo ~18 km/h). La vista «desde atrás» muestra hacia dónde empuja. La moto pesa
  326 kg en total.
- **Giroscopio de control (CMG):** como la Lit Motors C-1 o la Honda Riding Assist, un
  volante pesado gira a alta velocidad dentro de la moto; al inclinar su eje produce un
  par muy fuerte contra la caída. Absorbe al instante baches, rocas y sacudidas y deja
  que la moto **se incline y se enderece rápido**, así que puede hacer **giros rápidos y
  cerrados** (hasta ~0.8 g, casi el límite de agarre del asfalto). Dos límites reales:
  - el volante lo impulsa la transmisión, así que **su fuerza crece con la velocidad**:
    rápida está a tope y lenta casi no ayuda (lenta la moto sigue cayendo);
  - **se satura** si la exigencia es sostenida y se recupera cuando las exigencias van y
    vienen. La vista «desde atrás» muestra la capacidad que le queda y la red neuronal
    también la recibe como sensor.

  Con un piloto automático simple: de 0 a 15 km/h se cae en 2-5 s; desde 25 km/h aguanta
  incluso en rocas; y en rutas reales de Monterrey completó 8 de 8 sin errores y sin
  invadir el otro carril a **70 km/h de promedio** (antes 43 km/h).
- **Llantas con agarre realista:** el agarre llega al máximo con ~15 % de deslizamiento y
  **cae** si la llanta se bloquea al frenar o patina al acelerar (~30 % menos), y una
  llanta bloqueada casi no sostiene de lado: frenar a fondo en curva sobre lodo sin ABS
  tira la moto. Frenos de moto deportiva (pueden bloquear la llanta).
- **Ayudas electrónicas automáticas** (parte de la moto, no de la red neuronal; la
  telemetría tiene luces **ABS** y **TCS** que se encienden cuando actúan):
  - **ABS:** afloja el freno de la llanta que está por bloquearse, rueda por rueda.
  - **Control de tracción (TCS):** baja la potencia si la trasera patina.
  - **Amortiguador de dirección:** frena las sacudidas del manubrio en rocas y troncos.

  Sólo actúan con la rueda apoyada (en el aire la rueda gira libre y no es patinar).
  Comparación con y sin cada ayuda:

  | Prueba | Sin | Con |
  |---|---|---|
  | Frenar a fondo en curva, 60→30 km/h, **lodo** | se cae 6/6 | 0/6, frena en 34 m |
  | Frenar a fondo, 45→30 km/h, **hielo** | 47 m | **44 m** |
  | Frenar a fondo en curva, 60→30 km/h, asfalto seco | 12.9 m | 13.6 m (igual que en motos reales) |
  | Acelerar a fondo 5 s desde 32 km/h en **lodo** | 51 m | **58 m** |
  | 40 km/h en rocas y grava: bamboleo | 0.85° | **0.75°** |

- **Errores y reintento:** si la moto se cae de lado, se sale del carril, se voltea o
  choca el chasís, **no termina**: regresa al punto donde iba **2 segundos antes del
  error** y sigue desde ahí. El reloj no se detiene (pierde ese tiempo) y cada error
  resta 20 puntos. Con más de 3 errores en la misma pista, su intento termina. La
  ventana avisa cada error de la moto líder ("Error: se salió del camino a los 230 m →
  regresa 28 m…") y la telemetría muestra cuántos lleva.
- **Fin del intento:** llegó a la meta, más de 3 errores, se atascó 4 s sin avanzar o se
  acabó el tiempo.

## Archivos

| Archivo | Contenido |
|---|---|
| `main.py` | punto de entrada y opciones de línea de comandos |
| `config.py` | todos los parámetros (física, red, algoritmo genético) |
| `terreno.py` | generador procedural de caminos, materiales y niveles |
| `fisica.py` | simulación vectorizada de toda la población a la vez |
| `red.py` | red neuronal evaluada en lote |
| `evolucion.py` | algoritmo genético, currículo, guardado |
| `interfaz.py` | ventana tkinter: vistas, indicadores y panel |
| `graficos.py` | dibujo del cielo, la ciudad, el terreno y la moto |
| `calles.py` | calles reales: OpenStreetMap, imagen satelital, red vial, rutas A → B y Google Maps |
| `planificador.py` | ventana para elegir ciudad y marcar la ruta A → B sobre el mapa satelital |
| `mejor_moto.json` | la mejor moto (se genera al entrenar) |
| `poblacion.npz` | la población completa, para continuar el entrenamiento |
| `historial.csv` | aptitud por generación |
