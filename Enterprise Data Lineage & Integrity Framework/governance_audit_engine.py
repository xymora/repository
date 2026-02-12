import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
import requests
import os
import hashlib
from datetime import datetime
from io import StringIO
import platform # Para detectar el Sistema Operativo

# --- CONFIGURATION ---
DATA_URL = "https://repodatos.atdt.gob.mx/api_update/senasica/productos_regulados_registrados/productos_regulados_y_registrados_ok.csv"
LOG_FILE = "data_audit_trail.log"
REPORT_IMG = "governance_dashboard_premium.png"

def log_audit_event(step, status, details):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    log_entry = f"[{timestamp}] | {step:18} | {status:8} | {details}\n"
    with open(LOG_FILE, "a", encoding='utf-8') as f:
        f.write(log_entry)
    print(log_entry.strip())

def main():
    log_audit_event("PROCESS_START", "INIT", "Iniciando Pipeline de Gobernanza")

    try:
        # 1. INGESTA (BRONZE)
        response = requests.get(DATA_URL)
        df = pd.read_csv(StringIO(response.text))
        initial_count = len(df)
        log_audit_event("INGESTION", "SUCCESS", f"Registros iniciales: {initial_count}")

        # 2. CURACIÓN (SILVER)
        df.columns = [c.lower().replace(" ", "_").strip() for c in df.columns]
        crit_cols = [col for col in df.columns if 'nombre' in col or 'producto' in col]
        df_silver = df.dropna(subset=crit_cols).drop_duplicates()
        final_count = len(df_silver)
        log_audit_event("CURATION", "SUCCESS", f"Registros limpios: {final_count}")

        # 3. GENERACIÓN DE GRÁFICOS (GOLD)
        log_audit_event("REPORTING", "START", "Renderizando Dashboard Premium...")
        
        plt.style.use('dark_background')
        fig = plt.figure(figsize=(16, 10), facecolor='#0B0E14')
        grid = plt.GridSpec(2, 2, wspace=0.3, hspace=0.4)

        # Gráfica 1: Top Productos
        ax1 = fig.add_subplot(grid[0, 0])
        top_data = df_silver[crit_cols[0]].value_counts().head(10)
        sns.barplot(x=top_data.values, y=top_data.index, ax=ax1, palette="viridis")
        ax1.set_title("TOP 10 PRODUCTOS REGULADOS", color='#00FFCC', weight='bold')

        # Gráfica 2: Calidad de Datos (Donut)
        ax2 = fig.add_subplot(grid[0, 1])
        null_count = df.isnull().sum().sum()
        ax2.pie([df.size - null_count, null_count], labels=['Válidos', 'Nulos'], 
                colors=['#00FFCC', '#FF3366'], autopct='%1.1f%%', startangle=140)
        ax2.add_artist(plt.Circle((0,0), 0.70, fc='#0B0E14'))
        ax2.set_title("ÍNDICE DE INTEGRIDAD", color='#00FFCC', weight='bold')

        # Gráfica 3: Flujo de Datos
        ax3 = fig.add_subplot(grid[1, :])
        ax3.plot(['Bronze', 'Silver', 'Gold'], [initial_count, final_count, final_count], 
                 marker='o', color='#00FFCC', linewidth=4)
        ax3.set_title("TRAZABILIDAD: FLUJO DE VOLUMEN DE DATOS", color='#00FFCC', weight='bold')

        plt.suptitle(f"DATA GOVERNANCE AUDIT - {datetime.now().year}", fontsize=22, color='white', weight='bold')
        
        # GUARDAR Y MOSTRAR
        plt.savefig(REPORT_IMG, dpi=300, bbox_inches='tight')
        log_audit_event("REPORTING", "SUCCESS", f"Reporte guardado en: {REPORT_IMG}")

        # --- AQUÍ ESTÁ EL TRUCO PARA ABRIRLO AUTOMÁTICAMENTE ---
        print("\nAbriendo reporte visual...")
        if platform.system() == 'Windows':
            os.startfile(REPORT_IMG) # Abre la imagen con el visor predeterminado de Windows
        elif platform.system() == 'Darwin': # macOS
            os.system(f"open {REPORT_IMG}")
        else: # Linux
            os.system(f"xdg-open {REPORT_IMG}")

        # También puedes usar plt.show() si quieres que se abra una ventana interactiva de Python
        # plt.show() 

    except Exception as e:
        log_audit_event("PIPELINE", "ERROR", str(e))

if __name__ == "__main__":
    main()
