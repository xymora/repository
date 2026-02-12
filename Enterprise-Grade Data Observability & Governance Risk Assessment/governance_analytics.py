import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
from scipy import stats
import datetime
import sys

# UI/UX Style Configuration for Reports
sns.set_theme(style="whitegrid", palette="tab10")
plt.rcParams['font.family'] = 'sans-serif'
plt.rcParams['figure.titlesize'] = 18

class DataGovernanceSentinel:
    """
    Advanced Governance Engine for Quality Observability and 
    Risk-Based Decision Support.
    """
    
    def __init__(self, system_id="ERP_CORE_GLOBAL"):
        self.system_id = system_id
        self.audit_trail = []
        self.report_timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    def _log(self, action, status="INFO"):
        self.audit_trail.append(f"[{datetime.datetime.now().isoformat()}] {status}: {action}")

    def ingest_data(self, records=1200):
        """Simulates ingestion of high-volume financial data with governance anomalies."""
        self._log("Initiating data ingestion from source...")
        np.random.seed(42)
        
        data = {
            'timestamp': pd.date_range(start='2024-01-01', periods=records, freq='H'),
            'transaction_id': [f"TX-{i:05d}" for i in range(records)],
            'entity_code': np.random.choice(['NA', 'EU', 'APAC', 'LATAM', None], records, p=[0.4, 0.3, 0.15, 0.1, 0.05]),
            'operating_margin': np.random.normal(25000, 7000, records),
            'risk_index': np.random.uniform(0.1, 0.9, records),
            'processing_latency': np.random.gamma(2, 2, records)
        }
        
        df = pd.DataFrame(data)
        
        # Injecting 'Poisoned Data' for Governance Testing
        # 1. Outliers (Financial Risk)
        df.loc[np.random.choice(df.index, 25), 'operating_margin'] *= 8 
        # 2. Integrity Violations (Duplicates)
        df.loc[10:20, 'transaction_id'] = "TX-00010" 
        
        self._log(f"Successfully ingested {records} records.")
        return df

    def run_diagnostic(self, df):
        """Statistical diagnostic to determine dataset health."""
        self._log("Running Statistical Governance Diagnostic...")
        
        # Logic 1: Uniqueness Analysis
        dup_count = df.duplicated(subset=['transaction_id']).sum()
        
        # Logic 2: Outlier Detection (Z-Score > 3)
        z_scores = np.abs(stats.zscore(df['operating_margin']))
        outliers = (z_scores > 3).sum()
        
        # Logic 3: Null Ratio
        null_ratio = df['entity_code'].isnull().mean()
        
        return {
            "duplicates": dup_count,
            "outliers": outliers,
            "null_ratio": null_ratio,
            "avg_margin": df['operating_margin'].mean()
        }

    def generate_decision_dashboard(self, df, metrics):
        """Premium UX/UI Dashboard for Executive Stakeholders."""
        self._log("Rendering visual observability dashboard...")
        
        fig, axes = plt.subplots(2, 2, figsize=(16, 10))
        plt.subplots_adjust(hspace=0.4)

        # 1. Distribution & Outlier Visual
        sns.boxplot(x=df['operating_margin'], ax=axes[0, 0], color='#4e79a7')
        axes[0, 0].set_title('Financial Anomaly Detection (Operating Margin)', fontweight='bold')

        # 2. Completeness Analysis
        sns.countplot(data=df.fillna('MISSING'), x='entity_code', ax=axes[0, 1], palette='magma')
        axes[0, 1].set_title('Entity Distribution & Missing Data Logs', fontweight='bold')

        # 3. Time-Series Drift
        sns.lineplot(data=df, x='timestamp', y='operating_margin', ax=axes[1, 0], alpha=0.6)
        axes[1, 0].set_title('Temporal Data Stability (Drift Analysis)', fontweight='bold')

        # 4. Heatmap of Risk (Correlation)
        sns.heatmap(df.corr(), annot=True, cmap='RdYlGn', ax=axes[1, 1])
        axes[1, 1].set_title('Attribute Correlation Matrix', fontweight='bold')

        plt.suptitle(f"DATA GOVERNANCE OBSERVABILITY REPORT - {self.system_id}\nIssued: {self.report_timestamp}", fontsize=18)
        plt.show()

    def print_executive_summary(self, metrics):
        """Professional console output for decision making."""
        border = "═" * 70
        print(f"\n{border}")
        print(f"📊 GOVERNANCE EXECUTIVE SUMMARY | ID: {self.system_id}".center(70))
        print(f"{border}")
        
        # Scoring Logic
        critical_alert = False
        print(f"● DATA INTEGRITY : {'FAIL' if metrics['duplicates'] > 0 else 'PASS'}")
        print(f"  - Duplicate Records: {metrics['duplicates']}")
        
        print(f"● DATA QUALITY   : {'FAIL' if metrics['null_ratio'] > 0.03 else 'PASS'}")
        print(f"  - Null Ratio      : {metrics['null_ratio']:.2%}")
        
        print(f"● RISK ASSESSMENT : {'WARNING' if metrics['outliers'] > 10 else 'STABLE'}")
        print(f"  - Outlier Count   : {metrics['outliers']}")
        
        print("-" * 70)
        
        if metrics['duplicates'] > 0 or metrics['null_ratio'] > 0.05:
            print("🛑 STRATEGIC DECISION: [REJECTED] - DO NOT COMMINGLE WITH PRODUCTION DATA")
            self._log("Governance Decision: REJECTED", "CRITICAL")
        else:
            print("✅ STRATEGIC DECISION: [APPROVED] - DATA READY FOR DOWNSTREAM CONSUMPTION")
            self._log("Governance Decision: APPROVED", "SUCCESS")
        
        print(f"{border}\n")

if __name__ == "__main__":
    sentinel = DataGovernanceSentinel()
    raw_data = sentinel.ingest_data()
    results = sentinel.run_diagnostic(raw_data)
    sentinel.generate_decision_dashboard(raw_data, results)
    sentinel.print_executive_summary(results)
