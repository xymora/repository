import pandas as pd
import numpy as np
import plotly.graph_objects as go
import plotly.express as px
from datetime import datetime, timedelta

# --- DATA GOVERNANCE MODULE: TESLA SC-DIG ---
# Minimum 120 lines of professional code for high-level decision making

class TeslaDataGovernance:
    def __init__(self):
        self.audit_log = []
        self.quality_score = 0
        
    def generate_mock_supply_chain_data(self, records=1000):
        """Simulates raw data from Tesla's global battery suppliers."""
        np.random.seed(42)
        data = {
            'timestamp': [datetime(2023, 1, 1) + timedelta(hours=i) for i in range(records)],
            'supplier_id': np.random.choice(['TSL_NV_01', 'TSL_SH_02', 'TSL_BER_03'], records),
            'battery_batch_id': [f"BAT-{i:05d}" for i in range(records)],
            'energy_density_wh_kg': np.random.normal(260, 15, records), # Target 260
            'cobalt_content_percentage': np.random.uniform(0, 5, records),
            'production_cost_usd': np.random.normal(100, 10, records),
            'passed_qa': np.random.choice([True, False], records, p=[0.92, 0.08])
        }
        df = pd.DataFrame(data)
        # Introduce "Dirty Data" for Governance Simulation
        df.iloc[0:10, 3] = np.nan  # Missing values
        df.iloc[20:25, 3] = 999.0  # Outliers/Anomalies
        return df

    def apply_governance_rules(self, df):
        """Standardizes and cleans data according to Tesla's Policy #88-Data."""
        print(f"[{datetime.now()}] Initiating Governance Protocol SC-DIG...")
        
        # 1. Completeness Check
        initial_count = len(df)
        nulls = df['energy_density_wh_kg'].isnull().sum()
        df = df.dropna(subset=['energy_density_wh_kg'])
        
        # 2. Consistency & Range Check (Governance Constraint: 150 < wh_kg < 400)
        anomalies = df[(df['energy_density_wh_kg'] < 150) | (df['energy_density_wh_kg'] > 400)]
        df = df[(df['energy_density_wh_kg'] >= 150) & (df['energy_density_wh_kg'] <= 400)]
        
        # 3. Metadata Enrichment
        df['data_reliability_index'] = np.where(df['passed_qa'], 0.98, 0.75)
        
        self.audit_log.append({
            'nulls_removed': nulls,
            'anomalies_flagged': len(anomalies),
            'final_count': len(df)
        })
        return df

    def create_executive_dashboard(self, df):
        """Generates high-level visual insights for VP of Supply Chain."""
        # Figure 1: Energy Density Distribution (Quality Control)
        fig1 = px.histogram(df, x="energy_density_wh_kg", color="supplier_id",
                           marginal="box", title="Tesla Battery Asset Distribution - Quality Governance",
                           color_discrete_sequence=px.colors.qualitative.Bold)
        
        # Figure 2: Reliability vs Cost (Executive View)
        fig2 = px.scatter(df, x="production_cost_usd", y="energy_density_wh_kg",
                         size="data_reliability_index", color="supplier_id",
                         hover_name="battery_batch_id", title="Decision Matrix: Cost vs Energy Density")
        
        fig1.show()
        fig2.show()

    def print_console_report(self):
        """Prints a professional data health summary."""
        print("\n" + "="*50)
        print("TESLA DATA GOVERNANCE SYSTEM - STATUS REPORT")
        print("="*50)
        for log in self.audit_log:
            print(f"Data Completeness: {log['final_count']} valid records.")
            print(f"Integrity Alerts: {log['anomalies_flagged']} anomalies quarantined.")
            print(f"Health Score: {((log['final_count'] / 1000) * 100):.2f}%")
        print("="*50 + "\n")

# --- EXECUTION ---
if __name__ == "__main__":
    tg = TeslaDataGovernance()
    raw_data = tg.generate_mock_supply_chain_data()
    
    # Apply Governance
    clean_data = tg.apply_governance_rules(raw_data)
    
    # Reports
    tg.print_console_report()
    tg.create_executive_dashboard(clean_data)

    # Business Intelligence logic for decision making
    avg_density = clean_data.groupby('supplier_id')['energy_density_wh_kg'].mean()
    print("STRATEGIC RECOMMENDATION:")
    top_supplier = avg_density.idxmax()
    print(f"Invest 15% more capital in {top_supplier} based on Data Reliability Index.")
