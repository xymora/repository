# 1942 evolutivo

Shooter vertical propio **tipo 1942** donde una IA aprende a pilotar un avión de doble
fuselaje sobre el océano. No usa ROM, gráficos ni nombres de Capcom: el arte se dibuja
por código (océano animado, islas, nubes, portaaviones, sombras y explosiones).

El piloto es una **red neuronal** que aprende por **generaciones** con una
**estrategia evolutiva** (con Adam). Cada generación vuela una población de 100 aviones
y la ventana los muestra **en vivo**: la cámara sigue a uno y los demás se ven como
fantasmas translúcidos.

## Ejecutar

Doble clic en **`Iniciar_Simulador.bat`** (instala numpy e imageio-ffmpeg si faltan), o:

```bash
python main.py               # entrenar viendo la generación en vivo (continúa lo guardado)
python main.py --nuevo       # empezar la evolución desde cero
python main.py --campeona    # ver a la campeona guardada
python main.py --jugar       # pilotar tú
python main.py --turbo       # entrenar sin animación
python main.py --poblacion 120 --semilla 4
```

Requiere Python 3.8+ y **numpy**. La ventana es tkinter.

## Teclas

`Espacio` pausa · `T` turbo · `+`/`−` velocidad · `S` seguir al líder ·
`C` campeona (`←`/`→` cambia de misión) · `G` guardar · `N` reiniciar · `Esc` salir.

**Jugar tú (`J`):** flechas mueven, `X` o `Espacio` dispara, `Z` hace un rizo
(invulnerable un momento; 3 por vida), `P` pausa. Tus jugadas se graban y la red
**aprende por imitación** de ellas.

## El juego

- **8 misiones** con oleadas fijas por misión y ambientes de día, tormenta, noche y
  atardecer. Cada una termina con un jefe (Fortaleza gris, Halcón del mar, Coloso de
  hélice, Señor de la tormenta, Ballena de acero, Sombra nocturna, Almirante, Último titán).
- Enemigos: cazas en picada, en curva, en rizo, por detrás y de lado; bombarderos,
  aviones pesados que suben desde abajo y jefes con torretas.
- **POW** (las escuadrillas rojas sueltan uno): **A** mejora el arma (doble → cuádruple →
  abanico), **E** trae 2 escoltas que absorben un golpe, **R** da un rizo extra.
- El avance de una misión pesa 75 % lo sobrevivido y 25 % el daño al jefe.

## Cómo aprende

- **Sensores** (`sensores.py`): estado propio, 6 enemigos y 6 balas cercanas,
  trayectorias de las más peligrosas, un radar de 5×5, el POW y el jefe.
- **Red**: 123 entradas → 48 → 24 → 4 salidas (horizontal, vertical, disparar, rizo).
- **Evolución** (`evolucion.py`): estrategia evolutiva especular con Adam, evaluada en
  paralelo con varios procesos; sigma se reaviva si se estanca y cada generación repasa
  tus jugadas grabadas.

## Archivos

| Archivo | Qué hace |
|---|---|
| `main.py` | Punto de entrada y opciones |
| `config.py` | Parámetros del juego y del entrenamiento |
| `mundo.py` | Simulación del juego (sin interfaz) |
| `misiones.py` | Las 8 misiones y sus oleadas |
| `sensores.py` | Lo que "ve" la red |
| `cerebro.py` | Red neuronal |
| `evolucion.py` | Entrenamiento, guardado e imitación |
| `graficos.py` | Dibujo procedural de aviones, mar y efectos |
| `interfaz.py`, `tema.py` | Ventana y estilo oscuro |
| `grabador.py` | Botón para grabar la pantalla en video |

El avance se guarda en `datos\` (cada 10 generaciones, al pulsar Guardar y al salir);
al volver a abrir continúa donde se quedó. Los videos van a `grabaciones\`.
