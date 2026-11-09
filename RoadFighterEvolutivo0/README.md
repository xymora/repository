# Road Fighter evolutivo 0 (estrategia evolutiva desde cero)

El mismo juego propio **tipo Road Fighter** que `RoadFighterEvolutivo`, con la misma
física, pistas y gráficos, pero aquí la IA **aprende completamente desde cero**: no hay
piloto maestro ni imitación. Sirve para comparar cuánto ayuda el maestro (versión v1) y
cómo rinde el aprendizaje por refuerzo (versión 2).

## Ejecutar

Doble clic en **`Iniciar_Simulador.bat`** (instala numpy y pygame si faltan), o:

```bash
python main.py                  # entrenar viendo la animación (continúa lo guardado)
python main.py --nuevo          # empezar desde cero
python main.py --demo           # ver al mejor guardado
python main.py --rapido         # modo rápido dentro de la ventana
python main.py --generaciones   # carrera de generaciones
python main.py --algoritmo ga   # algoritmo genético en vez de estrategia evolutiva
python main.py --poblacion 120 --semilla 4
```

## Teclas

`Espacio` pausa · `T` modo rápido / animar · `+`/`−` velocidad · `G` carrera de
generaciones · `Tab`/`L` cambiar de auto seguido · `S` sensores · `N` red · `M` sonido ·
`F5` guardar · `F11` pantalla completa.

## Cómo aprende

- **Red recurrente** (`cerebro.py`): 37 → 24 (recurrente) → 16 → 3 salidas.
- **Evolución** (`evolucion.py`): estrategia evolutiva especular con Adam y salón de la
  fama, o algoritmo genético con `--algoritmo ga`.
- 4 niveles: Pradera, Puente, Montaña y Costa.

## Archivos

`config.py` · `pista.py` · `simulacion.py` · `cerebro.py` · `evolucion.py` · `juego.py`
(ventana pygame) · `sprites.py` · `sonido.py` · `grabador.py` · `main.py`.

El avance se guarda en `datos\`.
