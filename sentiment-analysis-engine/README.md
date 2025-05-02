# 💬 Sentiment Analysis Engine for Customer Reviews

This project implements a sentiment analysis system applied to customer reviews in order to assess product perception and support inventory and marketing strategies.

## 🎯 Objective

To automatically classify customer reviews as positive, neutral, or negative based on their textual content, and to provide insights into overall sentiment trends for each product.

## 🧠 Techniques Used

- Polarity analysis with TextBlob
- Categorical classification of sentiment
- Text preprocessing via rule-based polarity scoring
- Visualization of sentiment distribution

## 🛠️ Technologies

- Python 3.x
- pandas, matplotlib, seaborn
- TextBlob (Natural Language Processing)

## 📁 Project Structure

sentiment-analysis-engine/
├── sentiment_reviews.csv             # Simulated review dataset with rating and text  
├── sentiment_analysis_engine.py      # Script to compute and visualize sentiment  
├── sentiment_distribution.png        # Graph showing counts by sentiment class  
└── README.md                         # Project overview and methodology

## 🚀 Pipeline

1. Load customer review dataset  
2. Use TextBlob to calculate sentiment polarity  
3. Map polarity into categories: Positive, Neutral, Negative  
4. Count sentiment frequency and visualize  
5. Use output to inform product management and marketing

## 📊 Outputs

- Printed summary of sentiment class distribution  
- `sentiment_distribution.png`: visual overview of review polarity

## 📌 Future Enhancements

- Add aspect-based sentiment analysis  
- Use transformer models (e.g. BERT) for fine-tuned sentiment classification  
- Correlate sentiment trends with product return rates or stock decisions
