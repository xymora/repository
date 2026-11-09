# Domo de Defensa Móvil

Juego de defensa antiaérea donde una o varias **baterías móviles** protegen áreas
habitadas de cohetes, morteros y drones, y una **IA aprende a decidir a qué amenaza
disparar**. Es un juego: usa física y valores de juego, no parámetros de sistemas reales.

La IA es una **red neuronal** que puntúa cada amenaza y aprende por **generaciones** con
una **estrategia evolutiva** (con Adam), además de clases automáticas de un instructor
y de imitar tus partidas.

## Ejecutar

Doble clic en **`Iniciar_Simulador.bat`** (instala numpy, pygame e imageio-ffmpeg si
faltan). Para entrenar sin gráficos: **`Entrenar_Rapido.bat`**. Desde una terminal:

```bash
python main.py                         # abre en la pestaña Entrenar IA
python main.py --modo campeon          # ver al campeón (entrenar | campeon | jugar | comandante)
python main.py --modo jugar
python main.py --sin-entrenar          # abrir sin iniciar el entrenamiento
python main.py --rapido                # entrenar en la consola (Ctrl+C detiene)
python main.py --rapido-gui            # entrenar en una ventana pequeña con gráfica
python main.py --rapido --minutos 30   # o --generaciones 200
python main.py --datos C:\otra\carpeta # usar otra carpeta de avance
```

## Modos (pestañas)

- **Entrenar IA**: la IA entrena y se ve una partida en vivo, con la gráfica del avance y
  el panel "lo que decide la red".
- **Campeón**: el mejor de cada misión jugando.
- **Jugar tú**: empiezas en fase de despliegue (coloca las baterías y pulsa
  «¡Comenzar ataque!» o `Espacio`); las áreas se colorean según su cobertura. Lo que
  fija el radar se derriba aunque no dispares tú, y puedes adelantarte con clic.
- **Comandante**: partida libre y continua, con pestañas B1…Bn, «+ Batería» y
  «− Batería».

**Teclas:** `Espacio` comenzar/pausa · `+`/`−` velocidad · `F9` grabar video ·
`F12` captura · `Esc` salir.

## El juego

- **10 misiones**: Primera alerta, Campo abierto, Saturación, Morteros en la frontera,
  Enjambre, Dos frentes, Reubicación, Tormenta, Red de baterías y Defensa en profundidad.
- **Baterías configurables**: de 1 a 8 lanzadores por batería y varias baterías, cada
  una con su radar. Se mueven a 70 km/h (plegar → en ruta → desplegar) y no disparan en
  movimiento.
- **Radar** con retardo y calidad de traza; la incertidumbre del impacto baja con cada
  barrido. Un misil se **fija** si va a caer en un área o a pasar sobre ella, y queda fijado
  hasta derribarlo.
- **Mapa ficticio o real**: busca una ciudad, escribe `lat, lon` o pega un enlace de Google
  Maps. Vistas Terreno (Esri), Híbrido y Calles y casas (OpenStreetMap), con teselas
  más detalladas al acercar. Google Maps sólo se abre con un botón en el navegador.

## Cómo aprende

- `cerebro.py`: la red recibe 20 datos por amenaza y responde ENFRENTAR y SALVA DOBLE.
- `evolucion.py`: estrategia evolutiva con varios procesos, clases automáticas del
  instructor (`doctrina.py`) e imitación de tus partidas en Jugar tú.

## Archivos

| Archivo | Qué hace |
|---|---|
| `main.py` | Punto de entrada y opciones |
| `config.py` | Parámetros del juego |
| `simulacion.py` | Amenazas, radar, baterías y tiro |
| `misiones.py`, `mundo.py` | Misiones y escenario |
| `doctrina.py` | El instructor (reglas expertas) |
| `cerebro.py`, `evolucion.py` | Red y entrenamiento |
| `geo.py` | Mapas reales, búsqueda de lugares y teselas |
| `interfaz.py` | Ventana (pygame) |
| `rapido_gui.py` | Ventana del entrenamiento rápido |
| `grabador.py` | Grabar video |

El avance se guarda en `datos\`, los mapas descargados en `mapas\` y los videos en
`grabaciones\`.
