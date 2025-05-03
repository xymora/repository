# 🧠 Classification API with FastAPI and Docker

This project implements a complete machine learning classification pipeline using Python and scikit-learn, and deploys it as a REST API using FastAPI. The API includes endpoints for predictions, health checks, and auto-generated documentation via Swagger UI. The application is containerized with Docker for easy deployment and scalability.

## 🎯 Objective

To train a classification model (RandomForestClassifier) and expose it through a production-ready RESTful API for real-time inference.

## 🧠 Techniques Used

- Model training with scikit-learn
- Data preprocessing and serialization
- REST API development with FastAPI
- Model serving with Pydantic and Uvicorn
- Docker-based deployment

## 🛠️ Technologies

- Python 3.x
- scikit-learn
- pandas, NumPy
- FastAPI, Uvicorn
- Pydantic
- Docker

## 📁 Project Structure

classification-api-fastapi/  
├── data.csv                   # Dataset used to train the classifier  
├── train_model.py            # Script to train and serialize the classifier  
├── model.pkl                 # Trained model serialized with joblib  
├── main.py                   # FastAPI app exposing prediction and health endpoints  
├── Dockerfile                # Docker configuration for containerization  
├── requirements.txt          # Python dependencies  
└── README.md                 # Documentation and setup guide

## 🚀 Pipeline

1. Train a classification model with a labeled dataset  
2. Save the model using joblib  
3. Create a FastAPI app to expose:
   - `/predict`: accepts JSON input for prediction
   - `/health`: health check endpoint
   - `/docs`: Swagger API documentation
4. Containerize the app using Docker  
5. Run it locally or deploy it to cloud services

## 📊 Outputs

- RESTful API with prediction capabilities
- Interactive Swagger UI (`/docs`)
- JSON responses with class prediction and probabilities

## 🐳 Docker Instructions

Build and run locally:

```bash
docker build -t classification-api .
docker run -d -p 8000:8000 classification-api
