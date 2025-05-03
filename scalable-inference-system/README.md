# ⚙️ Scalable Inference System with FastAPI, Docker, and Load Testing

This project builds a scalable machine learning inference system using FastAPI, Docker, and Docker Compose. It supports concurrent requests through service replication and includes basic load testing with Locust. The system is ideal for serving pre-trained ML models in production environments with minimal latency and scalable performance.

## 🎯 Objective

To simulate a production-ready ML inference setup that supports multiple replicas, concurrent requests, load testing, and containerized deployment.

## 🧠 Techniques Used

- FastAPI for serving model predictions
- Docker & Docker Compose for containerization and orchestration
- Replicated deployment to handle concurrent load
- Locust for HTTP load testing
- Joblib for loading a trained logistic regression model
- Scikit-learn for initial model training (Iris dataset)

## 🛠️ Technologies

- Python 3.9
- FastAPI
- Docker & Docker Compose
- scikit-learn
- joblib
- Locust (for testing)

## 📁 Project Structure

scalable-inference-system/
├── app/
│   └── main.py                        # FastAPI API with /predict endpoint
├── model/
│   └── model.pkl                      # Trained Logistic Regression model (Iris)
├── load_test/
│   └── locustfile.py                 # Load testing script
├── Dockerfile                         # Defines build instructions for API container
├── docker-compose.yml                # Deploys multiple replicas and test setup
├── requirements.txt                  # Python dependencies
├── .gitignore                        # Files ignored in version control
└── README.md                         # Full project documentation

## 🚀 Pipeline Overview

1. Train and export a logistic regression model with scikit-learn  
2. Serve predictions via FastAPI in `main.py`  
3. Build the Docker image  
4. Use Docker Compose to deploy 3 replicas and optional Locust  
5. Simulate traffic and monitor performance from multiple endpoints

## 📊 Outputs

- Trained `model.pkl` for serving predictions  
- `/predict/` endpoint accepting JSON `{"features": [...]}`  
- Load test report via Locust dashboard (http://localhost:8089)  
- Fully containerized and horizontally scalable system  

## 📌 Future Enhancements

- Add monitoring with Prometheus + Grafana  
- Integrate with cloud-based load balancers (e.g. AWS ELB)  
- Apply autoscaling rules based on system metrics

## 📄 License

MIT License
