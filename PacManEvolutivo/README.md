# Pac-Man evolutivo (red neuronal)

Juego propio **tipo Pac-Man** donde una población de comecocos aprende a jugar con una
**red neuronal** que evoluciona por **generaciones**. No usa ROM ni gráficos de Namco:
los laberintos se generan por código y los sprites son propios.

Tiene una carpeta hermana, **`PacManEvolutivoGP`**, con el mismo juego pero con
programación genética en lugar de redes.

## Ejecutar

Doble clic en **`Iniciar_Simulador.bat`** (instala numpy y pygame si faltan), o:

```bash
python main.py                  # entrenar viendo la animación (continúa lo guardado)
python main.py --nuevo          # empezar desde cero
python main.py --demo           # ver a la mejor guardada
python main.py --rapido         # abrir en modo rápido (sin animación)
python main.py --generaciones   # carrera de generaciones
python main.py --algoritmo ga   # algoritmo genético en vez de estrategia evolutiva
python main.py --poblacion 120 --semilla 4
```

## Teclas

`Espacio` pausa · `T` modo rápido / animar · `+`/`−` velocidad · `G` carrera de
generaciones · `Tab`/`L` cambiar de comecocos seguido · `S` sensores · `N` red ·
`M` sonido · `F5` guardar · `F11` pantalla completa.

## El juego

- **8 niveles**: Primer bocado, Cuatro sombras, Jardín rosa, Noche rosa, Ciudad naranja,
  Cripta cian, Volcán y Laberinto infinito. Se sube de nivel con una racha de 3
  generaciones.
- Laberintos simétricos generados por cuadrícula, sin callejones sin salida.
- Los 4 fantasmas con su comportamiento clásico (dispersión y persecución, susto, ojos que
  vuelven a casa, modo "Elroy"), fruta y 3 vidas.
- Cada comecocos juega en su propio mundo, toda la población en paralelo.

## Cómo aprende

- **Red recurrente** (`cerebro.py`): 40 → 24 → 16 con una cabeza compartida que puntúa
  cada dirección; sólo elige entre direcciones libres.
- **Evolución** (`evolucion.py`): estrategia evolutiva (o algoritmo genético con
  `--algoritmo ga`), con salón de la fama.
- Paneles en vivo: red, gráfica del avance, población y telemetría.

## Archivos

`config.py` · `laberinto.py` (generador) · `simulacion.py` (juego vectorizado) ·
`cerebro.py` · `evolucion.py` · `juego.py` (ventana pygame) · `sprites.py` · `sonido.py` ·
`grabador.py` · `main.py`.

El avance se guarda en `datos\` (`poblacion.npz` y estado).
