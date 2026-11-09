# Licencia y datos: nota de recomendación

> **Esto es una recomendación, no una decisión.** No se creó un archivo `LICENSE`: elegir la licencia corresponde al autor. Esta nota no es asesoría legal; antes de cualquier uso comercial conviene que un abogado revise los términos vigentes.

## 1. Código: opciones

| Opción | Ventajas | Desventajas | Cuándo elegirla |
|---|---|---|---|
| **Apache-2.0** (recomendada si el objetivo es doctorado o reputación) | Las empresas la aceptan sin fricción; concesión explícita de patentes; permite uso comercial | Terceros pueden cerrar sus derivados | Paper, colaboración universidad-industria, máxima adopción |
| **MIT** | Mínima y muy conocida | Sin cláusula de patentes | Proyecto docente sencillo |
| **Dual: AGPL-3.0 + licencia comercial** | Protege el valor comercial: quien lo integre en un servicio cerrado debe pagar o liberar su código | Muchos departamentos legales corporativos **bloquean la AGPL**, lo que frena pilotos | Si se busca ingreso por licencias del caso de uso 1 |
| **Sin licencia** (estado actual) | — | Legalmente nadie puede usar, copiar ni modificar el código; inhibe la colaboración | No recomendada si se publica el repositorio |

Si se publica el paper con código, la recomendación del panel es **Apache-2.0**. Si se elige otra licencia, hay que documentar el porqué en el README.

## 2. Datos de OpenStreetMap (calles)

- Están bajo la **Open Database License (ODbL 1.0)**: https://www.openstreetmap.org/copyright
- **Atribución obligatoria:** "© OpenStreetMap contributors". El simulador ya la muestra en el mapa; debe aparecer también en el paper, el deck y las capturas.
- **Share-alike:** si se redistribuye una *base de datos derivada* (por ejemplo los `datos/*_osm.json` procesados), debe ir bajo ODbL. Las imágenes producidas (*produced works*) sólo requieren atribución.
- **Política de uso de los servidores:** las descargas vía Overpass y Nominatim tienen límites de uso. No se deben hacer descargas masivas en pruebas automáticas ni en CI; se usan los archivos ya cacheados en `datos/`.

## 3. Imagen satelital de Esri (World Imagery)

- Tiene **términos de uso propios de Esri y de sus proveedores**. En general la atribución es obligatoria y el uso **comercial**, la redistribución de mosaicos y el almacenamiento masivo pueden requerir cuenta o licencia de ArcGIS. **Verificar los términos vigentes** en el sitio de Esri antes de:
  - redistribuir los `datos/*_satelite.jpg` (recomendación: **excluirlos del repositorio público**, por ejemplo con `.gitignore`);
  - usar capturas satelitales en una demo pagada o en material comercial.
- Para material externo se recomienda usar en las capturas un fondo propio (OSM renderizado o mapa sin imagen), o mantener la atribución visible y limitarse al uso académico.

## 4. Marcas y nombre

- "Terminator" es una **marca registrada de terceros**. El repositorio puede seguir llamándose MotoTerminator para uso personal y académico, pero para material externo se usa el nombre técnico **MT-Bench** y el nombre comercial se define antes de cualquier uso comercial.
- Los nombres de Honda, Yamaha, BMW, Bosch, Ducati, dSPACE e IPG se citan sólo como referencia del estado del arte, sin sugerir afiliación ni respaldo.

## 5. Propiedad intelectual

- **Arte previo** que impide reclamar novedad en los mecanismos: CMG en vehículos de dos ruedas (Lit Motors, patente US11648994B2) y control activo del centro de masa (Yamaha AMCES).
- **Posible aporte original:** el método de generación de escenarios críticos con currículo evolutivo y requisitos STL (caso de uso 1). Si se considera patentar, hay que presentar la *invention disclosure* **antes** de publicar el paper y verificar con el IMPI o con la oficina correspondiente el periodo de gracia vigente por divulgación propia.

## 6. Checklist antes de publicar

- [ ] Elegir la licencia y crear `LICENSE` (decisión del autor).
- [ ] Atribución OSM en el README, el paper, el deck y las capturas.
- [ ] Excluir del repositorio público las imágenes Esri cacheadas, o verificar los términos.
- [ ] Usar "MT-Bench" en el material externo.
- [ ] Revisar que ningún archivo de `datos/` contenga información personal (por ejemplo, rutas A→B con domicilios).
