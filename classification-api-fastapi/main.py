from fastapi import FastAPI
from pydantic import BaseModel
import joblib
import numpy as np

class InputData(BaseModel):
    feature1: float
    feature2: float
    feature3: float

app = FastAPI()
model = joblib.load("model.joblib")

@app.get("/")
def read_root():
    return {"message": "Classification API is running."}

@app.post("/predict")
def predict(data: InputData):
    input_data = np.array([[data.feature1, data.feature2, data.feature3]])
    prediction = model.predict(input_data)
    return {"prediction": int(prediction[0])}