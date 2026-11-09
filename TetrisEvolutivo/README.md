# Tetris evolutivo

Una IA aprende a jugar **Tetris** evaluando cada posible colocación de la pieza con 8
características del tablero y ajustando cuánto pesa cada una con **CMA-ES**, un algoritmo
evolutivo. También puedes jugar tú y la IA aprende de tus jugadas.

Hecho sólo con tkinter y numpy, sin bibliotecas de juego.

## Ejecutar

Doble clic en **`Iniciar_Simulador.bat`** (instala numpy e imageio-ffmpeg si faltan), o:

```bash
python main.py                 # entrenar viendo la animación (continúa lo guardado)
python main.py --nuevo         # empezar desde cero
python main.py --campeona      # ver a la campeona guardada
python main.py --jugar         # jugar tú
python main.py --turbo         # entrenar sin animación
python main.py --poblacion 24 --semilla 3
```

## Teclas

`Espacio` pausa · `T` turbo · `+`/`−` velocidad · `C` campeona (`←`/`→` cambia de nivel) ·
`G` guardar · `N` reiniciar · `Esc` salir.

**Jugar tú (`J`):** `←`/`→` mover, `↑` o `X` girar, `Z` girar al revés, `↓` bajar rápido,
`Espacio` soltar, `P` pausa, `J` dejar de jugar.

## Niveles

1. Primeras líneas (limpia 20) · 2. Constancia (80 líneas) · 3. Escombros (empieza con
basura) · 4. Techo bajo (14 filas) · 5. Marea (sube basura cada 14 piezas) · 6. Pasillo
(11 filas) · 7. Diluvio · 8. Maratón (1000 líneas). Para subir, la líder debe superar la
meta en las 5 partidas, 3 generaciones seguidas; al completarlos repasa todos.

## Cómo aprende

- **Evaluador** (`evolucion.py`, `motor.py`): suma ponderada de 8 características —
  altura de aterrizaje, filas eliminadas, transiciones de filas y columnas, huecos, pozos,
  profundidad de huecos y filas con huecos. Se prueban todas las colocaciones a la vez.
- **CMA-ES** completo, escrito a mano; los pesos se normalizan porque sólo importa su
  proporción.
- **Imitación**: tus jugadas se guardan en `demos.npz`, ajustan los pesos al terminar de
  jugar y se repasan en cada generación.
- La ventana muestra "lo que valora la IA" (los pesos), la población de CMA y la
  campeona de cada nivel.

## Archivos

`config.py` · `piezas.py` · `niveles.py` · `motor.py` · `evolucion.py` · `graficos.py` ·
`interfaz.py` y `tema.py` · `grabador.py` · `main.py`.

El avance se guarda en `datos\` (cada 5 generaciones, al subir de nivel y al salir).
