import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import requests
import io

def download_dataset():
    print("[INFO] Initiating Secure Data Retrieval...")
    # Dataset: Online Retail de la UCI
    url = "https://archive.ics.uci.edu/ml/machine-learning-databases/00352/Online%20Retail.xlsx"
    try:
        response = requests.get(url)
        df = pd.read_excel(io.BytesIO(response.content))
        print(f"[SUCCESS] Dataset loaded: {df.shape[0]} records found.")
        return df
    except Exception as e:
        print(f"[ERROR] Connection failed: {e}")
        return None

def apply_quality_rules(df):
    print("[INFO] Applying Advanced Governance Rules & Dimensions...")
    
    # 1. COMPLETENESS: Auditoría de nulos
    df['Null_Count'] = df.isnull().sum(axis=1)
    df['Completeness_Score'] = ((df.shape[1] - df['Null_Count']) / df.shape[1]) * 100
    
    # 2. ACCURACY: Integridad Financiera
    Q1 = df['UnitPrice'].quantile(0.25)
    Q3 = df['UnitPrice'].quantile(0.75)
    IQR = Q3 - Q1
    df['Price_Outlier'] = (df['UnitPrice'] < (Q1 - 1.5 * IQR)) | (df['UnitPrice'] > (Q3 + 1.5 * IQR))
    
    # 3. GLOBAL QUALITY SCORE: Dimensión de Consistencia
    df['Quality_Score'] = df['Completeness_Score']
    df.loc[df['CustomerID'].isnull(), 'Quality_Score'] *= 0.7 
    df.loc[df['UnitPrice'] <= 0, 'Quality_Score'] *= 0.5

    report = {
        "Avg_Score": df['Quality_Score'].mean(),
        "Missing_Customers": df['CustomerID'].isnull().sum(),
        "Invalid_Prices": (df['UnitPrice'] <= 0).sum(),
        "Total_Outliers": df['Price_Outlier'].sum(),
        "Null_Summary": df.isnull().sum()[df.isnull().sum() > 0].to_dict()
    }
    
    return df, report

def create_premium_dashboard(df, report):
    print("[INFO] Building High-Impact Visualizations...")
    colors = {'primary': '#1A5276', 'secondary': '#A93226', 'accent': '#229954'}

    fig = make_subplots(
        rows=2, cols=2,
        specs=[[{"type": "indicator"}, {"type": "bar"}],
               [{"type": "scatter"}, {"type": "treemap"}]],
        subplot_titles=("Global Data Health Index", "Completeness Audit (Log Scale)", 
                        "Accuracy: Price vs Quantity Correlation", "Integrity by Region (Market Treemap)")
    )

    # --- 1. KPI GAUGE ---
    fig.add_trace(go.Indicator(
        mode = "gauge+number",
        value = report["Avg_Score"],
        number = {'suffix': "%"},
        title = {'text': "Reliability Index"},
        gauge = {'axis': {'range': [0, 100]}, 'bar': {'color': colors['primary']}}
    ), row=1, col=1)

    # --- 2. BAR CHART ---
    null_df = pd.DataFrame(list(report["Null_Summary"].items()), columns=['Field', 'Count'])
    fig.add_trace(go.Bar(
        x=null_df['Field'], 
        y=np.log10(null_df['Count'] + 1), 
        text=null_df['Count'], 
        marker_color=colors['secondary']
    ), row=1, col=2)

    # --- 3. SCATTER PLOT ---
    sample_df = df.sample(n=5000) if len(df) > 5000 else df
    fig.add_trace(go.Scatter(
        x=sample_df['Quantity'], y=sample_df['UnitPrice'],
        mode='markers', 
        marker=dict(color=sample_df['Quality_Score'], colorscale='RdYlGn', showscale=True),
        text=sample_df['Description']
    ), row=2, col=1)

    # --- 4. TREEMAP (CORREGIDO) ---
    country_data = df.groupby('Country').agg({'Quality_Score': 'mean', 'InvoiceNo': 'count'}).reset_index()
    country_data = country_data[country_data['InvoiceNo'] > 100]
    
    fig.add_trace(go.Treemap(
        labels=country_data['Country'],
        parents=[""] * len(country_data),
        values=country_data['InvoiceNo'],
        marker=dict(colors=country_data['Quality_Score'], colorscale='Viridis'),
        hovertemplate='<b>%{label}</b><br>Volume: %{value}<br>Quality Score: %{color:.2f}%'
    ), row=2, col=2)

    fig.update_layout(template="plotly_white", height=900, title_text="<b>ENTERPRISE DATA GOVERNANCE PORTAL</b>")
    fig.write_html("Data_Quality_Report.html")
    fig.show()

def main():
    raw_data = download_dataset()
    if raw_data is not None:
        processed_data, audit_report = apply_quality_rules(raw_data)
        print("\n" + "═"*60)
        print(f" 📊 AUDIT SUMMARY: {audit_report['Avg_Score']:.1f}% Global Reliability")
        print(" ═"*60 + "\n")
        create_premium_dashboard(processed_data, audit_report)

if __name__ == "__main__":
    main()
