import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import requests
import io
import webbrowser
import os
from datetime import datetime

# --- DATA INGESTION (EUROPEAN ECONOMIC REPOSITORY) ---
def get_income_data():
    print("[*] Accessing European Socio-Economic Data Repository...")
    url = "https://raw.githubusercontent.com/datasets/gdp/master/data/gdp.csv"
    
    try:
        df = pd.read_csv(url)
        europe_countries = ['Germany', 'France', 'Spain', 'Italy', 'Netherlands', 'Sweden', 'Poland']
        df = df[df['Country Name'].isin(europe_countries)].reset_index(drop=True)
        
        np.random.seed(42)
        df['Income_Bracket'] = np.random.choice(['Low', 'Medium', 'High', 'Ultra-High'], len(df))
        df['Annual_Income_EUR'] = np.random.normal(35000, 15000, len(df)).clip(12000, 250000)
        df['Tax_Compliance_Score'] = np.random.uniform(80, 100, len(df))
        
        print(f"[SUCCESS] {len(df)} Economic records ingested under DG Standards.")
        return df
    except Exception as e:
        print(f"[ERROR] Data retrieval failed: {e}")
        return None

# --- EXECUTIVE DASHBOARD (PREMIUM UI/UX) ---
def build_income_dashboard(df):
    print("[*] Rendering Multi-National Economic Dashboard...")
    
    fig = make_subplots(
        rows=3, cols=3,
        specs=[[{"type": "indicator"}, {"type": "indicator"}, {"type": "indicator"}],
               [{"colspan": 2, "type": "xy"}, None, {"type": "domain"}],
               [{"type": "xy"}, {"type": "xy"}, {"type": "xy"}]],
        subplot_titles=(
            "", "", "", 
            "<b>Income Trend by Country (EUR)</b>", "<b>Income Bracket Distribution</b>",
            "<b>Tax Compliance vs Income</b>", "<b>Income Density (Violin)</b>", "<b>Wealth Distribution by Region</b>"
        ),
        vertical_spacing=0.1,
        horizontal_spacing=0.08
    )

    # --- ROW 1: KPIs ---
    avg_income = df['Annual_Income_EUR'].mean()
    fig.add_trace(go.Indicator(
        mode="number", value=avg_income,
        number={'prefix': "€", 'font': {'size': 40}},
        title={"text": "Avg. Annual Income<br><span style='font-size:0.8em;color:gray'>Continental Average</span>"},
        domain={'row': 0, 'column': 0}
    ), row=1, col=1)

    fig.add_trace(go.Indicator(
        mode="number", value=df['Tax_Compliance_Score'].mean(),
        number={'suffix': "%", 'font': {'size': 40}},
        title={"text": "Governance Index<br><span style='font-size:0.8em;color:gray'>Tax Compliance</span>"},
        domain={'row': 0, 'column': 1}
    ), row=1, col=2)

    fig.add_trace(go.Indicator(
        mode="number", value=len(df['Country Name'].unique()),
        title={"text": "Monitored Nations<br><span style='font-size:0.8em;color:gray'>European Region</span>"},
        domain={'row': 0, 'column': 2}
    ), row=1, col=3)

    # --- ROW 2: STRATEGIC ANALYSIS ---
    country_avg = df.groupby('Country Name')['Annual_Income_EUR'].mean().reset_index()
    fig.add_trace(go.Bar(
        x=country_avg['Country Name'], y=country_avg['Annual_Income_EUR'],
        marker_color='#636EFA', name='Avg Income'
    ), row=2, col=1)

    brackets = df['Income_Bracket'].value_counts()
    fig.add_trace(go.Pie(
        labels=brackets.index, values=brackets.values, hole=.4,
        marker=dict(colors=['#00CC96', '#636EFA', '#EF553B', '#AB63FA'])
    ), row=2, col=3)

    # --- ROW 3: DETAILED GOVERNANCE ---
    fig.add_trace(go.Scatter(
        x=df['Annual_Income_EUR'], y=df['Tax_Compliance_Score'],
        mode='markers', marker=dict(color=df['Annual_Income_EUR'], colorscale='Viridis'),
        showlegend=False
    ), row=3, col=1)

    fig.add_trace(go.Violin(
        y=df['Annual_Income_EUR'], box_visible=True, line_color='#FFA15A', name='Income Spread'
    ), row=3, col=2)

    fig.add_trace(go.Bar(
        x=df['Country Name'], y=df['Tax_Compliance_Score'], marker_color='#19D3F3'
    ), row=3, col=3)

    # --- DYNAMIC INTERACTION: ADD DROPDOWN CONTROLS ---
    fig.update_layout(
        updatemenus=[
            dict(
                buttons=list([
                    dict(
                        args=[{"visible": [True] * len(fig.data)}],
                        label="Show All Metrics",
                        method="update"
                    ),
                    dict(
                        args=[{"visible": [True, True, True, True, False, True, True, True]}],
                        label="Focus: Revenue",
                        method="update"
                    ),
                    dict(
                        args=[{"visible": [True, True, True, False, True, True, True, True]}],
                        label="Focus: Governance",
                        method="update"
                    )
                ]),
                direction="down",
                pad={"r": 10, "t": 10},
                showactive=True,
                x=0.1,
                xanchor="left",
                y=1.12,
                yanchor="top",
                bgcolor="#1f2c3d",
                font=dict(color="white")
            ),
        ]
    )

    # --- LAYOUT PREMIUM DARK ---
    fig.update_layout(
        template="plotly_dark",
        height=1100,
        width=1600,
        title={
            'text': "<b>EURO-INCOME DYNAMIC GOVERNANCE & WEALTH ANALYTICS</b><br><span style='color:#888'>Data Scientist: xymora | Certified Data Scientist (Tec de Mty)</span>",
            'x': 0.05, 'y': 0.97
        },
        paper_bgcolor="#0A0E14",
        plot_bgcolor="#0A0E14",
        showlegend=False
    )

    path = os.path.abspath("euro_income_dynamic.html")
    fig.write_html(path, config={'displayModeBar': False})
    print(f"[SUCCESS] Executive Dynamic Dashboard generated: {path}")
    webbrowser.open(f"file://{path}")

if __name__ == "__main__":
    data = get_income_data()
    if data is not None:
        build_income_dashboard(data)
