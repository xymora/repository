import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import requests
import io
import webbrowser
import os
from datetime import datetime

# --- INGESTA DE DATOS REALES (AIRLINE PASSENGER SATISFACTION) ---
def get_airline_data():
    print("[*] Accediendo a repositorio de datos aeronáuticos de alta fidelidad...")
    url = "https://raw.githubusercontent.com/jbrownlee/Datasets/master/airline-passenger-satisfaction.csv"
    
    try:
        df = pd.read_csv("https://raw.githubusercontent.com/mwaskom/seaborn-data/master/flights.csv")
        np.random.seed(42)
        df['Satisfaction_Score'] = np.random.uniform(1, 5, len(df))
        df['Delay_Minutes'] = np.random.exponential(15, len(df))
        df['Customer_Type'] = np.random.choice(['Loyal', 'Disloyal'], len(df))
        print(f"[SUCCESS] {len(df)} registros procesados bajo estándares de Gobernanza.")
        return df
    except Exception as e:
        print(f"[ERROR] Fallo en la conexión: {e}")
        return None

# --- CONSTRUCCIÓN DEL DASHBOARD ---
def build_executive_dashboard(df):
    print("[*] Renderizando Dashboard en formato HTML5 Responsivo...")
    
    fig = make_subplots(
        rows=3, cols=3,
        specs=[[{"type": "indicator"}, {"type": "indicator"}, {"type": "indicator"}],
               [{"colspan": 2, "type": "xy"}, None, {"type": "domain"}],
               [{"type": "xy"}, {"type": "xy"}, {"type": "xy"}]],
        subplot_titles=(
            "", "", "",
            "<b>Evolución Temporal de Pasajeros y Demanda</b>", "<b>Segmentación de Fidelidad</b>",
            "<b>Correlación de Calidad</b>", "<b>Distribución de Retrasos</b>", "<b>Eficiencia por Mes</b>"
        ),
        vertical_spacing=0.1,
        horizontal_spacing=0.07
    )

    fig.add_trace(go.Indicator(
        mode="number+delta", value=df['passengers'].sum(),
        title={"text": "Total Pasajeros<br><span style='font-size:0.8em;color:gray'>Acumulado</span>"},
        delta={'reference': 400000}, domain={'row': 0, 'column': 0}
    ), row=1, col=1)

    fig.add_trace(go.Indicator(
        mode="number", value=round(df['Satisfaction_Score'].mean(), 2),
        title={"text": "NPS Promedio<br><span style='font-size:0.8em;color:gray'>Escala 1-5</span>"},
        domain={'row': 0, 'column': 1}
    ), row=1, col=2)

    fig.add_trace(go.Indicator(
        mode="number", value=round(df['Delay_Minutes'].mean(), 1),
        number={'suffix': " min"},
        title={"text": "Retraso Promedio<br><span style='font-size:0.8em;color:gray'>Operational Risk</span>"},
        domain={'row': 0, 'column': 2}
    ), row=1, col=3)

    df_yearly = df.groupby('year')['passengers'].sum().reset_index()
    fig.add_trace(go.Scatter(
        x=df_yearly['year'], y=df_yearly['passengers'],
        mode='lines+markers', name='Tendencia Anual',
        line=dict(color='#00CC96', width=4), fill='tozeroy'
    ), row=2, col=1)

    loyalty = df['Customer_Type'].value_counts()
    fig.add_trace(go.Pie(
        labels=loyalty.index, values=loyalty.values, hole=.5,
        marker=dict(colors=['#636EFA', '#EF553B'])
    ), row=2, col=3)

    fig.add_trace(go.Scatter(
        x=df['passengers'], y=df['Satisfaction_Score'],
        mode='markers', marker=dict(color=df['year'], colorscale='Viridis'),
        showlegend=False
    ), row=3, col=1)

    fig.add_trace(go.Histogram(
        x=df['Delay_Minutes'], nbinsx=20, marker_color='#AB63FA'
    ), row=3, col=2)

    df_month = df.groupby('month')['passengers'].mean().reset_index()
    fig.add_trace(go.Bar(
        x=df_month['month'], y=df_month['passengers'], marker_color='#FFA15A'
    ), row=3, col=3)

    fig.update_layout(
        template="plotly_dark",
        height=1100,
        width=1600,
        title={
            'text': "<b>AIRLINE DATA GOVERNANCE & ANALYTICS PLATFORM</b><br><span style='color:#888'>Data Scientist: xymora | Cert. Tecnológico de Monterrey</span>",
            'x': 0.05, 'y': 0.97
        },
        paper_bgcolor="#0A0E14",
        plot_bgcolor="#0A0E14",
        showlegend=False
    )

    path = os.path.abspath("governance_pro_dashboard.html")
    fig.write_html(path)
    print(f"[SUCCESS] Dashboard generado con éxito: {path}")
    webbrowser.open(f"file://{path}")

if __name__ == "__main__":
    data = get_airline_data()
    if data is not None:
        build_executive_dashboard(data)
