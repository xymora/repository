# 🤝 Collaborative ML Project Simulation

This repository demonstrates a full-stack simulation of a collaborative machine learning project involving product, data science, and engineering teams. Although developed by one person, the project structure reflects the workflow and interactions of a real-world team.

## 🎯 Objective

To showcase the workflow of an ML project as if developed by a multidisciplinary team, including:

- Product requirement documentation  
- Data science development and modeling  
- Engineering integration and API deployment  
- Issues, Pull Requests, and documentation simulation  

## 🧠 Techniques Used

- EDA and preprocessing  
- Model development and evaluation  
- REST API implementation using FastAPI  
- Version control and simulated PRs and issues  

## 🛠️ Technologies

- Python 3.10  
- scikit-learn  
- pandas  
- matplotlib  
- FastAPI  
- uvicorn  

## 📁 Project Structure

collaborative-ml-project/  
├── product/  
│   └── requirements.md          # Product vision and features  
├── data_science/  
│   └── eda_modeling.py          # Data analysis and modeling code  
├── engineering/  
│   └── api.py                   # FastAPI for model serving  
└── README.md  

## 🔄 Workflow Simulation

- Issues created in GitHub to represent user stories and dev tasks  
- Branches used for each component (e.g., product-docs, model-dev, api-service)  
- Pull Requests with descriptive messages and simulated reviews  
- Clear commit messages to reflect progress and traceability  

## 🚀 Execution

1. Review `product/requirements.md`  
2. Run `data_science/eda_modeling.py` to simulate training  
3. Start API from `engineering/api.py` using FastAPI and `uvicorn`  
   ```bash
   uvicorn api:app --reload
