# Contra evolutivo

Juego de acción y plataformas propio **tipo Contra**, donde una IA aprende a correr,
saltar, disparar y esquivar a lo largo de 8 etapas con jefes. No usa ROM ni gráficos de
Konami: todo se dibuja por código con numpy y los nombres son originales. Se puede
entrenar **1 jugador** o **2 jugadores** cooperando.

Cada soldado es una **red neuronal** que aprende por **generaciones** con una
**estrategia evolutiva** (con Adam). Mientras la población entrena en segundo plano,
la ventana muestra a la élite jugando en vivo.

## Ejecutar

Doble clic en **`Iniciar_Simulador.bat`** (instala numpy e imageio-ffmpeg si faltan), o:

```bash
python main.py                  # entrenar (1 jugador, continúa lo guardado)
python main.py --jugadores 2    # entrenar el modo de 2 jugadores
python main.py --nuevo          # empezar ese modo desde cero
python main.py --campeona       # ver a la campeona guardada
python main.py --jugar          # jugar tú como jugador 1
python main.py --semilla 4
```

Requiere Python 3.8+ y **numpy**. La ventana es tkinter (sin bibliotecas de juego).

## Teclas

`Espacio` pausa · `T` turbo · `+`/`−` velocidad · `1`/`2` jugadores ·
`C` campeona (`←`/`→` cambia de etapa) · `G` guardar · `N` reiniciar · `Esc` salir.

**Jugar tú (`J`):** flechas mueven y apuntan, `Z` salta, `X` dispara. La red **aprende
de tus jugadas** por imitación (se descartan los instantes justo antes de morir) y, si
superas una etapa jugando, la IA pasa a la siguiente.

## Etapas

Jungla · Base 1 · Cascada (vertical) · Base 2 · Nieve · Zona de energía · Hangar ·
Guarida alienígena. Cada una tiene su jefe. Se pasa de etapa cuando alguien la supera
2 generaciones seguidas.

## Cómo aprende

- **Sensores** (`sensores.py`): 162 entradas relativas a hacia dónde mira el soldado,
  con líneas de fuego de los tiradores y trayectorias de las balas cercanas.
- **Red**: 162 → 48 → 24 → 5 salidas.
- **Recompensas**: avanzar, dañar al jefe, eliminar enemigos fijos (las oleadas
  infinitas no cuentan) y **esquivar** balas; castigos por morir, quedarse en el agua
  o atorarse.
- **Evolución** (`evolucion.py`): estrategia evolutiva especular con Adam, evaluada con
  varios procesos en prioridad baja. En 2 jugadores se evolucionan las dos redes juntas
  con una aptitud de equipo.

## Archivos

| Archivo | Qué hace |
|---|---|
| `main.py` | Punto de entrada y opciones |
| `config.py` | Parámetros y recompensas |
| `mundo.py` | Simulación (30 ticks/s, sin interfaz) |
| `etapas.py`, `jefes.py` | Las 8 etapas y sus jefes |
| `sensores.py` | Lo que "ve" la red |
| `cerebro.py` | Red neuronal e imitación |
| `evolucion.py` | Entrenamiento y guardado |
| `graficos.py` | Fondos y sprites procedurales |
| `interfaz.py`, `tema.py` | Ventana y estilo oscuro |
| `grabador.py` | Grabar la pantalla en video |

El avance se guarda en `datos\1_jugador` y `datos\2_jugadores` (cada 10 generaciones, al
subir de etapa, al pulsar Guardar y al salir); tus jugadas en `demos.npz`.
