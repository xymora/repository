import joblib
import pandas as pd
from sklearn.datasets import load_iris
from sklearn.ensemble import RandomForestClassifier

def train_and_save_model():
    iris = load_iris()
    X, y = iris.data, iris.target
    model = RandomForestClassifier()
    model.fit(X, y)
    joblib.dump(model, "app/model.pkl")

def load_model():
    return joblib.load("app/model.pkl")