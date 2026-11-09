# Minería con drones

Sistema para planear y procesar **vuelos de drones en minas a cielo abierto**:
levantamiento topográfico, mapeo **LiDAR**, modelos 3D, comparación de la excavación
contra las **zonas autorizadas** e **inspección térmica y visual** de seguridad.
Trabaja con un sitio de demostración generado por el programa o con **sitios reales**
(imagen satelital, elevación y datos de OpenStreetMap).

## Ejecutar

Doble clic en **`Iniciar_Mineria.bat`** (instala numpy, scipy, Pillow, matplotlib,
contourpy, moderngl, pygame y pywebview si faltan), o:

```bash
python main.py                                   # abre el sistema
python main.py --proyectos C:\otra\carpeta       # usar otra carpeta de proyectos
python main.py --visor proyecto\vista3d.npz      # abrir directamente el visor 3D
python main.py --google 30.312 -109.545 --nombre "La Caridad"   # mapa de Google incrustado
```

Arranca en La Caridad (Sonora); sin internet usa la demostración. También hay
preajustes para Bingham y Chuquicamata, y se puede buscar cualquier lugar por nombre o
por `lat, lon`.

## Qué hace

1. **Sitio**: descarga imagen satelital (Esri), elevación (AWS Terrarium) y agua,
   edificios, caminos y tajos (OpenStreetMap), en una malla local en metros.
2. **Zonas**: dibuja las zonas autorizadas de extracción y las de exclusión (clic por
   vértice, doble clic o clic derecho cierra, `Esc` cancela). Exporta KML.
3. **Plan de vuelo** (`planificador.py`): líneas de barrido, órbitas a puntos de interés,
   recorrido de la corona del tajo, seguimiento del terreno y reparto entre drones y
   baterías.
4. **Vuelo simulado** (`sensores.py`): LiDAR con retornos múltiples, fotos con su GSD y
   cobertura, y deriva del GNSS.
5. **Procesamiento** (`procesamiento.py`): separa el suelo (DTM), corrige con puntos de
   control y compara dos fechas (DoD) para calcular volúmenes y detectar **excavación
   fuera de zona**.
6. **Inspección**: grietas, derrumbes, agua, personas en zonas de exclusión, equipo junto
   a la corona y anomalías térmicas.
7. **Exportar** (`exportar.py`): LAS con coordenadas UTM, ASC+PRJ, OBJ texturizado,
   GeoJSON, CSV de waypoints y un reporte.

**Visor 3D:** arrastra para girar, rueda para acercar, `1`–`5` cambia la capa,
`E`/`Q` exageración vertical, `H` oculta la ayuda, `F9` graba video, `F12` captura.

**Google:** el botón «Google Maps» abre el mapa oficial incrustado en una ventana propia
(o como capa, si pones tu clave en `config_local.json`). «Google Earth» abre Google
Earth Pro con el KML si está instalado, o Google Earth Web.

## Archivos

`interfaz.py`, `estilo.py` y `capas.py` (ventana) · `geo.py` (proyección, descargas y
búsquedas) · `terreno.py` (sitio real o de demostración) · `planificador.py` ·
`sensores.py` · `procesamiento.py` · `exportar.py` · `visor3d.py` · `mapa_google.py` ·
`grabador.py` · `config.py`.

Los proyectos se guardan en `proyectos\`, los mapas descargados en `mapas\` y lo
exportado en `exportaciones\`.
