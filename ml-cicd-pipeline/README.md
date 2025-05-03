# 🚀 ML CI/CD Pipeline with GitHub Actions, Docker & FastAPI

This project demonstrates a complete CI/CD pipeline for a machine learning model using GitHub Actions. It includes model training, unit testing, code linting, containerization with Docker, and automated deployment of a FastAPI application. The pipeline ensures that every code change is tested, validated, and deployed seamlessly.

## 🎯 Objective

To automate the end-to-end process of developing, testing, and deploying a machine learning model using modern DevOps practices.

## 🧠 Techniques Used

- **Modeling**: Logistic Regression with scikit-learn  
- **API Development**: FastAPI  
- **CI/CD**: GitHub Actions  
- **Containerization**: Docker  
- **Testing**: pytest  
- **Code Quality**: flake8  

## 🛠️ Technologies

- Python 3.9  
- scikit-learn  
- FastAPI  
- Docker  
- GitHub Actions  
- pytest  
- flake8  

## 📁 Project Structure

ml-cicd-pipeline/  
├── app/  
│   ├── main.py  
│   ├── model.py  
│   └── __init__.py  
├── data/  
│   └── iris.csv  
├── tests/  
│   └── test_model.py  
├── .github/  
│   └── workflows/  
│       └── ci-cd.yml  
├── Dockerfile  
├── requirements.txt  
├── .flake8  
├── .gitignore  
└── README.md  

## 🚀 Pipeline Overview

1. **Code Push**: Developer pushes code to GitHub repository  
2. **CI/CD Trigger**: GitHub Actions workflow is triggered  
3. **Linting**: flake8 checks code style  
4. **Testing**: pytest runs unit tests  
5. **Build**: Docker image is built  
6. **Deploy**: Docker container is deployed (e.g., to Docker Hub or cloud service)  

## 📊 Outputs

- Trained Logistic Regression model saved as `model.pkl`  
- Docker image containing the FastAPI application  
- Automated deployment of the API upon successful CI/CD pipeline execution  

## 📌 Future Enhancements

- Implement model versioning  
- Integrate with cloud services like AWS or GCP for deployment  
- Add monitoring and logging for the deployed API  

## 📄 License

This project is licensed under the MIT License.
