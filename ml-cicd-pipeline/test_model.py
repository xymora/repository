from app.model import predict

def test_prediction():
    sample = {"sepal_length": 5.1, "sepal_width": 3.5, "petal_length": 1.4, "petal_width": 0.2}
    result = predict(sample)
    assert result in [0, 1, 2]