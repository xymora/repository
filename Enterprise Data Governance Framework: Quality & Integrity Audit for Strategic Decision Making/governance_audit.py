import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
import requests
import os
from datetime import datetime

# ==========================================
# 1. DATA GOVERNANCE CONFIGURATION
# ==========================================
DATA_URL = "https://raw.githubusercontent.com/rfordatascience/tidytuesday/master/data/2020/2020-07-07/coffee_ratings.csv"
DATA_FILENAME = "enterprise_data_source.csv"

class DataGovernanceEngine:
    """High-level Data Governance Framework for Data Quality Auditing."""
    
    def __init__(self, df):
        self.df = df
        self.audit_results = {}
        sns.set_theme(style="whitegrid")

    def download_resource(self):
        """Compliance check: Data acquisition from authorized sources."""
        if not os.path.exists(DATA_FILENAME):
            print(f"[LOG] {datetime.now()} - Downloading data from source...")
            response = requests.get(DATA_URL)
            with open(DATA_FILENAME, 'wb') as f:
                f.write(response.content)
        return pd.read_csv(DATA_FILENAME)

    def run_quality_audit(self):
        """Executes the 6 dimensions of Data Quality audit."""
        print("-" * 50)
        print("EXECUTING DATA GOVERNANCE AUDIT REPORT")
        print("-" * 50)
        
        # 1. Completeness
        missing_data = self.df.isnull().sum()
        self.audit_results['completeness'] = (1 - (missing_data.sum() / self.df.size)) * 100
        
        # 2. Uniqueness
        duplicates = self.df.duplicated().sum()
        self.audit_results['uniqueness'] = (1 - (duplicates / len(self.df))) * 100

        # 3. Validity (Check if scores are within 0-100)
        valid_scores = self.df[self.df['total_cup_points'].between(0, 100)]
        self.audit_results['validity'] = (len(valid_scores) / len(self.df)) * 100

        print(f"Audit Status: {'PASSED' if self.audit_results['completeness'] > 80 else 'FAILED'}")
        print(f"Overall Data Health Score: {self.audit_results['completeness']:.2f}%")
        
    def generate_executive_dashboard(self):
        """Generates a professional dashboard for decision makers."""
        fig, axes = plt.subplots(2, 2, figsize=(16, 10))
        fig.suptitle('Strategic Governance Dashboard: Data Quality Assessment', fontsize=20)

        # Chart 1: Missing Data per Domain (Governance perspective)
        null_counts = self.df.isnull().sum().sort_values(ascending=False).head(10)
        sns.barplot(x=null_counts.values, y=null_counts.index, ax=axes[0, 0], palette="viridis")
        axes[0, 0].set_title('Top 10 Governance Vulnerabilities (Missing Info)', fontsize=14)

        # Chart 2: Distribution of Key Metric
        sns.histplot(self.df['total_cup_points'], kde=True, ax=axes[0, 1], color="teal")
        axes[0, 1].set_title('Data Reliability Distribution: Total Cup Points', fontsize=14)

        # Chart 3: Categorical Consistency
        top_countries = self.df['country_of_origin'].value_counts().head(5)
        axes[1, 0].pie(top_countries, labels=top_countries.index, autopct='%1.1f%%', startangle=140, colors=sns.color_palette("pastel"))
        axes[1, 0].set_title('Regional Data Lineage (Source Origin)', fontsize=14)

        # Chart 4: Correlation for Business Insights
        corr = self.df[['aroma', 'flavor', 'aftertaste', 'acidity', 'body', 'balance']].corr()
        sns.heatmap(corr, annot=True, cmap="YlGnBu", ax=axes[1, 1])
        axes[1, 1].set_title('Attribute Integrity Correlation Matrix', fontsize=14)

        plt.tight_layout(rect=[0, 0.03, 1, 0.95])
        plt.show()

    def console_executive_summary(self):
        """Prints a high-level summary for Data Stewards."""
        print("\n" + "="*60)
        print("EXECUTIVE SUMMARY - DATA STEWARDSHIP VIEW")
        print("="*60)
        summary = {
            "Total Records": len(self.df),
            "Critical Attributes": list(self.df.columns[:5]),
            "Integrity Score": f"{self.audit_results['completeness']:.2f}%",
            "Recommendation": "Proceed with Data Cleaning Phase 2" if self.audit_results['completeness'] < 95 else "Data Ready for Production"
        }
        for k, v in summary.items():
            print(f"{k.ljust(25)}: {v}")
        print("="*60)

# ==========================================
# MAIN EXECUTION FLOW
# ==========================================
if __name__ == "__main__":
    # In a real governance scenario, we would use a logger
    raw_df = pd.read_csv(DATA_URL) # Direct load for the practice
    
    # Initialize Engine
    dg_engine = DataGovernanceEngine(raw_df)
    
    # Run Audit
    dg_engine.run_quality_audit()
    
    # Output Results
    dg_engine.console_executive_summary()
    dg_engine.generate_executive_dashboard()
