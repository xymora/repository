from fastapi import FastAPI
import joblib
import numpy as np

app = FastAPI()
model = joblib.load("model/model.pkl")

@app.get("/")
def read_root():
    return {"message": "Inference API is running"}

@app.post("/predict/")
def predict(features: list[float]):
    prediction = model.predict([features])
    return {"prediction": prediction.tolist()}