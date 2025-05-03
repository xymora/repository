import pandas as pd
import pickle
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import train_test_split

def train_model():
    data = pd.read_csv('data/iris.csv')
    X = data.drop('target', axis=1)
    y = data['target']
    model = LogisticRegression(max_iter=200)
    model.fit(X, y)
    with open('model.pkl', 'wb') as f:
        pickle.dump(model, f)

def predict(features):
    with open('model.pkl', 'rb') as f:
        model = pickle.load(f)
    df = pd.DataFrame([features])
    return model.predict(df)[0]