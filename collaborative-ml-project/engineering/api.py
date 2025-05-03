from fastapi import FastAPI
from pydantic import BaseModel

app = FastAPI()

class InputData(BaseModel):
    feature1: int
    feature2: int

@app.get("/")
def read_root():
    return {"message": "Welcome to the ML API"}

@app.post("/predict")
def predict(data: InputData):
    # Mocked response
    return {"prediction": 1 if data.feature1 + data.feature2 > 150 else 0}
