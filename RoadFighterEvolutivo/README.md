# Road Fighter evolutivo (estrategia evolutiva + maestro)

Juego de carreras propio **tipo Road Fighter**: un auto debe llegar a la meta esquivando
el tránsito, sin chocar y sin quedarse sin gasolina. No usa ROM ni gráficos de Konami: el
pixel art, la fuente y el sonido son originales.

Esta versión (**v1**) aprende con una **red neuronal recurrente** evolucionada por
**generaciones** con una **estrategia evolutiva**, y al abrir por primera vez **imita a un
piloto experto** (`maestro.py`) para arrancar con ventaja.

Hay dos carpetas hermanas con el mismo juego para comparar:
`RoadFighterEvolutivo0` (estrategia evolutiva desde cero, sin maestro) y
`RoadFighterEvolutivo2` (aprendizaje por refuerzo PPO).

## Ejecutar

Doble clic en **`Iniciar_Simulador.bat`** (instala numpy y pygame si faltan), o:

```bash
python main.py                  # entrenar viendo la animación (continúa lo guardado)
python main.py --nuevo          # empezar desde cero
python main.py --demo           # ver al mejor guardado
python main.py --rapido         # modo rápido dentro de la ventana
python main.py --generaciones   # carrera de generaciones
python main.py --algoritmo ga   # algoritmo genético para comparar
python main.py --poblacion 120 --semilla 4
```

## Teclas

`Espacio` pausa · `T` modo rápido / animar · `+`/`−` velocidad · `G` carrera de
generaciones · `Tab`/`L` cambiar de auto seguido · `S` sensores · `N` red · `M` sonido ·
`F5` guardar · `F11` pantalla completa.

## El juego

- **4 niveles**: Pradera, Puente, Montaña y Costa, con pistas procedurales.
- Tránsito más lento que el jugador que hay que rebasar; el auto rojo cierra el paso.
  Hay manchas de aceite, combustible, reversa y cambio LOW/HIGH.
- Recompensas por avanzar, rebasar y el auto arcoíris; castigos por chocar.

## Cómo aprende

- **Red recurrente** (`cerebro.py`): 37 → 24 (recurrente) → 16 → 3 salidas, con
  normalización de entradas.
- **Evolución** (`evolucion.py`): estrategia evolutiva especular con rangos centrados,
  Adam y salón de la fama; opcionalmente algoritmo genético.
- **Maestro** (`maestro.py`): piloto experto que elige el carril con más espacio, frena a
  tiempo y usa la reversa si se pega. Su manejo se imita una vez al abrir.

## Archivos

`config.py` · `pista.py` · `simulacion.py` · `cerebro.py` · `evolucion.py` ·
`maestro.py` · `juego.py` (ventana pygame con paneles de red, gráfica, población y
telemetría) · `sprites.py` · `sonido.py` · `grabador.py` · `main.py`.

El avance se guarda en `datos\`; `datos_respaldo_*` es una copia hecha antes de la
imitación del maestro.
