# 🤖 ML API Collaboration Project

This project demonstrates a realistic simulation of a machine learning API deployed with FastAPI, designed for collaboration between frontend and backend developers. The structure emulates a multidisciplinary team workflow, providing a clear, modular, and documented backend API.

## 🎯 Objective

To create a deployable RESTful API serving predictions from a trained machine learning model, accompanied by documentation and interface guidelines for a frontend team. The project emphasizes communication and modular architecture.

## 🧠 Techniques Used

- Supervised learning with RandomForestClassifier  
- FastAPI for RESTful services  
- OpenAPI/Swagger for automatic documentation  
- Pytest for endpoint testing  
- Docker for containerization  

## 🛠️ Technologies

- Python 3.9  
- scikit-learn  
- FastAPI  
- uvicorn  
- joblib  
- pandas  
- Docker  

## 📁 Project Structure

ml-api-collaboration/  
├── app/  
│   ├── api.py                # FastAPI app and endpoints  
│   ├── model.py              # Model training and loading  
│   └── schemas.py            # Pydantic data models  
├── data/  
│   └── iris.csv              # Example dataset  
├── tests/  
│   └── test_api.py           # API unit tests  
├── Dockerfile                # Docker container definition  
├── requirements.txt          # Python dependencies  
└── README.md                 # Project documentation

## 🔄 Workflow Simulation

- Issues simulate frontend requirements and backend subtasks  
- Pull requests are separated by feature (e.g., model training, API endpoint)  
- Clear commit messages documenting model integration and endpoint definitions  

## 🚀 How to Run

1. Install dependencies: `pip install -r requirements.txt`  
2. Train model: Run `train_and_save_model()` in `model.py`  
3. Start API:  
uvicorn app.api:app --reload

markdown
Copiar
Editar
4. Access docs:  
Visit `http://127.0.0.1:8000/docs` for Swagger UI  
or `http://127.0.0.1:8000/redoc` for ReDoc  

## 📊 Outputs

- `app/model.pkl`: trained ML model (saved via joblib)  
- `/predict` endpoint: receives input JSON, returns prediction  

## 📦 Docker Support

Build and run the containerized app:
docker build -t ml-api-collab .
docker run -p 8000:8000 ml-api-collab

markdown
Copiar
Editar

## 📌 Future Enhancements

- Add frontend UI consuming the API  
- Implement token-based auth for production use  
- CI/CD integration with GitHub Actions  

## 📄 License

MIT License
