# Snake evolutivo

Una población de 200 víboras aprende a jugar **Snake** con **redes neuronales** que
evolucionan por **generaciones** con una **estrategia evolutiva** (con Adam). Toda la
población juega en paralelo y la ventana muestra a la mejor.

Hecho sólo con tkinter y numpy, sin bibliotecas de juego.

## Ejecutar

Doble clic en **`Iniciar_Simulador.bat`** (instala numpy e imageio-ffmpeg si faltan), o:

```bash
python main.py                 # entrenar viendo la animación (continúa lo guardado)
python main.py --nuevo         # empezar desde cero
python main.py --demo          # ver a la campeona guardada
python main.py --turbo         # entrenar sin animación
python main.py --poblacion 300 --semilla 3
```

## Teclas

`Espacio` pausa · `T` turbo · `+`/`−` velocidad · `C` campeona (`←`/`→` cambia de nivel) ·
`G` guardar · `N` reiniciar · `Esc` salir.

## Niveles

1. Jardín (tablero chico y despejado) · 2. Pradera (más espacio, frutas más lejos) ·
3. Pilares · 4. Muros con pasos angostos · 5. Cruz · 6. Habitaciones unidas por puertas ·
7. Serpentina (pasillos en zigzag) · 8. Fortaleza.

Se sube de nivel cuando la mejor víbora alcanza la meta del nivel 3 generaciones seguidas
(metas de 15 a 50 frutas).

## Cómo aprende

- **Red** (`cerebro.py`): 28 entradas → 24 → 16 → 3 salidas (girar hacia un lado,
  seguir derecho o girar hacia el otro), evaluada para toda la población a la vez.
- **Evolución** (`evolucion.py`): estrategia evolutiva especular con Adam; la población
  incluye siempre la media actual y la élite.

## Archivos

`config.py` · `niveles.py` · `simulacion.py` (toda la población en paralelo) ·
`cerebro.py` · `evolucion.py` · `interfaz.py` y `tema.py` (ventana con tema oscuro) ·
`grabador.py` (grabar la pantalla en video) · `main.py`.

El avance se guarda en `datos\` (`estado.json`, `campeones.json`, `historial.csv`).
