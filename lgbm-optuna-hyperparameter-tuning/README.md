# 🎯 Hyperparameter Tuning with Optuna for LightGBM Models

This project focuses on hyperparameter optimization for a LightGBM classification model using [Optuna](https://optuna.org/). It includes training a baseline model, tuning with Optuna, evaluating performance, and visualizing hyperparameter importance. Results are presented in a professional Jupyter Notebook ready for technical portfolios.

## 🧠 Objective

Optimize the performance of a LightGBM classifier by using Optuna for hyperparameter search, evaluating the tuned model against a baseline, and visualizing key outcomes.

## 🔍 Techniques Used

- LightGBM model training and evaluation  
- Optuna hyperparameter search with cross-validation  
- Feature importance and tuning parameter visualization  
- Baseline model comparison for metrics validation  

## 🛠️ Technologies

- Python 3.x  
- LightGBM  
- Optuna  
- Scikit-learn  
- Pandas  
- Matplotlib  

## 📁 Project Structure

lgbm-optuna-hyperparameter-tuning/  
├── data/  
│   └── training_data.csv                  # Simulated tabular dataset for classification  
├── notebooks/  
│   └── lgbm_optuna_tuning.ipynb           # Complete tuning and evaluation notebook  
├── outputs/  
│   ├── optuna_importance_plot.png         # Visualization of hyperparameter importance  
│   ├── base_model_metrics.json            # Metrics for baseline model  
│   └── tuned_model_metrics.json           # Metrics for tuned model  
├── requirements.txt                       # Project dependencies  
└── README.md                              # Full documentation

## 🚀 Pipeline

1. Load and preprocess training data  
2. Train a baseline LightGBM model using default parameters  
3. Perform hyperparameter tuning using Optuna with cross-validation  
4. Evaluate tuned model against baseline (accuracy, F1-score, etc.)  
5. Visualize parameter importance with Optuna's plotting tools  
6. Export best metrics and tuning results  

## 📊 Outputs

- `optuna_importance_plot.png`: key hyperparameter influence  
- `base_model_metrics.json`: accuracy and F1 of untuned model  
- `tuned_model_metrics.json`: accuracy and F1 after tuning  
- `lgbm_optuna_tuning.ipynb`: clean notebook with charts and interpretations  

## 📌 Future Enhancements

- Extend to regression tasks with RMSE metrics  
- Deploy as an automated ML tuning pipeline  
- Incorporate Bayesian optimization for broader model support  

## 📄 License

This project is licensed under the MIT License.
