# Emulador Game Boy Color con IA

Emulador propio de **Game Boy y Game Boy Color** (escrito en Python y acelerado con
numba) con una **IA que aprende a jugar** el juego que cargues. La IA lee las
instrucciones del juego, explora y guarda puntos de control para seguir avanzando, y
también puede aprender viéndote jugar.

## Ejecutar

Doble clic en **`Iniciar_Emulador.bat`** (instala numpy, numba, Pillow, sounddevice,
pypdf e imageio-ffmpeg si faltan). La primera vez tarda unos segundos en compilar el
emulador.

```bash
python main.py                  # abre con la última ROM usada
python main.py juego.gbc        # abre esa ROM (se copia a roms\)
python main.py --jugar          # abrir jugando tú
python main.py --entrenar       # empezar a entrenar al abrir
python main.py --turbo          # entrenar sin animación
python main.py --nuevo          # la IA de ese juego empieza desde cero
```

## ROMs

Con **Agregar ROM…** se copian a la carpeta `roms\` (`.gb`, `.gbc` o dentro de un
`.zip`). Se quedan ahí hasta que las borres con **Borrar**; lo aprendido por la IA se
conserva aunque borres la ROM. Las partidas guardadas del cartucho (y su reloj, como en
Pokémon) se guardan por juego.

## Modos

- **🎮 Jugar tú**: juegas con el teclado; tus jugadas se graban para que la IA te imite y
  las pantallas a las que llegas se vuelven puntos de partida para ella.
- **🤖 Ver a la IA**: la IA actual jugando en grande, con sonido y con las probabilidades de
  cada botón.
- **👥 Generación**: mosaico con 6 individuos de la generación en curso; al terminar se ve
  la aptitud de cada uno y el mejor queda en dorado.
- **⚡ Turbo**: sólo entrena.
- **🕹 Tomar control** (o `T`): mientras ves a la IA, tomas el mando justo donde va, sin
  detener el entrenamiento. Tus jugadas se graban para que te imite y los lugares a los que
  llegas se vuelven puntos de control. **🤖 Devolver control** (o `T`) hace que aprenda de
  inmediato de lo que hiciste y siga jugando desde ahí.

Botones: Entrenar/Pausar, Guardar, **📍 Fijar inicio aquí** (la IA entrena desde ese
momento del juego; útil para saltar menús), velocidad de la IA ×1–×8, Reiniciar IA,
Sonido y Grabar.

**Teclas:** flechas · `A`/`X`/`Espacio` = botón A · `S`/`Z` = botón B · `Enter` = START ·
`Retroceso` = SELECT · `T` tomar/devolver control · `Tab` rápido · `P` pausa · `M` sonido · `F1`/`F2` guardar/cargar
estado · `F5` guardar la IA.

## Emulador

- `nucleo.py`: CPU, memoria con MBC1, MBC2, MBC3 (con reloj) y MBC5, video a color y del
  Game Boy original, HDMA, temporizadores y sonido de 4 canales.
- Pasa las pruebas de CPU de Blargg (`cpu_instrs`, `instr_timing`) y las de video
  `cgb-acid2` y `dmg-acid2`.
- `consola.py`: cargar ROMs, botones, partidas del cartucho y estados guardados.
- `sonido.py`: salida de audio con sounddevice.

## Cómo aprende la IA

- **Instrucciones** (`instrucciones.py`): lee un `.txt`, `.md` o `.pdf` junto a la ROM, o lo
  que pegues en «Editar / pegar». Detecta qué hace cada botón, cuántas vidas hay y los
  objetivos, y con eso define los botones que usa la IA.
- **Red** (`cerebro.py`): mira la pantalla reducida a 20×18 y el cambio respecto al paso
  anterior, y decide qué botones apretar cada 4 cuadros.
- **Entrenamiento** (`entrenador.py`, `agente.py`): estrategia evolutiva en varios
  procesos. Premia descubrir **pantallas nuevas** y guarda **puntos de control** (estados
  del juego) desde donde las siguientes generaciones siguen explorando.
- **Detector** (`detector.py`): busca solo en la memoria del juego las vidas y los
  contadores de puntos, para castigar morir y premiar puntos. También busca la
  **posición del jugador** (X/Y que cambian de uno en uno con las flechas) y el **número de
  mapa**; en juegos así (Pokémon, Zelda, RPG) el premio pasa a ser **lugares nuevos del
  mundo** y las pantallas de menú casi no cuentan, abrir START/SELECT cuesta un poco y el
  episodio se corta si da vueltas sin descubrir nada («dio vueltas»).
- **Avance** (`perfiles.py`): para juegos conocidos (Pokémon Oro/Plata) se leen directo de la
  memoria la posición, el mapa, los niveles y la experiencia del equipo, las medallas, la
  Pokédex y las banderas de eventos de la historia. Ganar peleas, subir de nivel, atrapar,
  ganar medallas y cumplir eventos se premia; en otros juegos las banderas se detectan solas
  (bits que sólo se encienden).
- **Go-Explore por avance**: cada punto de control guarda su avance y la mitad de las veces
  se parte de la frontera (lo más avanzado). Tras cada evento de la historia los lugares
  vuelven a contar como nuevos, para las misiones que obligan a regresar.
- **Mini-mapa en la red**: además de la pantalla, la red ve 9×9 casillas alrededor del
  jugador con lo ya explorado (siempre y en el episodio), para no dar vueltas.
- **Brújula de exploración**: apunta hacia las casillas no visitadas (en el episodio y en
  total), aprende qué casillas están bloqueadas al chocar y va conectada directo a las
  flechas con un empuje inicial de curiosidad que el entrenamiento ajusta; se apaga sola en
  peleas y diálogos. La IA elige el botón por probabilidades (temperatura 0.5) y en juegos con
  posición no usa «no hacer nada».
- **Grabación**: sólo se graban los pasos en que aprietas algo.
- **Exploración**: rachas de botones al azar y ruido de la estrategia evolutiva que crece
  solo cuando todos los individuos empatan.
- **Imitación**: tus jugadas entrenan la red directamente.

Los datos de cada juego se guardan en `datos\<TITULO>\` (modelo, puntos de control,
jugadas, perfil e historial) y las instrucciones en `instrucciones\`.
