# Road Fighter evolutivo 2 (aprendizaje por refuerzo PPO)

El mismo juego propio **tipo Road Fighter** que `RoadFighterEvolutivo`, pero aquí la IA
no evoluciona por selección: aprende con **aprendizaje por refuerzo** usando **PPO**
(actor-crítico), después de un preentrenamiento por imitación del piloto experto.

## Ejecutar

Doble clic en **`Iniciar_Simulador.bat`** (instala numpy y pygame si faltan), o:

```bash
python main.py                  # entrenar viendo la animación (continúa lo guardado)
python main.py --nuevo          # empezar desde cero
python main.py --demo           # ver al mejor guardado
python main.py --rapido         # modo rápido dentro de la ventana
python main.py --generaciones   # carrera de generaciones
python main.py --poblacion 40 --semilla 4
```

## Teclas

`Espacio` pausa · `T` modo rápido / animar · `+`/`−` velocidad · `G` carrera de
generaciones · `Tab`/`L` cambiar de auto seguido · `S` sensores · `N` red · `M` sonido ·
`F5` guardar · `F11` pantalla completa.

## Cómo aprende

`aprendizaje.py` sustituye al `evolucion.py` de las otras versiones y conserva la misma
interfaz de entrenador:
- **Red actor-crítico** de 37 → 64 → 64 → 3 acciones.
- **PPO** con ventaja generalizada (GAE), recorte y freno temprano por divergencia KL. La
  actualización corre en un hilo aparte y la ventana muestra la caja "Aprendiendo".
- **Preentrenamiento por imitación** del maestro (`maestro.py`) y **DAgger**: al principio
  el maestro corrige con frecuencia y su ayuda va disminuyendo con las generaciones.
- La normalización de entradas se fija después de imitar, para que no cambie bajo la red.

4 niveles: Pradera, Puente, Montaña y Costa.

## Archivos

`config.py` · `pista.py` · `simulacion.py` · `cerebro.py` · `aprendizaje.py` ·
`maestro.py` · `juego.py` (ventana pygame) · `sprites.py` · `sonido.py` · `grabador.py` ·
`main.py`.

El avance se guarda en `datos\`.
