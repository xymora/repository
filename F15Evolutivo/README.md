# F-15 evolutivo

Simulador de vuelo de un **F-15** en 3D, todo **desde la cabina**: tablero con radar,
horizonte artificial, HSI, mapa móvil y HUD. Una **IA aprende a pilotar** con un plan de
lecciones, desde el despegue hasta el combate aéreo, y también puedes volar tú.

Los pilotos son **redes neuronales** que aprenden por **generaciones** con una
**estrategia evolutiva** (con Adam), con clases automáticas de un instructor y la
imitación de lo que vueles tú.

## Ejecutar

Doble clic en **`Iniciar_Simulador.bat`** (abre el menú de inicio; instala numpy,
pygame y moderngl si faltan). Para entrenar sin gráficos: **`Entrenar_Rapido.bat`**.

```bash
python main.py                 # menú de inicio
python main.py --ia            # ver a la IA aprender
python main.py --jugar         # pilotar la lección 1
python main.py --libre         # vuelo libre
python main.py --listar        # ver las misiones disponibles
python main.py --mision 13     # pilotar una misión (número o id)
python main.py --ver 6         # ver a la IA volar una misión
python main.py --entrenar 4    # entrenar a la IA sólo en esa misión
python main.py --curriculo mezcla
python main.py --resolucion 1920x1080   # o --ventana / --pantalla-completa
python main.py --rapido        # entrenamiento rápido sin gráficos
python entrenar_rapido.py --minutos 60 --generaciones 500 --sin-grafica
```

Requiere una tarjeta de video con OpenGL 3.3.

## Misiones

Definidas en `config_misiones\*.json`:

1. Despegue · 2. Ascenso y crucero · 3. Virajes · 4. Navegación entre montañas ·
5. Aproximación por senda (termina aterrizando) · 6. Aterrizaje · 7. Circuito completo ·
8. Intercepción · 9. Duelo con cañón · 10. Arranque en frío y despegue ·
11. Patrulla aérea (CAP) · 12. Vuelo integral · 13. Combate aéreo.

El **arranque en frío** sigue la lista real paso a paso (carlinga, arrancador, bombas,
motores, aviónica, controles, rodaje y despegue), con las teclas `1`–`0` o con clic en el
panel.

## Controles

En el menú: flechas y `Enter` o clic; `F1` muestra los controles de vuelo. Durante la
vista de la IA, **`J`** toma los mandos del avión que se sigue y lo vuelto se usa como
clase de imitación; `J` otra vez los devuelve. Clic en un rombo sigue a ese individuo.
`F2` abre el panel del aprendizaje · `F5` guarda la IA · `F9` graba video · `R` reintentar ·
`Esc` menú.

## Cómo aprende

- **Física** (`fisica.py`): toda la flota vectorizada, con límite de G y ángulo de ataque,
  tren de aterrizaje, motores, combustible, postquemador y fatiga estructural.
- **Red** (`cerebro.py`): 39 entradas y 7 salidas por piloto.
- **Entrenamiento** (`evolucion.py`): varios escenarios en paralelo. El currículo puede ser
  secuencial o mezclado, con repaso de lecciones ya superadas. Hay clases del instructor
  (`piloto.py`) al empezar cada lección o al estancarse, y se vuelve al campeón si la
  población empeora. Una lección sólo cuenta como superada si se voló con estabilidad.
- **Entrenamiento rápido** (`entrenar_rapido.py`): sin gráficos y con una ventana con la
  gráfica del avance (`grafica.py`).

## Archivos principales

`render.py` y `texturas.py` (3D con moderngl: terreno con niveles de detalle, mar, cielo,
nubes, pista con luces y sombras) · `cabina.py`, `hud.py` y `tablero.py` (instrumentos) ·
`terreno.py` · `misiones.py` y `catalogo.py` · `arranque.py` · `sonido.py` · `grabador.py`.

El avance se guarda en `datos\` y los videos en `grabaciones\`.
