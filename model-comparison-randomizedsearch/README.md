# 🔍 Model Comparison with RandomizedSearchCV

This project compares the performance of three popular classification algorithms—Logistic Regression, Random Forest, and XGBoost—using RandomizedSearchCV for hyperparameter tuning. It includes cross-validation, overfitting/underfitting diagnostics, and visualizations of model performance.

## 🎯 Objective

To identify the most suitable classification model through systematic comparison, tuning, and validation, using a real-world dataset and modern machine learning techniques.

## 🧠 Techniques Used

- Logistic Regression  
- Random Forest  
- XGBoost  
- Hyperparameter tuning with RandomizedSearchCV  
- K-Fold Cross Validation (k=5)  
- Confusion Matrix  
- Accuracy, Precision, Recall, F1-Score  
- Overfitting/underfitting analysis  

## 🛠️ Technologies

- Python 3.10  
- scikit-learn  
- xgboost  
- pandas, numpy  
- matplotlib, seaborn  

## 📁 Project Structure

model-comparison-randomizedsearch/  
├── data/  
│   └── breast_cancer.csv                   # Dataset used for training and validation  
├── outputs/  
│   ├── best_params.csv                     # Optimal hyperparameters for each model  
│   └── confusion_matrix_comparison.png     # Visual comparison of confusion matrices  
├── model_comparison_randomizedsearch.ipynb # Full notebook with training and evaluation  
└── README.md                               # Documentation and technical overview

## 🚀 Pipeline

1. Load and explore the dataset  
2. Preprocess the data (encoding, scaling)  
3. Define hyperparameter grids for each model  
4. Apply RandomizedSearchCV for tuning  
5. Evaluate models with cross-validation  
6. Visualize performance comparison  
7. Summarize optimal parameters and recommendations  

## 📊 Outputs

- `best_params.csv`: Contains the best hyperparameter combination found per model  
- `confusion_matrix_comparison.png`: Visual overview of model performance  
- Classification report printed in notebook for all models  

## 📌 Future Enhancements

- Include LightGBM and SVM in the comparison  
- Automate ML workflow with pipelines  
- Export the best model as a deployable .pkl or ONNX  

## 📄 License

This project is licensed under the MIT License.
