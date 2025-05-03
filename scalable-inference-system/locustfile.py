from locust import HttpUser, task

class InferenceUser(HttpUser):
    @task
    def predict(self):
        self.client.post("/predict/", json={"features": [5.1, 3.5, 1.4, 0.2]})