import pandas as pd
import numpy as np
import yfinance as yf
import matplotlib.pyplot as plt
import seaborn as sns
import plotly.graph_objects as go
from datetime import datetime
from sklearn.preprocessing import MinMaxScaler

# ==========================================
# DATA GOVERNANCE LAYER: CONFIGURATION
# ==========================================
PROJECT_NAME = "Project Phoenix"
DATA_SOURCE = "KO"  # Coca-Cola Ticker
START_DATE = "2005-01-01"
END_DATE = "2021-12-31"

class DataGovernanceManager:
    """Handles Data Quality and Integrity Rules"""
    @staticmethod
    def validate_data(df):
        print(f"[{datetime.now()}] Initiating Data Quality Checks...")
        # Check for Nulls
        null_count = df.isnull().sum().sum()
        # Check for Outliers (Z-Score)
        z_scores = np.abs((df - df.mean()) / df.std())
        outliers = (z_scores > 3).sum().sum()
        
        print(f"-> Integrity Report: {null_count} Nulls found, {outliers} Outliers detected.")
        return null_count == 0

# ==========================================
# DATA ACQUISITION & ETL
# ==========================================
def fetch_corporate_data(ticker, start, end):
    print(f"Fetching Historical Data for {ticker}...")
    raw_data = yf.download(ticker, start=start, end=end)
    
    # Governance Check
    gov = DataGovernanceManager()
    if gov.validate_data(raw_data):
        raw_data.to_csv("coca_cola_market_data.csv")
        return raw_data
    else:
        print("Data Inconsistency Detected. Cleaning...")
        return raw_data.fillna(method='ffill')

# ==========================================
# ANALYTICS & DASHBOARD GENERATION
# ==========================================
def generate_executive_dashboard(df):
    sns.set_theme(style="whitegrid")
    plt.figure(figsize=(16, 9))
    
    # Subplot 1: Price Evolution
    plt.subplot(2, 1, 1)
    plt.plot(df.index, df['Adj Close'], color='#F40009', linewidth=2) # Coca-Cola Red
    plt.title(f"{PROJECT_NAME}: Market Capitalization Trends (2005-2021)", fontsize=16)
    plt.ylabel("Adjusted Close Price (USD)")
    
    # Subplot 2: Volume Analysis (Market Liquidty)
    plt.subplot(2, 1, 2)
    plt.fill_between(df.index, df['Volume'], color='gray', alpha=0.3)
    plt.title("Transaction Volume & Market Liquidity Governance", fontsize=14)
    plt.ylabel("Volume")
    
    plt.tight_layout()
    plt.savefig("Executive_Summary_Chart.png")
    print("Dashboard saved as 'Executive_Summary_Chart.png'")

def generate_interactive_chart(df):
    """Generates a Premium UI/UX Interactive Chart with Plotly"""
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=df.index, y=df['Adj Close'],
                    mode='lines',
                    name='Stock Price',
                    line=dict(color='#F40009', width=3)))

    fig.update_layout(
        title='Coca-Cola Performance Analysis (Governance Framework Applied)',
        xaxis_title='Timeline',
        yaxis_title='USD Value',
        template='plotly_dark',
        font=dict(family="Arial, sans-serif", size=12)
    )
    fig.show()

# ==========================================
# MAIN EXECUTION (STRATEGIC LAYER)
# ==========================================
if __name__ == "__main__":
    print("-" * 50)
    print(f"INITIALIZING {PROJECT_NAME} CORPORATE PROTOCOL")
    print("-" * 50)
    
    # 1. Extraction with Governance
    data = fetch_corporate_data(DATA_SOURCE, START_DATE, END_DATE)
    
    # 2. Advanced Feature Engineering (Governance Rule: Data Enrichment)
    data['MA50'] = data['Adj Close'].rolling(window=50).mean()
    data['MA200'] = data['Adj Close'].rolling(window=200).mean()
    data['Volatility'] = data['Adj Close'].pct_change().rolling(window=21).std()
    
    # 3. Console Insights (High-Level Decision Support)
    avg_price = data['Adj Close'].mean()
    max_price = data['Adj Close'].max()
    current_vol = data['Volatility'].iloc[-1]
    
    print("\n" + "="*30)
    print("STRATEGIC INSIGHTS REPORT")
    print("="*30)
    print(f"Mean Trading Price: ${avg_price:.2f}")
    print(f"Peak Valuation:     ${max_price:.2f}")
    print(f"Market Volatility:  {current_vol:.4%}")
    print("Decision Status:    READY FOR QUARTERLY REVIEW")
    print("="*30 + "\n")
    
    # 4. Visualization
    generate_executive_dashboard(data)
    # generate_interactive_chart(data) # Descomentar para ver en navegador
