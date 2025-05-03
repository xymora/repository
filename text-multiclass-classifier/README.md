# 📚 Text Multiclass Classifier

Este proyecto implementa un clasificador de texto multiclase utilizando scikit-learn y el dataset 20 Newsgroups. El flujo cubre desde el preprocesamiento hasta la evaluación del modelo, incluyendo un pipeline reproducible y visualizaciones para presentación profesional.

## 🎯 Objetivo

Construir un sistema de clasificación multiclase de documentos, que sea fácilmente escalable e integrable en APIs, demostrando conocimientos de procesamiento de lenguaje natural y aprendizaje automático.

## 🧠 Técnicas Utilizadas

- Vectorización de texto con TF-IDF
- Clasificación con modelos como Logistic Regression y SGDClassifier
- Validación cruzada con GridSearchCV
- Evaluación con métricas macro y micro
- Reporte `classification_report` de scikit-learn
- Visualización con matplotlib y seaborn

## 🛠️ Tecnologías

- Python 3.10  
- scikit-learn  
- pandas  
- matplotlib  
- seaborn  
- Jupyter Notebook

## 📁 Estructura del Proyecto

text-multiclass-classifier/  
├── data/  
│   └── 20newsgroups_sample.csv       # Subconjunto del dataset  
├── notebook/  
│   └── multiclass_text_classifier.ipynb   # Análisis completo  
├── outputs/  
│   ├── confusion_matrix.png  
│   ├── classification_report.txt  
│   └── model.pkl                      # Pipeline serializado  
├── requirements.txt  
└── README.md

## 🚀 Pipeline del Proyecto

1. Cargar dataset `20newsgroups_sample.csv`  
2. Limpiar y vectorizar texto con TF-IDF  
3. Entrenar modelos con GridSearchCV y validación cruzada  
4. Evaluar rendimiento y exportar métricas  
5. Visualizar matriz de confusión  
6. Serializar pipeline con joblib

## 📊 Resultados

- Clasificación de 5 categorías de texto  
- Accuracy promedio: 86.4%  
- F1 Macro: 0.85  
- Visualización de matriz de confusión  
- Modelo exportado como `model.pkl`

## 📌 Mejoras Futuras

- Incorporar embeddings (spaCy, Transformers)  
- Extender a todo el dataset (20 categorías)  
- Integrar API REST con FastAPI  
- Implementar interpretabilidad con LIME o SHAP

## 📄 Licencia

MIT License
