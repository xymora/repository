import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
from textblob import TextBlob

# Cargar reseñas
df = pd.read_csv('sentiment_reviews.csv')

# Calcular polaridad de sentimiento
df['Polarity'] = df['ReviewText'].apply(lambda x: TextBlob(x).sentiment.polarity)
df['Sentiment'] = pd.cut(df['Polarity'], bins=[-1, -0.1, 0.1, 1], labels=['Negative', 'Neutral', 'Positive'])

# Estadísticas por sentimiento
sentiment_counts = df['Sentiment'].value_counts().sort_index()
print("Sentiment Distribution:")
print(sentiment_counts)

# Gráfica
plt.figure(figsize=(6,4))
sns.countplot(data=df, x='Sentiment', palette='Set2', order=['Negative', 'Neutral', 'Positive'])
plt.title('Sentiment Distribution from Customer Reviews')
plt.xlabel('Sentiment Category')
plt.ylabel('Review Count')
plt.tight_layout()
plt.savefig('sentiment_distribution.png')
plt.show()
