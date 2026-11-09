# Escudo Global

Versión mundial del **Domo de Defensa Móvil**: un juego de defensa contra misiles de
largo alcance lanzados desde otros países, con intercepción en **fase de impulso**, en el
**espacio**, a **gran altitud** y en la **fase terminal**. Incluye ojivas múltiples que se
separan en ojivas y señuelos, planeadores, submarinos y amenazas nucleares. Es un juego:
usa valores de juego, no parámetros reales.

Una **IA** aprende a decidir qué amenazas enfrentar con una **red neuronal** entrenada por
**generaciones** con una **estrategia evolutiva**, más clases de un instructor y la
imitación de tus partidas.

## Ejecutar

Doble clic en **`Iniciar_Simulador.bat`** (instala numpy, pygame, Pillow e
imageio-ffmpeg si faltan). Para entrenar sin gráficos: **`Entrenar_Rapido.bat`**.

```bash
python main.py                         # abre en la pestaña Entrenar IA
python main.py --modo jugar            # entrenar | campeon | jugar | comandante
python main.py --sin-entrenar
python main.py --rapido                # entrenar en la consola (Ctrl+C detiene)
python main.py --rapido-gui            # ventana pequeña con la red y el mapa en vivo
python main.py --rapido --minutos 60   # o --generaciones 100
python main.py --datos C:\otra\carpeta
```

## Modos

Las mismas 4 pestañas que el Domo: **Entrenar IA**, **Campeón**, **Jugar tú** (fase de
despliegue: arrastra tus activos y pulsa «Comenzar ataque» o `Espacio`) y
**Comandante**. **Teclas:** `Espacio` comenzar/pausa · `F9` grabar · `F12` captura · `Esc` salir.

**Elegir el escenario** (en las 4 pestañas):
- **ATACANTES**: agrega cualquier país de la lista, una búsqueda o el punto clicado.
- **Lugar**: buscar o escribir `lat, lon` → Ir / Proteger ciudad / Activo aquí /
  Misión original.
- **ACTIVO**: pon baterías donde quieras. Clic derecho pone o quita un activo, y
  «Automático» las despliega solo.
- **Satélites**: apagados o encendidos; los infrarrojos ven la fase de impulso y los de
  órbita baja siguen lo que va en el espacio.

## Misiones

24 misiones, desde «Primera prueba» y «Fase de impulso» hasta «Rusia contra la OTAN»,
«Submarino frente a México», «Estrecho de Taiwán», «Saturación total» y cuatro misiones
nucleares (la última es «Guerra nuclear global»). Se pueden repetir desde el panel
Entrenar.

## Cómo funciona

- `simulacion.py`: trayectorias por el círculo máximo en coordenadas terrestres, radar con
  horizonte, separación de ojivas y señuelos (los señuelos se queman al reentrar) y
  solución de tiro por capa. Un objetivo fijado se sigue hasta derribarlo, con un
  interceptor por objetivo.
- `doctrina.py`: el instructor que da las clases; `cerebro.py` y `evolucion.py`: la red y
  su entrenamiento en paralelo.
- `satelites.py`: constelación de alerta temprana y seguimiento.
- `geo.py` + `interfaz.py`: mapa mundial con teselas Esri (táctico, satélite, híbrido) y
  perfil de vuelo por altitud.
- `vista_rapida.py` + `rapido_gui.py`: la ventana del entrenamiento rápido.

El avance se guarda en `datos\`, las teselas en `mapas\teselas` y los videos en
`grabaciones\`.
