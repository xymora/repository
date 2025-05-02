# 🧬 Molecular Modeling Tool for Gene-Editing Therapy Simulation

This project implements a molecular modeling system that simulates gene-editing therapies based on immune resistance pathways. It integrates gene expression profiling with mutation targets to assess predicted effects of CRISPR-based editing strategies.

## 🎯 Objective

To simulate and evaluate gene-editing therapies by combining gene expression data with editing predictions across immune-related pathways, enabling strategic planning for immunotherapy design.

## 🧠 Techniques Used

- Integration of expression and mutation datasets
- Statistical aggregation by edit type and immune condition
- Visualization of editing effects and immune response shifts
- Prediction impact classification on resistance and activation

## 🛠️ Technologies

- Python 3.x
- pandas
- seaborn
- matplotlib

## 📁 Project Structure

molecular-modeling-tool/
├── immuno_gene_expression.csv          # Simulated expression levels under immune states  
├── gene_edit_predictions.csv           # Gene-editing predictions and expected immune pathway effects  
├── molecular_modeling_tool.py          # Full simulation and visualization script  
├── edit_expression_heatmap.png         # Heatmap of mean expression by condition and edit type  
├── edit_effects_distribution.png       # Bar chart of predicted edit outcomes per pathway  
└── README.md                           # Complete project documentation and analysis pipeline

## 🚀 Pipeline

1. Load gene expression data under baseline, activated, and suppressed immune states  
2. Load gene-editing predictions including CRISPR type and immune pathway targeting  
3. Merge datasets and group by edit type and condition to summarize effects  
4. Visualize aggregated results as a heatmap of expression and bar chart of predicted outcomes

## 📊 Outputs

- `edit_expression_heatmap.png`: average expression under each edit strategy  
- `edit_effects_distribution.png`: predicted effect frequency by pathway  
- Printed matrix summarizing expression trends by condition and intervention

## 📌 Future Enhancements

- Add real CRISPR edit data integration from clinical trials  
- Incorporate pathway enrichment analysis and mutation mapping  
- Extend to protein-protein interaction models and phenotype prediction
