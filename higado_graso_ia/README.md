# IA para detección y gradación de hígado graso en ecografía

Programa que analiza **ecografías en modo B del hígado** y clasifica la esteatosis
hepática en cuatro grados (S0 sin esteatosis, S1 leve, S2 moderada, S3 grave), usando un
modelo de aprendizaje profundo con referencia histológica. **El modelo ya viene
entrenado**: no hace falta entrenar para diagnosticar.

La documentación completa ya existe en esta carpeta:
- **[LEEME.md](LEEME.md)**: descripción técnica, estructura, datos, entrenamiento y
  resultados.
- **[GUIA_DE_USO.md](GUIA_DE_USO.md)**: instrucciones paso a paso para personal de salud.

## Inicio rápido

1. **`Instalar.bat`**: instala Python y las librerías (una sola vez; ver
   `requirements.txt`).
2. **`Iniciar_IA_Higado_Graso.bat`**: abre el programa.
3. Carga las imágenes del paciente y obtén el grado con el mapa de atención (Grad-CAM).

Opcional: **`Crear_acceso_directo.bat`** crea el ícono en el escritorio.

## Carpetas

| Carpeta | Contenido |
|---|---|
| `programa\` | Programa con ventanas, inferencia, entrenamiento, métricas y figuras |
| `modelos\` | Modelo entrenado (`.pt`) y su configuración (`.json`) |
| `datos\` | Ecografías por grado (S0–S3), metadatos y datos de pacientes |
| `extras\` | Preparación de datos, análisis no supervisado, app y cuaderno para Colab |
| `resultados\` | Resultados y figuras generados |
