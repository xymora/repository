# Espectáculo de drones

Diseñador y visor de **espectáculos de luces con drones**: los drones despegan, forman
en el aire figuras 2D o 3D (a partir de un **texto**, una **imagen** o figuras 3D
incluidas), cambian de una figura a otra con colores y efectos de luz, y aterrizan.

## Ejecutar

Doble clic en **`Iniciar_Espectaculo.bat`** (instala numpy, scipy, Pillow, pygame,
moderngl, matplotlib e imageio-ffmpeg si faltan), o:

```bash
python main.py                            # abre el diseñador
python main.py --ver shows\mi_show.json   # calcula ese show y lo abre en el visor 3D
python main.py --visor                    # abre el visor con el último plan calculado
python main.py --visor --camara cine --resolucion 1920x1080
python main.py --visor --capturas 10,25,40 --salida carpeta   # capturas sin ventana
```

## Diseñador

- Agrega escenas desde **texto**, **imagen** (respeta la transparencia o separa el fondo)
  o una de las **14 figuras 3D**, cada una con su paleta.
- Elige número de drones, separación mínima, colores y modos de color, movimientos
  (girar, vaivén, latido, ola) y efectos de luz.
- Guarda y abre shows en `shows\`; hay ejemplos en `ejemplos\`.

## Cómo se planea el vuelo

`planificador.py` arma la secuencia **tierra → prueba de luces → despegue → escenas →
regreso → aterrizaje**:
- reparte los puntos de cada figura de forma uniforme (`formaciones.py`);
- asigna cada dron a su lugar con el método húngaro para que nadie se cruce;
- traza trayectorias suaves y sincronizadas, respetando la velocidad máxima;
- verifica la separación mínima y exporta un **CSV por dron** en `exportaciones\`.

## Visor 3D

Cielo, ciudad, árboles, plataformas iluminadas, drones con brillo y estelas, y 5 cámaras.

**Teclas:** `Espacio` pausa · `←`/`→` ±5 s · `↑`/`↓` velocidad · `C` cámara · arrastrar
gira · rueda acerca · `T` estelas · `B` cuerpos de los drones · `H` interfaz ·
`F9` grabar video · `F12` captura · `R` reiniciar · `Esc` salir.

## Archivos

| Archivo | Qué hace |
|---|---|
| `main.py` | Punto de entrada |
| `editor.py`, `estilo.py` | Diseñador (tkinter, tema oscuro) |
| `formaciones.py` | Puntos de cada figura (texto, imagen, 3D) |
| `planificador.py` | Asignación, trayectorias y exportación |
| `visor.py`, `render.py`, `hud.py` | Visor 3D (moderngl) |
| `grabador.py` | Grabar video |
| `config.py` | Parámetros |

El último plan calculado queda en `datos\plan_actual.npz` y los videos en `grabaciones\`.
