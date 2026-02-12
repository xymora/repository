# 🧠 Content Analysis and Classification: Netflix Insights

This project demonstrates a robust machine learning and NLP pipeline for analyzing and classifying digital content metadata. By leveraging **TF-IDF Vectorization** and **Cosine Similarity**, the system identifies patterns in titles, descriptions, and genres to build a content-based classification engine.

## 🎯 Objective
To transform raw streaming data into actionable insights by:
* **Data Governance:** Implementing strict data quality checks and handling missing values in global datasets.
* **AutoEDA & Visualization:** Generating interactive intelligence reports to understand content distribution and growth.
* **NLP Modeling:** Building a classification engine using Natural Language Processing to find hidden relationships between titles.
* **Strategic Insights:** Identifying production trends across different countries and timeframes.

## 🧠 Techniques Used
* **Natural Language Processing (NLP):** Text vectorization via `TfidfVectorizer`.
* **Mathematical Modeling:** Similarity computation using `Cosine Similarity`.
* **Data Engineering:** Feature engineering, date normalization, and categorical imputation.
* **Interactive Analytics:** Dynamic plotting with `Plotly` and `Seaborn`.

## 🛠️ Technologies
* **Python 3.x**
* **Pandas & NumPy** (Data Manipulation)
* **Scikit-Learn** (Machine Learning & NLP)
* **Plotly & Seaborn** (Advanced Visualization)
* **Jupyter Notebook**

## 📁 Project Structure
Content_Analysis_and_Classification/
├── data/
│   └── netflix_titles.csv           # Original Dataset
├── notebooks/
│   └── content_analysis_and_classification.ipynb
├── outputs/
│   └── data_quality_report.html     # (Optional) Exported report
├── requirements.txt                 # Project dependencies
└── README.md                        # Documentation
