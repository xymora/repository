from fastapi import FastAPI
from pydantic import BaseModel
import numpy as np
from .model import load_model

app = FastAPI(title="ML Model API", description="A FastAPI-based ML model serving API.", version="1.0")

model = load_model()

class IrisRequest(BaseModel):
    sepal_length: float
    sepal_width: float
    petal_length: float
    petal_width: float

@app.post("/predict")
def predict(data: IrisRequest):
    features = np.array([[data.sepal_length, data.sepal_width, data.petal_length, data.petal_width]])
    prediction = model.predict(features)
    return {"prediction": int(prediction[0])}