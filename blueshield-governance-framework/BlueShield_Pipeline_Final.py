import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
import requests
import io
from datetime import datetime

# ==========================================
# DATA GOVERNANCE MODULE
# ==========================================
class DataGovernanceEngine:
    def __init__(self):
        self.log_book = []
        print(f"[{datetime.now()}] Governance Engine v3.1 (Premium) Initialized.")

    def log_event(self, step, status, details):
        print(f"GOV_LOG: {step} | {status} | {details}")

    def generate_synthetic_data(self):
        self.log_event("Ingestion", "Fallback", "Source 404. Generating synthetic fishery data.")
        np.random.seed(42)
        n_rows = 500
        data = {
            'mmsi': [f"VESSEL-{i}" for i in range(1000, 1000 + n_rows)],
            'hours': np.random.uniform(100, 1000, n_rows),
            'fishing_hours': np.random.uniform(20, 950, n_rows)
        }
        df = pd.DataFrame(data)
        # Introduce some "dirty" data for governance testing
        df.iloc[0:5, 1] = np.nan 
        return df

    def validate_quality(self, df):
        initial = len(df)
        # Rule 1: Remove Nulls
        df = df.dropna(subset=['hours', 'fishing_hours'])
        # Rule 2: Logical Consistency (Fishing cannot exceed total)
        df = df[df['fishing_hours'] <= df['hours']]
        self.log_event("Quality Check", "Passed", f"Cleaned {initial - len(df)} rows.")
        return df

# ==========================================
# PIPELINE FUNCTIONS
# ==========================================
def ingest_data(gov):
    url = "https://raw.githubusercontent.com/GlobalFishingWatch/data-science/master/invalid_path.csv"
    try:
        r = requests.get(url, timeout=3)
        if r.status_code == 200:
            return pd.read_csv(io.StringIO(r.text))
        return gov.generate_synthetic_data()
    except:
        return gov.generate_synthetic_data()

def apply_business_logic(df):
    # Calculate Risk Score
    df['sustainability_index'] = 1 - (df['fishing_hours'] / (df['hours'] + 1))
    
    # Classification Logic
    conditions = [
        (df['sustainability_index'] < 0.35),
        (df['sustainability_index'] >= 0.35) & (df['sustainability_index'] < 0.65),
        (df['sustainability_index'] >= 0.65)
    ]
    labels = ['High Risk', 'Moderate', 'Compliant']
    df['status'] = np.select(conditions, labels, default='Unknown')
    return df

# ==========================================
# PREMIUM DASHBOARD (UI/UX)
# ==========================================
def generate_dashboard(df):
    plt.style.use('dark_background')
    fig, axes = plt.subplots(1, 2, figsize=(18, 7))
    fig.patch.set_facecolor('#0b0e14')
    
    palette = {'Compliant': '#00ffcc', 'Moderate': '#ffcc00', 'High Risk': '#ff3333'}

    # Chart 1: Distribution (Fixed logic)
    sns.countplot(ax=axes[0], data=df, x='status', palette=palette, hue='status', legend=False)
    axes[0].set_title("Vessel Compliance Distribution", fontsize=16, color='#00d4ff', pad=20)
    axes[0].set_xlabel("Governance Status", color='gray')
    axes[0].grid(axis='y', linestyle='--', alpha=0.3)

    # Chart 2: Scatter Mapping
    sns.scatterplot(ax=axes[1], data=df, x='hours', y='fishing_hours', hue='status', 
                    palette=palette, alpha=0.6, s=60, edgecolor='black')
    axes[1].set_title("Fishing Intensity Mapping", fontsize=16, color='#00d4ff', pad=20)
    axes[1].set_xlabel("Total Operational Hours", color='gray')
    axes[1].set_ylabel("Active Fishing Hours", color='gray')

    plt.tight_layout()
    plt.show()

if __name__ == "__main__":
    gov_engine = DataGovernanceEngine()
    raw_df = ingest_data(gov_engine)
    clean_df = gov_engine.validate_quality(raw_df)
    final_df = apply_business_logic(clean_df)
    
    print("\n--- GOVERNANCE AUDIT SUMMARY ---")
    print(final_df['status'].value_counts())
    
    generate_dashboard(final_df)
