# 🧠 Análisis de Sentimiento en Reseñas de Productos/Servicios

Este proyecto realiza un análisis de sentimiento utilizando reseñas de productos o servicios (como las de Amazon o IMDb). Incluye preprocesamiento de texto, entrenamiento de modelos de Machine Learning, evaluación con métricas estándar y visualizaciones interactivas.

## 🎯 Objetivo

Desarrollar un sistema capaz de clasificar reseñas como positivas o negativas, proporcionando insights útiles para la toma de decisiones en negocios.

## 📚 Dataset

Se utiliza un dataset de reseñas que incluye el texto de la reseña y su clasificación correspondiente (positiva o negativa). El archivo `data/reviews.csv` debe contener al menos dos columnas: `review` y `sentiment`.

## 🧠 Técnicas Aplicadas

- Limpieza y normalización de texto
- Tokenización, eliminación de stopwords
- Stemming y lematización
- Vectorización con TF-IDF
- Clasificación con Regresión Logística
- Evaluación con F1-score, precisión, recall y matriz de confusión
- Visualización con Seaborn y Plotly
- App interactiva con Streamlit

## 🛠️ Tecnologías

- Python 3.x  
- Pandas  
- NLTK  
- Scikit-learn  
- Matplotlib  
- Seaborn  
- Plotly  
- Streamlit  
- Joblib  

## 📁 Estructura del Proyecto

```
sentiment-analysis-project/
├── data/
│   └── reviews.csv                 # Dataset de reseñas (Amazon o IMDb)
├── notebooks/
│   └── sentiment_analysis.ipynb    # Jupyter Notebook con todo el análisis
├── models/
│   └── logistic_regression.pkl     # Modelo entrenado serializado
├── app/
│   └── dashboard.py                # Aplicación Streamlit para visualización
├── requirements.txt                # Dependencias del proyecto
└── README.md                       # Documentación del proyecto
```

## 🔎 Flujo del Proyecto

1. **Carga de Datos**  
2. **Preprocesamiento de texto**: minúsculas, limpieza, tokenización, stemming  
3. **Vectorización con TF-IDF**  
4. **Entrenamiento del modelo de Regresión Logística**  
5. **Evaluación con métricas estándar**  
6. **Visualización de resultados**  
7. **Despliegue como aplicación con Streamlit**  

## 🚀 Cómo Ejecutar el Proyecto

1. Clona el repositorio:
   ```bash
   git clone https://github.com/tu_usuario/sentiment-analysis-project.git
   cd sentiment-analysis-project
   ```

2. Crea y activa un entorno virtual:
   ```bash
   python -m venv env
   source env/bin/activate  # En Windows: env\Scripts\activate
   ```

3. Instala las dependencias:
   ```bash
   pip install -r requirements.txt
   ```

4. Ejecuta el análisis en Jupyter:
   ```bash
   jupyter notebook notebooks/sentiment_analysis.ipynb
   ```

5. Ejecuta la app:
   ```bash
   streamlit run app/dashboard.py
   ```

## 📊 Outputs

- Modelo entrenado guardado como `models/logistic_regression.pkl`  
- Matriz de confusión y visualizaciones  
- Dashboard en tiempo real accesible en `localhost:8501`

## 📌 Futuras Mejoras

- Integrar modelos BERT para mejores resultados  
- Añadir soporte multilingüe  
- Añadir autenticación y base de datos en la app  

## 📄 Licencia

Este proyecto está licenciado bajo la Licencia MIT.
