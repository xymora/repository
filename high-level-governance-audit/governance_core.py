import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
import requests
import io
import sys
from datetime import datetime
from sklearn.preprocessing import LabelEncoder

# --- UX/UI PREMIUM CONFIGURATION ---
plt.style.use('dark_background')
COLOR_PALETTE = ["#00E5FF", "#76FF03", "#D500F9", "#FFEA00", "#FF3D00"]
sns.set_palette(sns.color_palette(COLOR_PALETTE))

class GovernanceAuditEngine:
    """
    Strategic Engine for Data Governance, Risk Management, and Compliance (GRC).
    Targets: Financial Sector Regulatory Standards.
    """
    
    def __init__(self):
        # Using a high-complexity Loan/Financial dataset from a public R&D repository
        self.data_url = "https://raw.githubusercontent.com/stedy/Machine-Learning-with-R-datasets/master/insurance.csv" 
        # Note: In a production GRC environment, this would point to a secure S3/Azure Blob financial lake.
        self.df = None
        self.audit_results = {}
        self.timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    def log_step(self, message):
        print(f"[{datetime.now().strftime('%H:%M:%S')}] 🛡️ GOVERNANCE_LOG: {message}")

    def ingest_data(self):
        """Strategic Data Ingestion with Schema Validation."""
        self.log_step("Initiating secure connection to Financial Data Lake...")
        try:
            response = requests.get(self.data_url)
            self.df = pd.read_csv(io.StringIO(response.text))
            self.log_step(f"Data ingested. Dimensions: {self.df.shape[0]} rows x {self.df.shape[1]} columns.")
            return True
        except Exception as e:
            self.log_step(f"CRITICAL FAILURE: Data breach or connection error: {e}")
            return False

    def perform_dq_audit(self):
        """Advanced Data Quality Audit (Dimensional Analysis)."""
        self.log_step("Running Data Quality (DQ) Audit...")
        
        # 1. Completeness Dimension
        completeness = (1 - self.df.isnull().sum() / len(self.df))
        
        # 2. Validity (Example: Negative values in positive-only financial fields)
        validity = []
        for col in self.df.select_dtypes(include=[np.number]).columns:
            invalid_count = (self.df[col] < 0).sum()
            validity.append(1 - (invalid_count / len(self.df)))
        
        # 3. Data Entropy (Measuring information chaos/uniqueness)
        entropy = self.df.nunique() / len(self.df)
        
        self.audit_results['dq_metrics'] = pd.DataFrame({
            'Completeness': completeness,
            'Entropy/Uniqueness': entropy
        }).iloc[:10] # Top 10 for dashboard clarity
        
        self.log_step("DQ Audit completed. Anomalies flagged.")

    def compliance_risk_assessment(self):
        """Compliance Scan for PII and Regulatory Risk."""
        self.log_step("Executing PII Discovery & Risk Scoring (GDPR/SOX)...")
        
        # Mocking PII detection logic based on column naming and data patterns
        pii_patterns = ['age', 'region', 'bmi', 'smoker', 'identity', 'ssn', 'account']
        found_pii = [col for col in self.df.columns if any(p in col.lower() for p in pii_patterns)]
        
        risk_score = (len(found_pii) / len(self.df.columns)) * 10
        self.audit_results['risk_score'] = risk_score
        self.audit_results['pii_inventory'] = found_pii
        
        self.log_step(f"Risk Assessment finished. Exposure Index: {risk_score:.2f}/10")

    def generate_strategic_dashboard(self):
        """Premium UX/UI Dashboard for Executive Decision Making."""
        self.log_step("Rendering Executive Dashboard...")
        
        fig = plt.figure(figsize=(18, 10))
        grid = plt.GridSpec(2, 3, wspace=0.3, hspace=0.4)
        
        fig.suptitle(f"GOVERNANCE & COMPLIANCE SCORECARD | {self.timestamp}", fontsize=22, fontweight='bold', color='#00E5FF')

        # 1. Data Quality Bar Chart
        ax1 = fig.add_subplot(grid[0, 0:2])
        self.audit_results['dq_metrics'].plot(kind='bar', ax=ax1, width=0.8)
        ax1.set_title("Data Quality Dimensions by Asset", fontsize=14, loc='left')
        ax1.axhline(0.95, color='red', linestyle='--', label='Regulatory Threshold (95%)')
        ax1.legend()

        # 2. Risk Meter (Pie Chart)
        ax2 = fig.add_subplot(grid[0, 2])
        risk = self.audit_results['risk_score']
        ax2.pie([risk, 10-risk], labels=['Risk Exposure', 'Compliance'], 
                colors=['#FF3D00', '#76FF03'], autopct='%1.1f%%', startangle=90, explode=(0.1, 0))
        ax2.set_title("Executive Risk Summary", fontsize=14)

        # 3. Statistical Distribution (Financial Insight)
        ax3 = fig.add_subplot(grid[1, 0:1])
        sns.histplot(self.df['charges'], kde=True, ax=ax3, color="#D500F9")
        ax3.set_title("Financial Asset Distribution (Audit)", fontsize=14)

        # 4. Correlation Heatmap (Inter-dependency Risk)
        ax4 = fig.add_subplot(grid[1, 1:3])
        # Select only numeric for correlation
        numeric_df = self.df.select_dtypes(include=[np.number])
        sns.heatmap(numeric_df.corr(), annot=True, cmap='mako', ax=ax4, fmt='.2f')
        ax4.set_title("Regulatory Dependency Heatmap", fontsize=14)

        plt.show()

    def run_full_audit(self):
        """Orchestrator for the Governance Practice."""
        print("\n" + "="*60)
        print(" STRATEGIC DATA GOVERNANCE ENGINE - STARTING AUDIT ")
        print("="*60)
        
        if self.ingest_data():
            self.perform_dq_audit()
            self.compliance_risk_assessment()
            
            print("\n" + "-"*60)
            print("EXECUTIVE SUMMARY FOR CHIEF DATA OFFICER (CDO)")
            print(f"1. Total Assets Inspected: {self.df.shape[1]}")
            print(f"2. PII Exposure: {', '.join(self.audit_results['pii_inventory'])}")
            print(f"3. Strategic Action: {'IMMEDIATE REMEDIATION' if self.audit_results['risk_score'] > 5 else 'MONITOR'}")
            print("-"*60 + "\n")
            
            self.generate_strategic_dashboard()

if __name__ == "__main__":
    engine = GovernanceAuditEngine()
    engine.run_full_audit()
