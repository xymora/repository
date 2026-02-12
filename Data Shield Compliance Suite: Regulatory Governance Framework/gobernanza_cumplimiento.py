import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
from faker import Faker
import os

# --- CONFIGURACIÓN DE UI/UX ---
plt.style.use('ggplot')
sns.set_palette("viridis")

class DataGovernanceEngine:
    """
    Framework para la simulación de cumplimiento regulatorio (GDPR/LFPDPPP).
    Desarrollado para prácticas profesionales de Data Science.
    """
    
    def __init__(self):
        self.fake = Faker()
        self.dataset = None
        self.audit_results = None

    def generate_professional_dataset(self, n_records=1000):
        """Genera datos sintéticos que simulan una DB de clientes bancarios."""
        print("[INFO] Generando dataset de gobernanza...")
        data = []
        for _ in range(n_records):
            data.append({
                'customer_id': self.fake.uuid4(),
                'name': self.fake.name(),
                'email': self.fake.email(),
                'age': np.random.randint(18, 85),
                'country': np.random.choice(['Mexico', 'Spain', 'Germany', 'USA', 'France']),
                'phone': self.fake.phone_number(),
                'consent_given': np.random.choice([True, False], p=[0.7, 0.3]),
                'last_login_days': np.random.randint(0, 1000),
                'is_encrypted': np.random.choice([True, False], p=[0.8, 0.2]),
                'data_category': np.random.choice(['Public', 'Internal', 'Confidential', 'Restricted'], p=[0.1, 0.4, 0.3, 0.2])
            })
        self.dataset = pd.DataFrame(data)
        self.dataset.to_csv('audit_dataset.csv', index=False)
        print(f"[SUCCESS] Dataset guardado como 'audit_dataset.csv'. Registros: {len(self.dataset)}")

    def run_compliance_audit(self):
        """Aplica reglas de negocio basadas en GDPR y LFPDPPP."""
        print("[PROCESS] Iniciando auditoría de cumplimiento...")
        df = self.dataset.copy()
        
        # Regla 1: Riesgo de Exposición (PII sin encriptación)
        df['pii_risk_score'] = df.apply(lambda x: 100 if not x['is_encrypted'] and x['data_category'] in ['Confidential', 'Restricted'] else 0, axis=1)
        
        # Regla 2: Derecho al Olvido / Retención (GDPR Art. 5)
        # Si no ha entrado en > 730 días (2 años), marcar para eliminación
        df['retention_violation'] = df['last_login_days'] > 730
        
        # Regla 3: Falta de Consentimiento (LFPDPPP Art. 8)
        df['consent_breach'] = ~df['consent_given']
        
        self.audit_results = df
        print("[SUCCESS] Auditoría completada.")

    def generate_dashboard(self):
        """Genera visualizaciones profesionales para la toma de decisiones."""
        if self.audit_results is None:
            return
            
        fig, axes = plt.subplots(2, 2, figsize=(16, 12))
        fig.suptitle('Dashboard de Gobernanza de Datos & Cumplimiento Legal', fontsize=20, fontweight='bold')

        # Gráfico 1: Riesgo PII por País
        risk_by_country = self.audit_results.groupby('country')['pii_risk_score'].mean()
        risk_by_country.plot(kind='barh', ax=axes[0, 0], color='#e74c3c')
        axes[0, 0].set_title('Riesgo de Exposición PII por Región (%)')
        axes[0, 0].set_xlabel('Score de Riesgo Promedio')

        # Gráfico 2: Violaciones de Retención (Derecho al Olvido)
        retention_counts = self.audit_results['retention_violation'].value_counts()
        axes[0, 1].pie(retention_counts, labels=['Cumple', 'Violación'], autopct='%1.1f%%', colors=['#2ecc71', '#f1c40f'], startangle=90)
        axes[0, 1].set_title('Estado de Retención de Datos (GDPR Art. 17)')

        # Gráfico 3: Consentimiento por Categoría de Datos
        sns.heatmap(pd.crosstab(self.audit_results['data_category'], self.audit_results['consent_given']), 
                    annot=True, fmt='d', cmap='Blues', ax=axes[1, 0])
        axes[1, 0].set_title('Matriz de Consentimiento vs Categoría de Datos')

        # Gráfico 4: Distribución de Edad vs Riesgo
        sns.boxplot(x='data_category', y='age', data=self.audit_results, ax=axes[1, 1])
        axes[1, 1].set_title('Distribución de Datos Sensibles por Rango de Edad')

        plt.tight_layout(rect=[0, 0.03, 1, 0.95])
        plt.show()

    def print_executive_report(self):
        """Imprime resumen ejecutivo en consola."""
        total = len(self.audit_results)
        violations = self.audit_results['retention_violation'].sum()
        risk_avg = self.audit_results['pii_risk_score'].mean()
        
        print("\n" + "="*50)
        print("          RESUMEN EJECUTIVO DE CUMPLIMIENTO")
        print("="*50)
        print(f"Total de registros auditados: {total}")
        print(f"Alertas de Retención (GDPR):  {violations} ({(violations/total)*100:.2f}%)")
        print(f"Índice de Riesgo Global PII:  {risk_avg:.2f}/100")
        print("-" * 50)
        
        if risk_avg > 15:
            print("ESTADO: [CRÍTICO] - Se requiere encriptación inmediata.")
        else:
            print("ESTADO: [SALUDABLE] - Los controles están operando.")
        print("="*50 + "\n")

if __name__ == "__main__":
    engine = DataGovernanceEngine()
    engine.generate_professional_dataset(1500)
    engine.run_compliance_audit()
    engine.print_executive_report()
    engine.generate_dashboard()
