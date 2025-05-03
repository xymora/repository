from fastapi import FastAPI
from app.model import predict

app = FastAPI()

@app.get("/")
def read_root():
    return {"message": "API is running"}

@app.post("/predict")
def make_prediction(features: dict):
    return {"prediction": predict(features)}