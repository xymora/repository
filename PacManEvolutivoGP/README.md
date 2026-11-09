# Pac-Man evolutivo (programación genética)

El mismo juego propio **tipo Pac-Man** que `PacManEvolutivo`, pero aquí el "cerebro" de
cada comecocos **no es una red neuronal**: es un **programa** (un árbol de reglas
SI / ENTONCES) que evoluciona con **programación genética**. El programa que se está
evaluando se ve escrito en vivo en la ventana.

## Ejecutar

Doble clic en **`Iniciar_Simulador.bat`** (instala numpy y pygame si faltan), o:

```bash
python main.py                  # entrenar viendo la animación (continúa lo guardado)
python main.py --nuevo          # empezar desde cero
python main.py --demo           # ver al mejor guardado
python main.py --rapido         # modo rápido (sin animación)
python main.py --generaciones   # carrera de generaciones
python main.py --poblacion 150 --semilla 4
```

## Teclas

`Espacio` pausa · `T` modo rápido / animar · `+`/`−` velocidad · `G` carrera de
generaciones · `Tab`/`L` cambiar de comecocos seguido · `S` sensores · `N` programa ·
`M` sonido · `F5` guardar · `F11` pantalla completa.

## Cómo aprende

- **Programas** (`programa.py`): árboles guardados como listas JSON y compilados a
  funciones de Python, con simplificación de constantes y traducción a texto legible.
- **Evolución** (`evolucion.py`): selección por torneo de 4, élite de 2, cruce de
  subárboles, mutaciones y un castigo por tamaño para que los programas sigan siendo
  cortos (máximo 70 nodos).

## Niveles

Los mismos 8 niveles que la versión con red. En el **nivel 8 (Laberinto infinito)** el
laberinto se queda fijo hasta que algún comecocos lo limpia **sin perder vidas**; entonces
se crea otro laberinto diferente, de otro color, indefinidamente.

## Archivos

`config.py` · `laberinto.py` · `simulacion.py` · `programa.py` · `evolucion.py` ·
`juego.py` (ventana pygame) · `sprites.py` · `sonido.py` · `grabador.py` · `main.py`.

El avance se guarda en `datos\` (`poblacion.json` y estado).
