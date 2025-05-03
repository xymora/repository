FROM tiangolo/uvicorn-gunicorn-fastapi:python3.9
COPY ./app /app
COPY ./model /app/model
RUN pip install joblib scikit-learn numpy fastapi